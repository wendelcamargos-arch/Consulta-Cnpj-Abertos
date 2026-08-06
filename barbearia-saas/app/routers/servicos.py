"""Tabela de serviços e combos (combo = pacote de serviços com preço fechado)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import contexto_tenant, exigir_gerente
from ..db import get_db, row, rows

router = APIRouter(prefix="/api/servicos", tags=["servicos"])


class ServicoIn(BaseModel):
    nome: str
    preco: float
    duracao_min: int = 30


class ComboIn(BaseModel):
    nome: str
    preco: float                 # preço do pacote (normalmente < soma dos itens)
    servico_ids: list[int]


@router.get("")
def listar(usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        lista = rows(db.execute(
            "SELECT * FROM servicos WHERE tenant_id=? AND ativo=1 ORDER BY eh_combo, nome", (usuario["tenant_id"],)))
        for s in lista:
            if s["eh_combo"]:
                s["itens"] = rows(db.execute(
                    """SELECT sv.id, sv.nome, sv.preco FROM combo_itens ci
                       JOIN servicos sv ON sv.id = ci.servico_id WHERE ci.combo_id=?""", (s["id"],)))
    return lista


@router.post("")
def criar(dados: ServicoIn, usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        sid = db.insert(
            "INSERT INTO servicos (tenant_id, nome, preco, duracao_min) VALUES (?,?,?,?)",
            (usuario["tenant_id"], dados.nome, dados.preco, dados.duracao_min))
        return {"id": sid}


@router.post("/combo")
def criar_combo(dados: ComboIn, usuario: dict = Depends(exigir_gerente)):
    if len(dados.servico_ids) < 2:
        raise HTTPException(422, "Um combo precisa de pelo menos 2 serviços")
    with get_db() as db:
        marcadores = ",".join("?" * len(dados.servico_ids))
        itens = rows(db.execute(
            f"SELECT id, duracao_min FROM servicos WHERE tenant_id=? AND eh_combo=0 AND ativo=1 AND id IN ({marcadores})",
            (usuario["tenant_id"], *dados.servico_ids)))
        if len(itens) != len(set(dados.servico_ids)):
            raise HTTPException(422, "Combo só pode conter serviços simples ativos da própria barbearia")
        duracao = sum(i["duracao_min"] for i in itens)
        combo_id = db.insert(
            "INSERT INTO servicos (tenant_id, nome, preco, duracao_min, eh_combo) VALUES (?,?,?,?,1)",
            (usuario["tenant_id"], dados.nome, dados.preco, duracao))
        for i in itens:
            db.execute("INSERT INTO combo_itens (combo_id, servico_id) VALUES (?,?)", (combo_id, i["id"]))
        return {"id": combo_id, "duracao_min": duracao}


@router.put("/{servico_id}")
def atualizar(servico_id: int, dados: ServicoIn, usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        if not row(db.execute("SELECT id FROM servicos WHERE id=? AND tenant_id=?", (servico_id, usuario["tenant_id"]))):
            raise HTTPException(404, "Serviço não encontrado")
        db.execute("UPDATE servicos SET nome=?, preco=?, duracao_min=? WHERE id=? AND tenant_id=?",
                   (dados.nome, dados.preco, dados.duracao_min, servico_id, usuario["tenant_id"]))
    return {"mensagem": "Serviço atualizado"}


@router.delete("/{servico_id}")
def desativar(servico_id: int, usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        db.execute("UPDATE servicos SET ativo=0 WHERE id=? AND tenant_id=?", (servico_id, usuario["tenant_id"]))
    return {"mensagem": "Serviço desativado"}
