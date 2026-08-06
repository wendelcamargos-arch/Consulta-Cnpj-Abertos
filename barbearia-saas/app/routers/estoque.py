"""Estoque: produtos de venda e consumo interno, com alerta de mínimo."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import contexto_tenant, exigir_gerente
from ..db import get_db, row, rows

router = APIRouter(prefix="/api/estoque", tags=["estoque"])


class ProdutoIn(BaseModel):
    nome: str
    custo: float = 0
    preco_venda: float = 0
    estoque_minimo: float = 0


class MovimentoIn(BaseModel):
    tipo: str          # compra | consumo | ajuste
    quantidade: float  # sempre positiva; o sinal vem do tipo
    valor_unitario: float = 0
    lancar_no_caixa: bool = True


@router.get("")
def listar(usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        lista = rows(db.execute(
            "SELECT * FROM produtos WHERE tenant_id=? AND ativo=1 ORDER BY nome", (usuario["tenant_id"],)))
    for p in lista:
        p["abaixo_minimo"] = p["quantidade"] <= p["estoque_minimo"]
    return lista


@router.post("")
def criar(dados: ProdutoIn, usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO produtos (tenant_id, nome, custo, preco_venda, estoque_minimo) VALUES (?,?,?,?,?)",
            (usuario["tenant_id"], dados.nome, dados.custo, dados.preco_venda, dados.estoque_minimo))
        return {"id": cur.lastrowid}


@router.post("/{produto_id}/movimento")
def movimentar(produto_id: int, dados: MovimentoIn, usuario: dict = Depends(contexto_tenant)):
    if dados.tipo not in ("compra", "consumo", "ajuste"):
        raise HTTPException(422, "Tipo deve ser compra, consumo ou ajuste")
    if dados.quantidade <= 0 and dados.tipo != "ajuste":
        raise HTTPException(422, "Quantidade deve ser positiva")
    with get_db() as db:
        p = row(db.execute("SELECT * FROM produtos WHERE id=? AND tenant_id=? AND ativo=1",
                           (produto_id, usuario["tenant_id"])))
        if not p:
            raise HTTPException(404, "Produto não encontrado")
        delta = dados.quantidade if dados.tipo in ("compra", "ajuste") else -dados.quantidade
        if p["quantidade"] + delta < 0:
            raise HTTPException(409, f"Estoque insuficiente de {p['nome']}")
        db.execute("UPDATE produtos SET quantidade = quantidade + ? WHERE id=?", (delta, produto_id))
        db.execute(
            "INSERT INTO movimentos_estoque (tenant_id, produto_id, tipo, quantidade, valor_unitario) VALUES (?,?,?,?,?)",
            (usuario["tenant_id"], produto_id, dados.tipo, delta, dados.valor_unitario or p["custo"]))
        if dados.tipo == "compra" and dados.lancar_no_caixa:
            custo_total = round((dados.valor_unitario or p["custo"]) * dados.quantidade, 2)
            if custo_total > 0:
                db.execute(
                    "INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor) VALUES (?, date('now'), 'saida', 'despesa_variavel', ?, ?)",
                    (usuario["tenant_id"], f"Compra estoque: {dados.quantidade:g}x {p['nome']}", custo_total))
    return {"mensagem": f"Movimento registrado ({delta:+g} {p['nome']})"}


@router.get("/{produto_id}/movimentos")
def movimentos(produto_id: int, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return rows(db.execute(
            """SELECT m.* FROM movimentos_estoque m JOIN produtos p ON p.id=m.produto_id
               WHERE m.produto_id=? AND p.tenant_id=? ORDER BY m.data DESC LIMIT 100""",
            (produto_id, usuario["tenant_id"])))
