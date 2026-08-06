"""WhatsApp: fila, envio, retry/dead-letter, webhook (verificação, assinatura,
duplicidade) e interpretação de respostas."""
import hashlib
import hmac
import json

from app.db import get_db
from app.routers.whatsapp import interpretar_resposta
from tests.conftest import cab


def _msg_na_fila(tenant_id, cliente_id, telefone="34999000001", tipo="confirmacao",
                 agendada="2020-01-01T08:00", ag_id=None, status="pendente"):
    with get_db() as db:
        return db.insert(
            """INSERT INTO mensagens_whatsapp (tenant_id, cliente_id, agendamento_id, telefone, tipo, template, texto, agendada_para, status)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (tenant_id, cliente_id, ag_id, telefone, tipo, "confirmacao_agendamento",
             "Pode confirmar?", agendada, status))


def test_agendamento_enfileira_momentos_configurados(client, barbearia):
    client.patch("/api/tenants/meu/settings", headers=cab(barbearia["gerente"]),
                 json={"confirmacao_min": 1440, "lembrete_min": 120, "aviso_min": 30})
    ag = client.post("/api/agendamentos", headers=cab(barbearia["gerente"]), json={
        "cliente_id": barbearia["cliente"], "barbeiro_id": barbearia["barbeiro"],
        "inicio": "2027-09-01T10:00", "servico_ids": [barbearia["corte"]]}).json()
    fila = client.get("/api/whatsapp/fila", headers=cab(barbearia["gerente"])).json()
    minhas = [m for m in fila if m["agendamento_id"] == ag["id"]]
    assert {m["tipo"] for m in minhas} == {"confirmacao", "lembrete", "aviso_final"}
    conf = next(m for m in minhas if m["tipo"] == "confirmacao")
    assert conf["agendada_para"] == "2027-08-31T10:00"       # 24h antes
    aviso = next(m for m in minhas if m["tipo"] == "aviso_final")
    assert aviso["agendada_para"] == "2027-09-01T09:30"      # 30min antes


def test_processar_envia_e_registra_provider_id(client, barbearia, provider):
    _msg_na_fila(barbearia["tenant_id"], barbearia["cliente"])
    r = client.post("/api/whatsapp/processar", headers=cab(barbearia["gerente"])).json()
    assert r["enviadas"] >= 1
    assert provider.enviadas
    enviadas = client.get("/api/whatsapp/fila?status=enviada",
                          headers=cab(barbearia["gerente"])).json()
    assert any(m["provider_msg_id"].startswith("sim-") for m in enviadas)


def test_falha_gera_retry_e_depois_falha_final(client, barbearia, provider):
    provider.falhar = True
    _msg_na_fila(barbearia["tenant_id"], barbearia["cliente"], telefone="34999000077")
    r1 = client.post("/api/whatsapp/processar", headers=cab(barbearia["gerente"])).json()
    assert r1["erros"] >= 1
    with get_db() as db:
        m = dict(db.execute(
            "SELECT * FROM mensagens_whatsapp WHERE telefone='34999000077'").fetchone())
        assert m["status"] == "erro" and m["tentativas"] == 1 and m["proximo_retry"]
        # força o vencimento dos retries e esgota as tentativas
        for _ in range(3):
            db.execute("UPDATE mensagens_whatsapp SET proximo_retry='2020-01-01T00:00' WHERE id=?",
                       (m["id"],))
            db.commit()
            client.post("/api/whatsapp/processar", headers=cab(barbearia["gerente"]))
        final = dict(db.execute("SELECT status, tentativas FROM mensagens_whatsapp WHERE id=?",
                                (m["id"],)).fetchone())
    assert final["status"] == "falha_final"          # dead-letter
    assert final["tentativas"] == 4


def test_webhook_verificacao(client):
    r = client.get("/api/whatsapp/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "token-verificacao-teste",
        "hub.challenge": "12345"})
    assert r.status_code == 200 and r.text == "12345"
    assert client.get("/api/whatsapp/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "x"}).status_code == 403


def _payload_status(provider_id, status):
    return {"entry": [{"changes": [{"value": {"statuses": [{"id": provider_id, "status": status}]}}]}]}


def test_webhook_assinatura_invalida_rejeitada(client, monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "segredo-meta-teste")
    corpo = json.dumps(_payload_status("wamid.x", "delivered")).encode()
    ruim = client.post("/api/whatsapp/webhook", content=corpo,
                       headers={"X-Hub-Signature-256": "sha256=invalida"})
    assert ruim.status_code == 403
    assinatura = "sha256=" + hmac.new(b"segredo-meta-teste", corpo, hashlib.sha256).hexdigest()
    ok = client.post("/api/whatsapp/webhook", content=corpo,
                     headers={"X-Hub-Signature-256": assinatura})
    assert ok.status_code == 200


def test_webhook_status_atualiza_e_duplicado_ignorado(client, barbearia, provider):
    _msg_na_fila(barbearia["tenant_id"], barbearia["cliente"], telefone="34999000088")
    client.post("/api/whatsapp/processar", headers=cab(barbearia["gerente"]))
    with get_db() as db:
        pid = dict(db.execute(
            "SELECT provider_msg_id FROM mensagens_whatsapp WHERE telefone='34999000088'").fetchone())["provider_msg_id"]
    r1 = client.post("/api/whatsapp/webhook", json=_payload_status(pid, "read")).json()
    assert r1["status_atualizados"] == 1
    r2 = client.post("/api/whatsapp/webhook", json=_payload_status(pid, "read")).json()
    assert r2["duplicados"] == 1                      # idempotência por evento
    # evento 'delivered' fora de ordem não rebaixa 'lida'
    client.post("/api/whatsapp/webhook", json=_payload_status(pid, "delivered"))
    with get_db() as db:
        st = dict(db.execute("SELECT status FROM mensagens_whatsapp WHERE provider_msg_id=?",
                             (pid,)).fetchone())["status"]
    assert st == "lida"


def test_interpretacao_de_respostas():
    assert interpretar_resposta("CONFIRMAR") == "confirmar"
    assert interpretar_resposta("  confirmar ") == "confirmar"
    assert interpretar_resposta("Cancelar") == "cancelar"
    assert interpretar_resposta("vou atrasar") == "atrasar"
    assert interpretar_resposta("VOU ATRASAR ") == "atrasar"
    assert interpretar_resposta("ok pode ser") is None       # ambígua


def _payload_msg(telefone, texto, msg_id):
    return {"entry": [{"changes": [{"value": {"messages": [
        {"id": msg_id, "from": f"55{telefone}", "text": {"body": texto}}]}}]}]}


def test_webhook_resposta_confirma_cancela_atrasa_e_ambigua(client, admin, provider):
    from tests.conftest import nova_barbearia
    for i, (texto, esperado) in enumerate([("CONFIRMAR", "confirmado"),
                                           ("cancelar", "cancelado"),
                                           ("VOU ATRASAR", "atrasado")]):
        b = nova_barbearia(client, admin)
        tel = f"3499911{i:04d}"
        with get_db() as db:
            db.execute("UPDATE clientes SET telefone=? WHERE id=?", (tel, b["cliente"]))
        ag = client.post("/api/agendamentos", headers=cab(b["gerente"]), json={
            "cliente_id": b["cliente"], "barbeiro_id": b["barbeiro"],
            "inicio": "2027-09-02T10:00", "servico_ids": [b["corte"]]}).json()
        with get_db() as db:
            db.execute("""UPDATE mensagens_whatsapp SET status='enviada', agendada_para='2020-01-01T00:00'
                          WHERE agendamento_id=? AND tipo='confirmacao'""", (ag["id"],))
        r = client.post("/api/whatsapp/webhook", json=_payload_msg(tel, texto, f"wamid.resp{i}")).json()
        assert r["respostas"] == 1
        ags = client.get("/api/agendamentos?data=2027-09-02", headers=cab(b["gerente"])).json()
        assert ags[0]["status"] == esperado

    # ambígua → pendência da recepção, agendamento intacto
    b = nova_barbearia(client, admin)
    tel = "34999119999"
    with get_db() as db:
        db.execute("UPDATE clientes SET telefone=? WHERE id=?", (tel, b["cliente"]))
    ag = client.post("/api/agendamentos", headers=cab(b["gerente"]), json={
        "cliente_id": b["cliente"], "barbeiro_id": b["barbeiro"],
        "inicio": "2027-09-02T10:00", "servico_ids": [b["corte"]]}).json()
    with get_db() as db:
        db.execute("""UPDATE mensagens_whatsapp SET status='enviada'
                      WHERE agendamento_id=? AND tipo='confirmacao'""", (ag["id"],))
    client.post("/api/whatsapp/webhook", json=_payload_msg(tel, "quem fala?", "wamid.amb"))
    pendencias = client.get("/api/whatsapp/fila?pendencia=1", headers=cab(b["gerente"])).json()
    assert len(pendencias) == 1 and pendencias[0]["resposta"].startswith("ambigua")
    ags = client.get("/api/agendamentos?data=2027-09-02", headers=cab(b["gerente"])).json()
    assert ags[0]["status"] == "agendado"
