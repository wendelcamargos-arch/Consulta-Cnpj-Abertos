"""Campanha de aniversário: consentimento, 08:00, voucher único, resgate único,
intransferível, validade e 29/02."""
from datetime import date

from app.db import get_db
from app.routers.aniversario import data_aniversario_no_ano
from tests.conftest import cab, nova_barbearia


def _preparar(client, admin, aniversario_mm_dd, consentimento=True):
    b = nova_barbearia(client, admin)
    client.put(f"/api/clientes/{b['cliente']}", headers=cab(b["gerente"]), json={
        "nome": "Aniversariante", "telefone": "34999000001",
        "aniversario": aniversario_mm_dd, "consentimento_marketing": consentimento})
    return b


def test_29_fevereiro():
    assert data_aniversario_no_ano("02-29", 2025) == date(2025, 2, 28)
    assert data_aniversario_no_ano("02-29", 2024) == date(2024, 2, 29)
    assert data_aniversario_no_ano("13-99", 2025) is None      # data inválida


def test_campanha_exige_consentimento(client, admin):
    hoje = date.today()
    sem = _preparar(client, admin, f"{hoje.month:02d}-15", consentimento=False)
    r = client.post(f"/api/aniversario/gerar?mes={hoje.month}", headers=cab(sem["gerente"])).json()
    assert r["vouchers_emitidos"] == 0 and r["sem_consentimento"] == 1


def test_emissao_unica_e_mensagem_as_8h(client, admin):
    hoje = date.today()
    b = _preparar(client, admin, f"{hoje.month:02d}-15")
    r1 = client.post(f"/api/aniversario/gerar?mes={hoje.month}", headers=cab(b["gerente"])).json()
    assert r1["vouchers_emitidos"] == 1
    r2 = client.post(f"/api/aniversario/gerar?mes={hoje.month}", headers=cab(b["gerente"])).json()
    assert r2["vouchers_emitidos"] == 0 and r2["ja_emitidos"] == 1      # proteção duplicidade
    fila = client.get("/api/whatsapp/fila", headers=cab(b["gerente"])).json()
    aniver = [m for m in fila if m["tipo"] == "aniversario"]
    assert len(aniver) == 1
    assert aniver[0]["agendada_para"].endswith("T08:00")                 # hora configurada


def _fechar_com_voucher(client, b, codigo, dia="2027-06-15T10:00"):
    ag = client.post("/api/agendamentos", headers=cab(b["gerente"]), json={
        "cliente_id": b["cliente"], "barbeiro_id": b["barbeiro"],
        "inicio": dia, "servico_ids": [b["corte"]]}).json()
    client.patch(f"/api/agendamentos/{ag['id']}/status?status=atendido", headers=cab(b["gerente"]))
    return client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(b["gerente"]),
                       json={"pagamentos": [{"forma": "pix"}], "voucher_codigo": codigo})


def test_resgate_unico_validade_e_intransferibilidade(client, admin):
    hoje = date.today()
    b = _preparar(client, admin, f"{hoje.month:02d}-{hoje.day:02d}")     # aniversário HOJE
    client.post(f"/api/aniversario/gerar?mes={hoje.month}", headers=cab(b["gerente"]))
    voucher = client.get("/api/aniversario/vouchers", headers=cab(b["gerente"])).json()[0]

    # resgate válido: 10% de 50 = 5 de desconto
    r = _fechar_com_voucher(client, b, voucher["codigo"])
    assert r.status_code == 200
    assert r.json()["desconto"] == 5.0
    assert r.json()["recebido"] == 45.0

    # uso único
    r2 = _fechar_com_voucher(client, b, voucher["codigo"], dia="2027-06-16T10:00")
    assert r2.status_code == 422 and "uso único" in r2.json()["detail"]

    # intransferível: outro cliente do mesmo tenant não usa
    outro = client.post("/api/clientes", headers=cab(b["gerente"]), json={
        "nome": "Outro Cliente", "telefone": "34999000002"}).json()["id"]
    ag = client.post("/api/agendamentos", headers=cab(b["gerente"]), json={
        "cliente_id": outro, "barbeiro_id": b["barbeiro"],
        "inicio": "2027-06-17T10:00", "servico_ids": [b["corte"]]}).json()
    client.patch(f"/api/agendamentos/{ag['id']}/status?status=atendido", headers=cab(b["gerente"]))
    # voucher novo do aniversariante para testar transferência
    with get_db() as db:
        db.execute("DELETE FROM birthday_vouchers WHERE tenant_id=?", (b["tenant_id"],))
    client.post(f"/api/aniversario/gerar?mes={hoje.month}", headers=cab(b["gerente"]))
    codigo2 = client.get("/api/aniversario/vouchers", headers=cab(b["gerente"])).json()[0]["codigo"]
    r3 = client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(b["gerente"]),
                     json={"pagamentos": [{"forma": "pix"}], "voucher_codigo": codigo2})
    assert r3.status_code == 422 and "intransferível" in r3.json()["detail"]


def test_voucher_fora_da_validade(client, admin):
    hoje = date.today()
    b = _preparar(client, admin, f"{hoje.month:02d}-{hoje.day:02d}")
    client.post(f"/api/aniversario/gerar?mes={hoje.month}", headers=cab(b["gerente"]))
    voucher = client.get("/api/aniversario/vouchers", headers=cab(b["gerente"])).json()[0]
    with get_db() as db:   # força a janela para o passado
        db.execute("UPDATE birthday_vouchers SET valido_de='2020-01-01', valido_ate='2020-01-31' WHERE id=?",
                   (voucher["id"],))
    r = _fechar_com_voucher(client, b, voucher["codigo"])
    assert r.status_code == 422 and "validade" in r.json()["detail"]


def test_cancelamento_manual_auditado(client, admin):
    hoje = date.today()
    b = _preparar(client, admin, f"{hoje.month:02d}-20")
    client.post(f"/api/aniversario/gerar?mes={hoje.month}", headers=cab(b["gerente"]))
    voucher = client.get("/api/aniversario/vouchers", headers=cab(b["gerente"])).json()[0]
    r = client.post(f"/api/aniversario/vouchers/{voucher['id']}/cancelar", headers=cab(b["gerente"]))
    assert r.status_code == 200
    trilha = client.get("/api/relatorios/auditoria", headers=cab(b["gerente"])).json()
    assert any(a["acao"] == "voucher_cancelado_manual" for a in trilha)
    # voucher cancelado não resgata
    resultado = _fechar_com_voucher(client, b, voucher["codigo"])
    assert resultado.status_code == 422 and "cancelado" in resultado.json()["detail"]
