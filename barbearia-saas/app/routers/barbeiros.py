"""Gestão de barbeiros e modelo de aluguel de cadeiras.

Dois modelos de remuneração por barbeiro:
  comissao        — a barbearia fica com (100 - percentual_comissao)% de cada serviço
  aluguel_cadeira — o barbeiro paga valor fixo mensal e fica com 100% dos serviços
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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
        cur = db.execute(
            """INSERT INTO barbeiros (tenant_id, nome, telefone, modelo, percentual_comissao, valor_aluguel, hora_inicio, hora_fim)
               VALUES (?,?,?,?,?,?,?,?)""",
            (usuario["tenant_id"], dados.nome, dados.telefone, dados.modelo,
             dados.percentual_comissao, dados.valor_aluguel, dados.hora_inicio, dados.hora_fim))
        return {"id": cur.lastrowid}


@router.put("/{barbeiro_id}")
def atualizar(barbeiro_id: int, dados: BarbeiroIn, usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        if not row(db.execute("SELECT id FROM barbeiros WHERE id=? AND tenant_id=?", (barbeiro_id, usuario["tenant_id"]))):
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
        db.execute("UPDATE barbeiros SET ativo=0 WHERE id=? AND tenant_id=?", (barbeiro_id, usuario["tenant_id"]))
    return {"mensagem": "Barbeiro desativado"}


@router.post("/{barbeiro_id}/cobrar-aluguel")
def cobrar_aluguel(barbeiro_id: int, competencia: str, usuario: dict = Depends(exigir_gerente)):
    """Lança no caixa a receita do aluguel da cadeira do mês (competencia = YYYY-MM)."""
    with get_db() as db:
        b = row(db.execute("SELECT * FROM barbeiros WHERE id=? AND tenant_id=?", (barbeiro_id, usuario["tenant_id"])))
        if not b:
            raise HTTPException(404, "Barbeiro não encontrado")
        if b["modelo"] != "aluguel_cadeira" or b["valor_aluguel"] <= 0:
            raise HTTPException(422, "Barbeiro não está no modelo de aluguel de cadeira")
        descricao = f"Aluguel de cadeira {competencia} — {b['nome']}"
        if row(db.execute(
                "SELECT id FROM lancamentos_caixa WHERE tenant_id=? AND descricao=?",
                (usuario["tenant_id"], descricao))):
            raise HTTPException(409, "Aluguel dessa competência já lançado")
        db.execute(
            "INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor) VALUES (?,?,?,?,?,?)",
            (usuario["tenant_id"], f"{competencia}-01", "entrada", "aluguel_cadeira", descricao, b["valor_aluguel"]))
    return {"mensagem": descricao, "valor": b["valor_aluguel"]}
