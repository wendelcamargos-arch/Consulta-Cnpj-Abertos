"""Financeiro: pagamentos (simples/dividido/parcial/estorno), comissão, aluguel,
sessão de caixa com divergência e DRE."""
from tests.conftest import cab, nova_barbearia


def _atendido(client, b, hora="10:00", dia="2027-06-15"):
    ag = client.post("/api/agendamentos", headers=cab(b["gerente"]), json={
        "cliente_id": b["cliente"], "barbeiro_id": b["barbeiro"],
        "inicio": f"{dia}T{hora}", "servico_ids": [b["corte"]]}).json()
    client.patch(f"/api/agendamentos/{ag['id']}/status?status=atendido", headers=cab(b["gerente"]))
    return ag


def test_pagamento_simples_com_comissao(client, admin):
    b = nova_barbearia(client, admin)
    ag = _atendido(client, b)
    r = client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(b["gerente"]),
                    json={"pagamentos": [{"forma": "pix"}]}).json()
    assert r["status"] == "pago" and r["recebido"] == 50.0
    assert r["comissao_barbeiro"] == 25.0        # 50% de 50
    caixa = client.get("/api/caixa", headers=cab(b["gerente"])).json()
    cats = {(lanc["tipo"], lanc["categoria"]) for lanc in caixa["lancamentos"]}
    assert ("entrada", "servico") in cats and ("saida", "comissao") in cats


def test_pagamento_dividido(client, admin):
    b = nova_barbearia(client, admin)
    ag = _atendido(client, b)
    r = client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(b["gerente"]),
                    json={"pagamentos": [{"forma": "dinheiro", "valor": 20},
                                          {"forma": "pix"}]}).json()   # pix pega o restante
    assert r["status"] == "pago" and r["recebido"] == 50.0
    pagamentos = client.get(f"/api/agendamentos/{ag['id']}/pagamentos",
                            headers=cab(b["gerente"])).json()
    assert sorted((p["forma"], p["valor"]) for p in pagamentos) == [("dinheiro", 20.0), ("pix", 30.0)]


def test_pagamento_parcial_depois_quitacao(client, admin):
    b = nova_barbearia(client, admin)
    ag = _atendido(client, b)
    r1 = client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(b["gerente"]),
                     json={"pagamentos": [{"forma": "dinheiro", "valor": 30}]}).json()
    assert r1["status"] == "pago_parcial" and r1["saldo_restante"] == 20.0
    # sem comissão enquanto não quitar
    assert r1["comissao_barbeiro"] == 0
    r2 = client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(b["gerente"]),
                     json={"pagamentos": [{"forma": "pix", "valor": 20}]}).json()
    assert r2["status"] == "pago" and r2["saldo_restante"] == 0.0
    assert r2["comissao_barbeiro"] == 25.0
    # pagar acima do devido é recusado
    ag2 = _atendido(client, b, hora="11:00")
    r3 = client.post(f"/api/agendamentos/{ag2['id']}/fechar", headers=cab(b["gerente"]),
                     json={"pagamentos": [{"forma": "pix", "valor": 999}]})
    assert r3.status_code == 422


def test_estorno(client, admin):
    b = nova_barbearia(client, admin)
    ag = _atendido(client, b)
    client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(b["gerente"]),
                json={"pagamentos": [{"forma": "pix"}]})
    pagamento = client.get(f"/api/agendamentos/{ag['id']}/pagamentos",
                           headers=cab(b["gerente"])).json()[0]
    r = client.post(f"/api/agendamentos/{ag['id']}/estorno?payment_id={pagamento['id']}",
                    headers=cab(b["gerente"])).json()
    assert r["valor"] == 50.0
    # estorno duplicado recusado
    r2 = client.post(f"/api/agendamentos/{ag['id']}/estorno?payment_id={pagamento['id']}",
                     headers=cab(b["gerente"]))
    assert r2.status_code == 422
    caixa = client.get("/api/caixa", headers=cab(b["gerente"])).json()
    assert any(lanc["categoria"] == "estorno" for lanc in caixa["lancamentos"])


