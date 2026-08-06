"""Agenda: conflito, concorrência, expediente, bloqueio, alteração, cancelamento,
fechamento duplicado."""
import threading

import pytest

from app.db import is_postgres
from tests.conftest import cab

DIA = "2027-06-15"   # terça-feira futura, dentro do expediente padrão 09-19


def agendar(client, b, hora, dia=DIA, **kw):
    return client.post("/api/agendamentos", headers=cab(b["gerente"]), json={
        "cliente_id": kw.get("cliente_id", b["cliente"]),
        "barbeiro_id": kw.get("barbeiro_id", b["barbeiro"]),
        "inicio": f"{dia}T{hora}", "servico_ids": kw.get("servico_ids", [b["corte"]])})


def test_conflito_simples(client, barbearia):
    assert agendar(client, barbearia, "10:00").status_code == 200
    r = agendar(client, barbearia, "10:15")      # sobrepõe 10:00-10:30
    assert r.status_code == 409
    assert agendar(client, barbearia, "10:30").status_code == 200   # adjacente ok


def test_fora_do_expediente(client, barbearia):
    assert agendar(client, barbearia, "07:00").status_code == 422
    assert agendar(client, barbearia, "18:45").status_code == 422   # fim 19:15 > 19:00


def test_dia_fechado(client, barbearia):
    client.patch("/api/tenants/meu/settings", headers=cab(barbearia["gerente"]),
                 json={"dias_fechados": [6, "2027-06-16"]})          # domingo + data específica
    assert agendar(client, barbearia, "10:00", dia="2027-06-20").status_code == 422  # domingo
    assert agendar(client, barbearia, "10:00", dia="2027-06-16").status_code == 422  # feriado
    client.patch("/api/tenants/meu/settings", headers=cab(barbearia["gerente"]),
                 json={"dias_fechados": []})


def test_barbeiro_bloqueado(client, barbearia):
    client.post(f"/api/barbeiros/{barbearia['barbeiro']}/bloqueios",
                headers=cab(barbearia["gerente"]),
                json={"inicio": f"{DIA}T14:00", "fim": f"{DIA}T16:00", "motivo": "consulta médica"})
    r = agendar(client, barbearia, "14:30")
    assert r.status_code == 409
    assert "indisponível" in r.json()["detail"]
    assert agendar(client, barbearia, "16:00").status_code == 200


def test_reagendamento(client, barbearia):
    ag = agendar(client, barbearia, "11:00").json()
    r = client.put(f"/api/agendamentos/{ag['id']}", headers=cab(barbearia["gerente"]),
                   json={"inicio": f"{DIA}T12:00"})
    assert r.status_code == 200
    assert r.json()["inicio"] == f"{DIA}T12:00"
    # horário antigo liberado
    assert agendar(client, barbearia, "11:00").status_code == 200


def test_cancelamento_e_transicoes(client, barbearia):
    ag = agendar(client, barbearia, "09:00").json()
    ok = client.patch(f"/api/agendamentos/{ag['id']}/status?status=cancelado",
                      headers=cab(barbearia["gerente"]))
    assert ok.status_code == 200
    # cancelado não transiciona mais
    r = client.patch(f"/api/agendamentos/{ag['id']}/status?status=atendido",
                     headers=cab(barbearia["gerente"]))
    assert r.status_code == 422
    # horário liberado após cancelamento
    assert agendar(client, barbearia, "09:00").status_code == 200


def test_fechamento_duplicado(client, barbearia):
    ag = agendar(client, barbearia, "17:00").json()
    client.patch(f"/api/agendamentos/{ag['id']}/status?status=atendido",
                 headers=cab(barbearia["gerente"]))
    r1 = client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(barbearia["gerente"]),
                     json={"pagamentos": [{"forma": "pix"}]})
    assert r1.status_code == 200 and r1.json()["status"] == "pago"
    r2 = client.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(barbearia["gerente"]),
                     json={"pagamentos": [{"forma": "pix"}]})
    assert r2.status_code == 422


@pytest.mark.skipif(not is_postgres(), reason="garantia de concorrência é do PostgreSQL")
def test_conflito_concorrente_bloqueado_pelo_banco(barbearia):
    """Duas inserções sobrepostas em conexões paralelas: a constraint de exclusão
    GiST garante que só uma sobrevive, mesmo sem passar pela validação da app."""
    from app.db import connect
    resultados = []

    def inserir(offset):
        db = connect()
        try:
            db.execute(
                """INSERT INTO agendamentos (tenant_id, cliente_id, barbeiro_id, inicio, fim, valor_total)
                   VALUES (?,?,?,?,?,50)""",
                (barbearia["tenant_id"], barbearia["cliente"], barbearia["barbeiro"],
                 f"2027-07-01T10:{offset:02d}", "2027-07-01T10:45"))
            db.commit()
            resultados.append("ok")
        except Exception:
            db.rollback()
            resultados.append("bloqueado")
        finally:
            db.close()

    t1 = threading.Thread(target=inserir, args=(0,))
    t2 = threading.Thread(target=inserir, args=(15,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert sorted(resultados) == ["bloqueado", "ok"]
