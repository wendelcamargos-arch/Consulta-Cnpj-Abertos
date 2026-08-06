"""Estoque: entrada, venda, consumo, ajuste, perda, mínimo e custo médio móvel."""
from tests.conftest import cab, nova_barbearia


def _produto(client, b, custo=10, venda=30, minimo=2):
    return client.post("/api/estoque", headers=cab(b["gerente"]), json={
        "nome": "Pomada", "custo": custo, "preco_venda": venda,
        "estoque_minimo": minimo}).json()["id"]


def test_compra_venda_consumo_ajuste_perda(client, admin):
    b = nova_barbearia(client, admin)
    pid = _produto(client, b)
    g = cab(b["gerente"])
    assert client.post(f"/api/estoque/{pid}/movimento", headers=g,
                       json={"tipo": "compra", "quantidade": 10, "valor_unitario": 10}).status_code == 200
    assert client.post(f"/api/estoque/{pid}/movimento", headers=g,
                       json={"tipo": "consumo", "quantidade": 2}).status_code == 200
    assert client.post(f"/api/estoque/{pid}/movimento", headers=g,
                       json={"tipo": "perda", "quantidade": 1}).status_code == 200
    assert client.post(f"/api/estoque/{pid}/movimento", headers=g,
                       json={"tipo": "ajuste", "quantidade": 1}).status_code == 200
    # venda pelo fechamento de atendimento
    ag = client.post("/api/agendamentos", headers=g, json={
        "cliente_id": b["cliente"], "barbeiro_id": b["barbeiro"],
        "inicio": "2027-06-15T10:00", "servico_ids": [b["corte"]]}).json()
    client.patch(f"/api/agendamentos/{ag['id']}/status?status=atendido", headers=g)
    client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=g,
                json={"pagamentos": [{"forma": "pix"}], "produto_ids": [pid]})
    produto = client.get("/api/estoque", headers=g).json()[0]
    assert produto["quantidade"] == 7        # 10 -2 -1 +1 -1(venda)
    movimentos = client.get(f"/api/estoque/{pid}/movimentos", headers=g).json()
    assert {m["tipo"] for m in movimentos} == {"compra", "consumo", "perda", "ajuste", "venda"}
    # perda gera CMV no caixa
    caixa = client.get("/api/caixa", headers=g).json()
    assert any(lanc["categoria"] == "cmv" and "Perda" in lanc["descricao"] for lanc in caixa["lancamentos"])


def test_estoque_insuficiente_e_minimo(client, admin):
    b = nova_barbearia(client, admin)
    pid = _produto(client, b, minimo=5)
    g = cab(b["gerente"])
    r = client.post(f"/api/estoque/{pid}/movimento", headers=g,
                    json={"tipo": "consumo", "quantidade": 1})
    assert r.status_code == 409              # nada em estoque
    client.post(f"/api/estoque/{pid}/movimento", headers=g,
                json={"tipo": "compra", "quantidade": 3, "valor_unitario": 10})
    produto = client.get("/api/estoque", headers=g).json()[0]
    assert produto["abaixo_minimo"] is True  # 3 <= 5


def test_custo_medio_movel(client, admin):
    b = nova_barbearia(client, admin)
    pid = _produto(client, b, custo=10)
    g = cab(b["gerente"])
    client.post(f"/api/estoque/{pid}/movimento", headers=g,
                json={"tipo": "compra", "quantidade": 10, "valor_unitario": 10})
    r = client.post(f"/api/estoque/{pid}/movimento", headers=g,
                    json={"tipo": "compra", "quantidade": 10, "valor_unitario": 20}).json()
    assert r["custo_medio"] == 15.0          # (10*10 + 10*20) / 20
    movs = client.get(f"/api/estoque/{pid}/movimentos", headers=g).json()
    ultima_compra = [m for m in movs if m["tipo"] == "compra"][0]
    assert ultima_compra["custo_unitario"] == 15.0
