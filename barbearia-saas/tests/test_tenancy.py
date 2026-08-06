"""Isolamento multi-tenant: leitura, escrita, exclusão cruzada e suspensão."""
from tests.conftest import cab, nova_barbearia


def test_tenant_nao_le_dados_do_outro(client, admin):
    a = nova_barbearia(client, admin)
    b = nova_barbearia(client, admin)
    clientes_b = client.get("/api/clientes", headers=cab(b["gerente"])).json()
    assert {c["id"] for c in clientes_b} == {b["cliente"]}
    assert a["cliente"] not in {c["id"] for c in clientes_b}
    # histórico direto por id de outro tenant → 404
    assert client.get(f"/api/clientes/{a['cliente']}/historico",
                      headers=cab(b["gerente"])).status_code == 404


def test_tenant_nao_altera_nem_usa_recursos_do_outro(client, admin):
    a = nova_barbearia(client, admin)
    b = nova_barbearia(client, admin)
    # alterar cliente do outro → 404
    r = client.put(f"/api/clientes/{a['cliente']}", headers=cab(b["gerente"]),
                   json={"nome": "Invadido", "telefone": "34999000009"})
    assert r.status_code == 404
    # agendar usando barbeiro/serviço do outro → 404/422
    r = client.post("/api/agendamentos", headers=cab(b["gerente"]), json={
        "cliente_id": b["cliente"], "barbeiro_id": a["barbeiro"],
        "inicio": "2027-03-10T10:00", "servico_ids": [b["corte"]]})
    assert r.status_code == 404
    r = client.post("/api/agendamentos", headers=cab(b["gerente"]), json={
        "cliente_id": b["cliente"], "barbeiro_id": b["barbeiro"],
        "inicio": "2027-03-10T10:00", "servico_ids": [a["corte"]]})
    assert r.status_code == 422


def test_tenant_nao_exclui_recursos_do_outro(client, admin):
    a = nova_barbearia(client, admin)
    b = nova_barbearia(client, admin)
    client.delete(f"/api/barbeiros/{a['barbeiro']}", headers=cab(b["gerente"]))
    ainda_la = client.get("/api/barbeiros", headers=cab(a["gerente"])).json()
    assert a["barbeiro"] in {x["id"] for x in ainda_la}


def test_suspensao_do_tenant_bloqueia_acesso(client, admin):
    b = nova_barbearia(client, admin)
    assert client.patch(f"/api/tenants/{b['tenant_id']}/ativo",
                        headers=cab(admin)).json()["ativo"] == 0
    # sessão existente para de funcionar
    assert client.get("/api/clientes", headers=cab(b["gerente"])).status_code == 403
    # novo login barrado
    r = client.post("/api/auth/login", json={
        "email": f"gerente@{b['slug']}.com", "senha": "senha-gerente-123"})
    assert r.status_code == 403
    # reativação restaura
    client.patch(f"/api/tenants/{b['tenant_id']}/ativo", headers=cab(admin))
    assert client.get("/api/clientes", headers=cab(b["gerente"])).status_code == 200


def test_superadmin_opera_tenant_via_header(client, admin):
    b = nova_barbearia(client, admin)
    r = client.get("/api/clientes", headers=cab(admin, {"X-Tenant-Id": str(b["tenant_id"])}))
    assert r.status_code == 200
    assert {c["id"] for c in r.json()} == {b["cliente"]}
