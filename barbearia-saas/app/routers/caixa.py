"""Fluxo de caixa com sessões (abertura → reforço/sangria/recebimentos → fechamento).

O fechamento calcula o valor esperado em DINHEIRO da sessão
(inicial + reforços + recebimentos em dinheiro − sangrias − estornos em dinheiro)
e registra a divergência contra o valor contado, com responsável e auditoria.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..audit import auditar
from ..auth import contexto_tenant
from ..db import get_db, row, rows
from ..util import agora_tenant

router = APIRouter(prefix="/api/caixa", tags=["caixa"])

CATEGORIAS_MANUAIS = ("servico", "produto", "aluguel_cadeira", "comissao",
                      "despesa_fixa", "despesa_variavel", "imposto", "outro")


class LancamentoIn(BaseModel):
    data: str
    tipo: str
    categoria: str
    descricao: str
    valor: float


class AberturaIn(BaseModel):
    valor_inicial: float = 0


class MovimentoSessaoIn(BaseModel):
    valor: float
    descricao: str = ""


class FechamentoSessaoIn(BaseModel):
    valor_contado: float


def sessao_aberta(db, tenant_id: int) -> dict | None:
    return row(db.execute(
        "SELECT * FROM cash_sessions WHERE tenant_id=? AND status='aberta' ORDER BY id DESC",
        (tenant_id,)))


@router.get("")
def listar(inicio: str = "", fim: str = "", usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        hoje = agora_tenant(db, usuario["tenant_id"]).date()
        inicio = inicio or hoje.replace(day=1).isoformat()
        fim = fim or hoje.isoformat()
        lancamentos = rows(db.execute(
            """SELECT * FROM lancamentos_caixa WHERE tenant_id=? AND data BETWEEN ? AND ?
               ORDER BY data DESC, id DESC""", (usuario["tenant_id"], inicio, fim)))
        totais = row(db.execute(
            """SELECT COALESCE(SUM(CASE WHEN tipo='entrada' THEN valor END),0) entradas,
                      COALESCE(SUM(CASE WHEN tipo='saida' THEN valor END),0) saidas
               FROM lancamentos_caixa WHERE tenant_id=? AND data BETWEEN ? AND ?""",
            (usuario["tenant_id"], inicio, fim)))
        sessao = sessao_aberta(db, usuario["tenant_id"])
    return {"periodo": {"inicio": inicio, "fim": fim}, "lancamentos": lancamentos,
            "entradas": round(totais["entradas"], 2), "saidas": round(totais["saidas"], 2),
            "saldo": round(totais["entradas"] - totais["saidas"], 2),
            "sessao_aberta": sessao}


@router.post("")
def lancar(dados: LancamentoIn, usuario: dict = Depends(contexto_tenant)):
    if dados.tipo not in ("entrada", "saida"):
        raise HTTPException(422, "Tipo deve ser entrada ou saida")
    if dados.categoria not in CATEGORIAS_MANUAIS:
        raise HTTPException(422, f"Categoria manual deve ser uma de: {', '.join(CATEGORIAS_MANUAIS)}")
    if dados.valor <= 0:
        raise HTTPException(422, "Valor deve ser positivo")
    with get_db() as db:
        sessao = sessao_aberta(db, usuario["tenant_id"])
        lanc_id = db.insert(
            "INSERT INTO lancamentos_caixa (tenant_id, sessao_id, data, tipo, categoria, descricao, valor) VALUES (?,?,?,?,?,?,?)",
            (usuario["tenant_id"], sessao["id"] if sessao else None, dados.data,
             dados.tipo, dados.categoria, dados.descricao, dados.valor))
        return {"id": lanc_id}


@router.delete("/{lanc_id}")
def excluir(lanc_id: int, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        lanc = row(db.execute("SELECT * FROM lancamentos_caixa WHERE id=? AND tenant_id=?",
                              (lanc_id, usuario["tenant_id"])))
        if not lanc:
            raise HTTPException(404, "Lançamento não encontrado")
        if lanc["agendamento_id"] or lanc["categoria"] in ("abertura", "reforco", "sangria", "estorno"):
            raise HTTPException(422, "Lançamento automático ou de sessão não pode ser excluído manualmente")
        db.execute("DELETE FROM lancamentos_caixa WHERE id=?", (lanc_id,))
        auditar(db, usuario["tenant_id"], usuario["uid"], "lancamento_excluido",
                "lancamento", lanc_id, f"{lanc['categoria']} {lanc['valor']:.2f}")
    return {"mensagem": "Lançamento excluído"}


# ---------- sessões de caixa ----------

@router.post("/sessao/abrir")
def abrir_sessao(dados: AberturaIn, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        if sessao_aberta(db, usuario["tenant_id"]):
            raise HTTPException(409, "Já existe uma sessão de caixa aberta")
        agora = agora_tenant(db, usuario["tenant_id"])
        sessao_id = db.insert(
            "INSERT INTO cash_sessions (tenant_id, aberto_por, aberto_em, valor_inicial) VALUES (?,?,?,?)",
            (usuario["tenant_id"], usuario["uid"], agora.strftime("%Y-%m-%dT%H:%M"), dados.valor_inicial))
        if dados.valor_inicial > 0:
            db.execute(
                "INSERT INTO lancamentos_caixa (tenant_id, sessao_id, data, tipo, categoria, descricao, valor) VALUES (?,?,?,?,?,?,?)",
                (usuario["tenant_id"], sessao_id, agora.strftime("%Y-%m-%d"), "entrada", "abertura",
                 "Abertura de caixa", dados.valor_inicial))
        auditar(db, usuario["tenant_id"], usuario["uid"], "caixa_aberto", "sessao", sessao_id,
                f"inicial={dados.valor_inicial:.2f}")
    return {"id": sessao_id}


def _mov_sessao(tipo: str):
    def handler(dados: MovimentoSessaoIn, usuario: dict = Depends(contexto_tenant)):
        if dados.valor <= 0:
            raise HTTPException(422, "Valor deve ser positivo")
        with get_db() as db:
            sessao = sessao_aberta(db, usuario["tenant_id"])
            if not sessao:
                raise HTTPException(409, "Nenhuma sessão de caixa aberta")
            agora = agora_tenant(db, usuario["tenant_id"])
            db.execute(
                "INSERT INTO lancamentos_caixa (tenant_id, sessao_id, data, tipo, categoria, descricao, valor) VALUES (?,?,?,?,?,?,?)",
                (usuario["tenant_id"], sessao["id"], agora.strftime("%Y-%m-%d"),
                 "entrada" if tipo == "reforco" else "saida", tipo,
                 dados.descricao or tipo.capitalize(), dados.valor))
            auditar(db, usuario["tenant_id"], usuario["uid"], f"caixa_{tipo}", "sessao", sessao["id"],
                    f"valor={dados.valor:.2f}")
        return {"mensagem": f"{tipo.capitalize()} registrado"}
    return handler


router.post("/sessao/reforco")(_mov_sessao("reforco"))
router.post("/sessao/sangria")(_mov_sessao("sangria"))


@router.post("/sessao/fechar")
def fechar_sessao(dados: FechamentoSessaoIn, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        sessao = sessao_aberta(db, usuario["tenant_id"])
        if not sessao:
            raise HTTPException(409, "Nenhuma sessão de caixa aberta")
        dinheiro = row(db.execute(
            """SELECT COALESCE(SUM(CASE WHEN lc.tipo='entrada' THEN lc.valor ELSE -lc.valor END),0) v
               FROM lancamentos_caixa lc
               LEFT JOIN payments p ON p.agendamento_id = lc.agendamento_id AND p.sessao_id = lc.sessao_id
               WHERE lc.sessao_id=? AND (
                     lc.categoria IN ('abertura','reforco','sangria')
                  OR (lc.categoria IN ('servico','produto') AND p.forma='dinheiro')
                  OR (lc.categoria='estorno' AND p.forma='dinheiro'))""",
            (sessao["id"],)))["v"]
        esperado = round(dinheiro, 2)
        divergencia = round(dados.valor_contado - esperado, 2)
        agora = agora_tenant(db, usuario["tenant_id"])
        db.execute(
            """UPDATE cash_sessions SET status='fechada', fechado_por=?, fechado_em=?,
               valor_esperado=?, valor_contado=?, divergencia=? WHERE id=?""",
            (usuario["uid"], agora.strftime("%Y-%m-%dT%H:%M"), esperado,
             dados.valor_contado, divergencia, sessao["id"]))
        auditar(db, usuario["tenant_id"], usuario["uid"], "caixa_fechado", "sessao", sessao["id"],
                f"esperado={esperado:.2f} contado={dados.valor_contado:.2f} divergencia={divergencia:.2f}")
    return {"valor_esperado_dinheiro": esperado, "valor_contado": dados.valor_contado,
            "divergencia": divergencia}


@router.get("/sessoes")
def listar_sessoes(usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return rows(db.execute(
            """SELECT s.*, u1.nome aberto_por_nome, u2.nome fechado_por_nome
               FROM cash_sessions s
               JOIN usuarios u1 ON u1.id=s.aberto_por
               LEFT JOIN usuarios u2 ON u2.id=s.fechado_por
               WHERE s.tenant_id=? ORDER BY s.id DESC LIMIT 60""", (usuario["tenant_id"],)))