def test_aluguel_de_cadeira_com_contrato(client, admin):
    b = nova_barbearia(client, admin)
    locatario = client.post("/api/barbeiros", headers=cab(b["gerente"]), json={
        "nome": "Locatário", "modelo": "aluguel_cadeira", "valor_aluguel": 900,
        "percentual_comissao": 0}).json()["id"]
    cadeira = client.post("/api/barbeiros/cadeiras", headers=cab(b["gerente"]),
                          json={"nome": "Cadeira 1"}).json()["id"]
    r = client.post("/api/barbeiros/cadeiras/contratos", headers=cab(b["gerente"]), json={
        "chair_id": cadeira, "barbeiro_id": locatario, "valor_mensal": 1100,
        "inicio": "2027-01-01"})
    assert r.status_code == 200
    # cadeira ocupada não aceita segundo contrato
    r2 = client.post("/api/barbeiros/cadeiras/contratos", headers=cab(b["gerente"]), json={
        "chair_id": cadeira, "barbeiro_id": locatario, "valor_mensal": 1200,
        "inicio": "2027-02-01"})
    assert r2.status_code == 409
    # cobrança usa o valor do contrato vigente e não duplica competência
    cobranca = client.post(f"/api/barbeiros/{locatario}/cobrar-aluguel?competencia=2027-03",
                           headers=cab(b["gerente"])).json()
    assert cobranca["valor"] == 1100
    dup = client.post(f"/api/barbeiros/{locatario}/cobrar-aluguel?competencia=2027-03",
                      headers=cab(b["gerente"]))
    assert dup.status_code == 409


def test_sessao_de_caixa_com_divergencia(client, admin):
    b = nova_barbearia(client, admin)
    assert client.post("/api/caixa/sessao/abrir", headers=cab(b["gerente"]),
                       json={"valor_inicial": 100}).status_code == 200
    # segunda abertura recusada
    assert client.post("/api/caixa/sessao/abrir", headers=cab(b["gerente"]),
                       json={"valor_inicial": 0}).status_code == 409
    client.post("/api/caixa/sessao/reforco", headers=cab(b["gerente"]),
                json={"valor": 50, "descricao": "troco"})
    client.post("/api/caixa/sessao/sangria", headers=cab(b["gerente"]),
                json={"valor": 30, "descricao": "malote"})
    # recebimento em dinheiro dentro da sessão
    ag = _atendido(client, b)
    client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(b["gerente"]),
                json={"pagamentos": [{"forma": "dinheiro"}]})
    # esperado: 100 + 50 - 30 + 50 = 170; contado 165 → divergência -5
    r = client.post("/api/caixa/sessao/fechar", headers=cab(b["gerente"]),
                    json={"valor_contado": 165}).json()
    assert r["valor_esperado_dinheiro"] == 170.0
    assert r["divergencia"] == -5.0
    sessoes = client.get("/api/caixa/sessoes", headers=cab(b["gerente"])).json()
    assert sessoes[0]["status"] == "fechada" and sessoes[0]["divergencia"] == -5.0


def test_dre_completo(client, admin):
    b = nova_barbearia(client, admin)
    ag = _atendido(client, b)
    client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(b["gerente"]),
                json={"pagamentos": [{"forma": "pix"}], "desconto": 10})
    hoje = client.get("/api/caixa", headers=cab(b["gerente"])).json()["periodo"]["fim"]
    client.post("/api/caixa", headers=cab(b["gerente"]), json={
        "data": hoje, "tipo": "saida", "categoria": "despesa_fixa",
        "descricao": "Aluguel do ponto", "valor": 15})
    client.post("/api/caixa", headers=cab(b["gerente"]), json={
        "data": hoje, "tipo": "saida", "categoria": "imposto",
        "descricao": "Simples Nacional", "valor": 4})
    dre = client.get("/api/relatorios/dre", headers=cab(b["gerente"])).json()
    # serviço 50-10=40 recebido; desconto 10; comissão 50% de 40 = 20
    assert dre["receita_bruta"] == 40.0
    assert dre["descontos"] == 10.0
    assert dre["impostos"] == 4.0
    assert dre["comissoes"] == 20.0
    assert dre["despesas_fixas"] == 15.0
    assert dre["lucro_liquido"] == 40.0 - 10 - 4 - 20 - 15
    # KPIs seguem a competência do agendamento (2027-06 no cenário deste teste)
    kpis = client.get("/api/relatorios/indicadores?competencia=2027-06",
                      headers=cab(b["gerente"])).json()
    assert kpis["faturamento"] == 40.0
    assert kpis["agendamentos"] == 1
