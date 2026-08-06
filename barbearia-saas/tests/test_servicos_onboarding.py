"""Serviços/combos e onboarding completo da barbearia."""
from tests.conftest import cab, nova_barbearia


def test_combo_criacao_listagem_e_regras(client, admin):
    b = nova_barbearia(client, admin)
    g = cab(b["gerente"])
    barba = client.post("/api/servicos", headers=g,
                        json={"nome": "Barba", "preco": 30, "duracao_min": 30}).json()["id"]
    combo = client.post("/api/servicos/combo", headers=g, json={
        "nome": "Combo", "preco": 70, "servico_ids": [b["corte"], barba]})
    assert combo.status_code == 200
    assert combo.json()["duracao_min"] == 60          # soma dos itens
    # combo precisa de >= 2 serviços simples do próprio tenant
    assert client.post("/api/servicos/combo", headers=g, json={
        "nome": "X", "preco": 10, "servico_ids": [b["corte"]]}).status_code == 422
    assert client.post("/api/servicos/combo", headers=g, json={
        "nome": "X", "preco": 10, "servico_ids": [b["corte"], 999999]}).status_code == 422

    lista = client.get("/api/servicos", headers=g).json()
    combo_listado = next(s for s in lista if s["eh_combo"])
    assert {i["nome"] for i in combo_listado["itens"]} == {"Corte", "Barba"}

    # atualização e desativação
    assert client.put(f"/api/servicos/{barba}", headers=g,
                      json={"nome": "Barba Premium", "preco": 40, "duracao_min": 30}).status_code == 200
    assert client.put("/api/servicos/999999", headers=g,
                      json={"nome": "X", "preco": 1, "duracao_min": 10}).status_code == 404
    assert client.delete(f"/api/servicos/{barba}", headers=g).status_code == 200
    ativos = client.get("/api/servicos", headers=g).json()
    assert barba not in {s["id"] for s in ativos}


def test_onboarding_completo_e_checklist(client, admin):
    r = client.post("/api/onboarding", headers=cab(admin), json={
        "nome": "Barbearia Onboard", "slug": "onboard-x", "cnpj": "00000000000191",
        "telefone": "3433330000", "endereco": "Rua A, 100", "timezone": "America/Sao_Paulo",
        "dias_fechados": [6],
        "barbeiros": [{"nome": "B1", "modelo": "comissao", "percentual_comissao": 40},
                       {"nome": "B2", "modelo": "aluguel_cadeira", "valor_aluguel": 800}],
        "servicos": [{"nome": "Corte", "preco": 45}, {"nome": "Barba", "preco": 35}],
        "cor_primaria": "#AA8800", "telefone_whatsapp": "5534999990000",
        "confirmacao_min": 720, "lembrete_min": 60, "aviso_min": 15,
        "gerente": {"nome": "Dono", "email": "dono@onboard-x.com", "senha": "senha-dono-123"},
        "usuarios": [{"nome": "Recep", "email": "recep@onboard-x.com",
                       "senha": "senha-recep-123", "papel": "recepcao"}]})
    assert r.status_code == 200, r.text
    # slug duplicado recusado
    assert client.post("/api/onboarding", headers=cab(admin), json={
        "nome": "Outra", "slug": "onboard-x",
        "gerente": {"nome": "X", "email": "x@y.com", "senha": "12345678"}}).status_code == 409

    gerente = client.post("/api/auth/login", json={
        "email": "dono@onboard-x.com", "senha": "senha-dono-123"}).json()["token"]
    assert len(client.get("/api/barbeiros", headers=cab(gerente)).json()) == 2
    assert len(client.get("/api/servicos", headers=cab(gerente)).json()) == 2
    meu = client.get("/api/tenants/meu", headers=cab(gerente)).json()
    assert meu["settings"]["confirmacao_min"] == 720
    assert meu["settings"]["dias_fechados"] == [6]

    checklist = client.get("/api/onboarding/checklist", headers=cab(gerente)).json()
    assert checklist["barbeiros_cadastrados"] and checklist["servicos_cadastrados"]
    assert checklist["usuarios_equipe"] and not checklist["completo"]  # sem clientes/caixa ainda
