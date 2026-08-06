"""Fluxo de caixa: entradas, saídas e saldo por período."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import contexto_tenant
from ..db import get_db, row, rows

router = APIRouter(prefix="/api/caixa", tags=["caixa"])

CATEGORIAS = ("servico", "produto", "aluguel_cadeira", "comissao",
              "despesa_fixa", "despesa_variavel", "imposto", "outro")


class LancamentoIn(BaseModel):
    data: str
    tipo: str        # entrada | saida
    categoria: str
    descricao: str
    valor: float


@router.get("")
def listar(inicio: str = "", fim: str = "", usuario: dict = Depends(contexto_tenant)):
    inicio = inicio or date.today().replace(day=1).isoformat()
    fim = fim or date.today().isoformat()
    with get_db() as db:
        lancamentos = rows(db.execute(
            """SELECT * FROM lancamentos_caixa WHERE tenant_id=? AND data BETWEEN ? AND ?
               ORDER BY data DESC, id DESC""", (usuario["tenant_id"], inicio, fim)))
        totais = row(db.execute(
            """SELECT COALESCE(SUM(CASE WHEN tipo='entrada' THEN valor END),0) entradas,
                      COALESCE(SUM(CASE WHEN tipo='saida' THEN valor END),0) saidas
               FROM lancamentos_caixa WHERE tenant_id=? AND data BETWEEN ? AND ?""",
            (usuario["tenant_id"], inicio, fim)))
    return {"periodo": {"inicio": inicio, "fim": fim}, "lancamentos": lancamentos,
            "entradas": totais["entradas"], "saidas": totais["saidas"],
            "saldo": round(totais["entradas"] - totais["saidas"], 2)}


@router.post("")
def lancar(dados: LancamentoIn, usuario: dict = Depends(contexto_tenant)):
    if dados.tipo not in ("entrada", "saida"):
        raise HTTPException(422, "Tipo deve ser entrada ou saida")
    if dados.categoria not in CATEGORIAS:
        raise HTTPException(422, f"Categoria deve ser uma de: {', '.join(CATEGORIAS)}")
    if dados.valor <= 0:
        raise HTTPException(422, "Valor deve ser positivo")
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor) VALUES (?,?,?,?,?,?)",
            (usuario["tenant_id"], dados.data, dados.tipo, dados.categoria, dados.descricao, dados.valor))
        return {"id": cur.lastrowid}


@router.delete("/{lanc_id}")
def excluir(lanc_id: int, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        l = row(db.execute("SELECT agendamento_id FROM lancamentos_caixa WHERE id=? AND tenant_id=?",
                           (lanc_id, usuario["tenant_id"])))
        if not l:
            raise HTTPException(404, "Lançamento não encontrado")
        if l["agendamento_id"]:
            raise HTTPException(422, "Lançamento gerado por fechamento de atendimento não pode ser excluído manualmente")
        db.execute("DELETE FROM lancamentos_caixa WHERE id=?", (lanc_id,))
    return {"mensagem": "Lançamento excluído"}
