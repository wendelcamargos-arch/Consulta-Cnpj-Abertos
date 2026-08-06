"""Gestão de barbeiros, bloqueios de agenda, cadeiras físicas e contratos de aluguel."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..audit import auditar
from ..auth import contexto_tenant, exigir_gerente
from ..db import get_db, row, rows

router = APIRouter(prefix="/api/barbeiros", tags=["barbeiros"])


class BarbeiroIn(BaseModel):
    nome: str
    telefone: str = ""
    modelo: str = "comissao"
    percentual_comissao: float = 50
    valor_aluguel: float = 0
    hora_inicio: str = "09:00"
    hora_fim: str = "19:00"


class BloqueioIn(BaseModel):
    inicio: str            # YYYY-MM-DDTHH:MM
    fim: str
    motivo: str = ""


class CadeiraIn(BaseModel):
    nome: str


class ContratoIn(BaseModel):
    chair_id: int
    barbeiro_id: int
    valor_mensal: float
    inicio: str            # YYYY-MM-DD


@router.get("")
def listar(usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return rows(db.execute(
            "SELECT * FROM barbeiros WHERE tenant_id=? AND ativo=1 ORDER BY nome", (usuario["tenant_id"],)))


@router.post("")
def criar(dados: BarbeiroIn, usuario: dict = Depends(exigir_gerente)):
    if dados.modelo not in ("comissao", "aluguel_cadeira"):
        raise HTTPException(422, "Modelo deve ser comissao ou aluguel_cadeira")
    with get_db() as db:
        bid = db.insert(
            """INSERT INTO barbeiros (tenant_id, nome, telefone, modelo, percentual_comissao, valor_aluguel, hora_inicio, hora_fim)
               VALUES (?,?,?,?,?,?,?,?)""",
            (usuario["tenant_id"], dados.nome, dados.telefone, dados.modelo,
             dados.percentual_comissao, dados.valor_aluguel, dados.hora_inicio, dados.hora_fim))
        return {"id": bid}


@router.put("/{barbeiro_id}")
def atualizar(barbeiro_id: int, dados: BarbeiroIn, usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        if not row(db.execute("SELECT id FROM barbeiros WHERE id=? AND tenant_id=?",
                              (barbeiro_id, usuario["tenant_id"]))):
            raise HTTPException(404, "Barbeiro não encontrado")
        db.execute(
            """UPDATE barbeiros SET nome=?, telefone=?, modelo=?, percentual_comissao=?, valor_aluguel=?, hora_inicio=?, hora_fim=?
               WHERE id=? AND tenant_id=?""",
            (dados.nome, dados.telefone, dados.modelo, dados.percentual_comissao,
             dados.valor_aluguel, dados.hora_inicio, dados.hora_fim, barbeiro_id, usuario["tenant_id"]))
    return {"mensagem": "Barbeiro atualizado"}


@router.delete("/{barbeiro_id}")
def desativar(barbeiro_id: int, usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        db.execute("UPDATE barbeiros SET ativo=0 WHERE id=? AND tenant_id=?",
                   (barbeiro_id, usuario["tenant_id"]))
        auditar(db, usuario["tenant_id"], usuario["uid"], "barbeiro_desativado", "barbeiro", barbeiro_id)
    return {"mensagem": "Barbeiro desativado"}


# ---------- bloqueios (ausências, folgas, imprevistos) ----------

@router.get("/{barbeiro_id}/bloqueios")
def listar_bloqueios(barbeiro_id: int, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return rows(db.execute(
            "SELECT * FROM barber_blocks WHERE barbeiro_id=? AND tenant_id=? ORDER BY inicio DESC LIMIT 50",
            (barbeiro_id, usuario["tenant_id"])))


@router.post("/{barbeiro_id}/bloqueios")
def criar_bloqueio(barbeiro_id: int, dados: BloqueioIn, usuario: dict = Depends(contexto_tenant)):
    if dados.fim <= dados.inicio:
        raise HTTPException(422, "Fim deve ser depois do início")
    with get_db() as db:
        if not row(db.execute("SELECT id FROM barbeiros WHERE id=? AND tenant_id=?",
                              (barbeiro_id, usuario["tenant_id"]))):
            raise HTTPException(404, "Barbeiro não encontrado")
        bid = db.insert(
            "INSERT INTO barber_blocks (tenant_id, barbeiro_id, inicio, fim, motivo) VALUES (?,?,?,?,?)",
            (usuario["tenant_id"], barbeiro_id, dados.inicio, dados.fim, dados.motivo))
        return {"id": bid}


@router.delete("/bloqueios/{bloqueio_id}")
def remover_bloqueio(bloqueio_id: int, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        db.execute("DELETE FROM barber_blocks WHERE id=? AND tenant_id=?",
                   (bloqueio_id, usuario["tenant_id"]))
    return {"mensagem": "Bloqueio removido"}


# ---------- cadeiras e contratos de aluguel ----------

@router.get("/cadeiras/todas")
def listar_cadeiras(usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        cadeiras = rows(db.execute(
            "SELECT * FROM chairs WHERE tenant_id=? AND ativo=1 ORDER BY nome", (usuario["tenant_id"],)))
        for c in cadeiras:
            c["contrato"] = row(db.execute(
                """SELECT cc.*, b.nome barbeiro FROM chair_contracts cc JOIN barbeiros b ON b.id=cc.barbeiro_id
                   WHERE cc.chair_id=? AND cc.ativo=1 ORDER BY cc.id DESC LIMIT 1""", (c["id"],)))
    return cadeiras


@router.post("/cadeiras")
def criar_cadeira(dados: CadeiraIn, usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        cid = db.insert("INSERT INTO chairs (tenant_id, nome) VALUES (?,?)",
                        (usuario["tenant_id"], dados.nome))
        return {"id": cid}


@router.post("/cadeiras/contratos")
def criar_contrato(dados: ContratoIn, usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        cadeira = row(db.execute("SELECT id FROM chairs WHERE id=? AND tenant_id=? AND ativo=1",
                                 (dados.chair_id, usuario["tenant_id"])))
        barbeiro = row(db.execute("SELECT id FROM barbeiros WHERE id=? AND tenant_id=? AND ativo=1",
                                  (dados.barbeiro_id, usuario["tenant_id"])))
        if not cadeira or not barbeiro:
            raise HTTPException(404, "Cadeira ou barbeiro não encontrado")
        vigente = row(db.execute("SELECT id FROM chair_contracts WHERE chair_id=? AND ativo=1",
                                 (dados.chair_id,)))
        if vigente:
            raise HTTPException(409, "Cadeira já tem contrato vigente — encerre-o primeiro")
        contrato_id = db.insert(
            "INSERT INTO chair_contracts (tenant_id, chair_id, barbeiro_id, valor_mensal, inicio) VALUES (?,?,?,?,?)",
            (usuario["tenant_id"], dados.chair_id, dados.barbeiro_id, dados.valor_mensal, dados.inicio))
        auditar(db, usuario["tenant_id"], usuario["uid"], "contrato_cadeira_criado",
                "contrato", contrato_id, f"valor={dados.valor_mensal:.2f}")
        return {"id": contrato_id}


@router.delete("/cadeiras/contratos/{contrato_id}")
def encerrar_contrato(contrato_id: int, fim: str, usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        c = row(db.execute("SELECT id FROM chair_contracts WHERE id=? AND tenant_id=? AND ativo=1",
                           (contrato_id, usuario["tenant_id"])))
        if not c:
            raise HTTPException(404, "Contrato não encontrado")
        db.execute("UPDATE chair_contracts SET ativo=0, fim=? WHERE id=?", (fim, contrato_id))
        auditar(db, usuario["tenant_id"], usuario["uid"], "contrato_cadeira_encerrado",
                "contrato", contrato_id)
    return {"mensagem": "Contrato encerrado"}


@router.post("/{barbeiro_id}/cobrar-aluguel")
def cobrar_aluguel(barbeiro_id: int, competencia: str, usuario: dict = Depends(exigir_gerente)):
    """Lança a receita mensal do aluguel (contrato vigente ou valor do cadastro)."""
    with get_db() as db:
        b = row(db.execute("SELECT * FROM barbeiros WHERE id=? AND tenant_id=?",
                           (barbeiro_id, usuario["tenant_id"])))
        if not b:
            raise HTTPException(404, "Barbeiro não encontrado")
        contrato = row(db.execute(
            "SELECT valor_mensal FROM chair_contracts WHERE barbeiro_id=? AND ativo=1 ORDER BY id DESC LIMIT 1",
            (barbeiro_id,)))
        valor = contrato["valor_mensal"] if contrato else b["valor_aluguel"]
        if b["modelo"] != "aluguel_cadeira" or valor <= 0:
            raise HTTPException(422, "Barbeiro não está no modelo de aluguel de cadeira")
        descricao = f"Aluguel de cadeira {competencia} — {b['nome']}"
        if row(db.execute("SELECT id FROM lancamentos_caixa WHERE tenant_id=? AND descricao=?",
                          (usuario["tenant_id"], descricao))):
            raise HTTPException(409, "Aluguel dessa competência já lançado")
        db.execute(
            "INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor) VALUES (?,?,?,?,?,?)",
            (usuario["tenant_id"], f"{competencia}-01", "entrada", "aluguel_cadeira", descricao, valor))
        auditar(db, usuario["tenant_id"], usuario["uid"], "aluguel_cobrado", "barbeiro", barbeiro_id,
                f"{competencia} valor={valor:.2f}")
    return {"mensagem": descricao, "valor": valor}
