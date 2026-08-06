"""Recorrência: frequências, políticas de conflito, exceções e cancelamentos."""
from datetime import date

from app.routers.recorrencias import proximas_datas
from tests.conftest import cab

HOJE = date(2027, 6, 1)   # terça-feira


def test_datas_semanal_quinzenal_mensal_anual():
    semanal = proximas_datas({"frequencia": "semanal", "dia_semana": 2}, 3, HOJE)
    assert [d.isoformat() for d in semanal] == ["2027-06-02", "2027-06-09", "2027-06-16"]
    quinzenal = proximas_datas({"frequencia": "quinzenal", "dia_semana": 2}, 2, HOJE)
    assert [d.isoformat() for d in quinzenal] == ["2027-06-02", "2027-06-16"]
    mensal = proximas_datas({"frequencia": "mensal", "dia_mes": 10}, 2, HOJE)
    assert [d.isoformat() for d in mensal] == ["2027-06-10", "2027-07-10"]
    anual = proximas_datas({"frequencia": "anual", "data_base": "2020-08-20"}, 2, HOJE)
    assert [d.isoformat() for d in anual] == ["2027-08-20", "2028-08-20"]


def test_anual_29_fevereiro_vira_28_em_ano_nao_bissexto():
    datas = proximas_datas({"frequencia": "anual", "data_base": "2024-02-29"}, 2, date(2026, 1, 1))
    assert [d.isoformat() for d in datas] == ["2026-02-28", "2027-02-28"]
    bissexto = proximas_datas({"frequencia": "anual", "data_base": "2024-02-29"}, 1, date(2027, 12, 1))
    assert bissexto[0].isoformat() == "2028-02-29"


def test_data_fim_limita_geracao():
    datas = proximas_datas({"frequencia": "semanal", "dia_semana": 2,
                            "data_inicio": None, "data_fim": "2027-06-10"}, 10, HOJE)
    assert [d.isoformat() for d in datas] == ["2027-06-02", "2027-06-09"]


def criar_rec(client, b, politica=None, hora="10:00"):
    return client.post("/api/recorrencias", headers=cab(b["gerente"]), json={
        "cliente_id": b["cliente"], "barbeiro_id": b["barbeiro"], "servico_id": b["corte"],
        "frequencia": "semanal", "dia_semana": 2, "hora": hora, "politica": politica}).json()


def test_gerar_cria_agendamentos_e_nao_duplica(client, barbearia):
    rec = criar_rec(client, barbearia)
    r1 = client.post(f"/api/recorrencias/{rec['id']}/gerar?quantidade=3",
                     headers=cab(barbearia["gerente"])).json()
    assert len(r1["criados"]) == 3
    r2 = client.post(f"/api/recorrencias/{rec['id']}/gerar?quantidade=3",
                     headers=cab(barbearia["gerente"])).json()
    assert r2["criados"] == []       # ocorrências já tratadas não repetem


def test_politica_pular_e_pendencia_em_conflito(client, admin):
    from tests.conftest import nova_barbearia
    b = nova_barbearia(client, admin)
    rec_a = criar_rec(client, b, politica="pular", hora="11:00")
    client.post(f"/api/recorrencias/{rec_a['id']}/gerar?quantidade=2", headers=cab(b["gerente"]))
    # segunda recorrência no MESMO horário/barbeiro → conflita
    rec_b = criar_rec(client, b, politica="pular", hora="11:00")
    r = client.post(f"/api/recorrencias/{rec_b['id']}/gerar?quantidade=2",
                    headers=cab(b["gerente"])).json()
    assert len(r["pulados"]) == 2 and r["criados"] == []

    rec_c = criar_rec(client, b, politica="pendencia", hora="11:00")
    r = client.post(f"/api/recorrencias/{rec_c['id']}/gerar?quantidade=2",
                    headers=cab(b["gerente"])).json()
    assert len(r["pendentes"]) == 2 and r["criados"] == []
    ocorr = client.get(f"/api/recorrencias/{rec_c['id']}/ocorrencias",
                       headers=cab(b["gerente"])).json()
    assert all(o["status"] == "pendente" for o in ocorr)


def test_politica_sugerir_encontra_horario_alternativo(client, admin):
    from tests.conftest import nova_barbearia
    b = nova_barbearia(client, admin)
    rec_a = criar_rec(client, b, hora="09:00")
    client.post(f"/api/recorrencias/{rec_a['id']}/gerar?quantidade=1", headers=cab(b["gerente"]))
    rec_b = criar_rec(client, b, politica="sugerir", hora="09:00")
    r = client.post(f"/api/recorrencias/{rec_b['id']}/gerar?quantidade=1",
                    headers=cab(b["gerente"])).json()
    assert len(r["sugeridos"]) == 1
    assert r["sugeridos"][0]["hora"] != "09:00"


def test_cancelar_ocorrencia_e_serie(client, admin):
    from tests.conftest import nova_barbearia
    b = nova_barbearia(client, admin)
    rec = criar_rec(client, b, hora="15:00")
    gerados = client.post(f"/api/recorrencias/{rec['id']}/gerar?quantidade=2",
                          headers=cab(b["gerente"])).json()["criados"]
    data_primeira = gerados[0]["inicio"][:10]
    r = client.delete(f"/api/recorrencias/{rec['id']}/ocorrencia/{data_primeira}",
                      headers=cab(b["gerente"]))
    assert r.status_code == 200
    # série encerrada cancelando futuros
    r = client.delete(f"/api/recorrencias/{rec['id']}?cancelar_futuros=true",
                      headers=cab(b["gerente"])).json()
    assert r["agendamentos_cancelados"] >= 1
    ativas = client.get("/api/recorrencias", headers=cab(b["gerente"])).json()
    assert rec["id"] not in {x["id"] for x in ativas}
