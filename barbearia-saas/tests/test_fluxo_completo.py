"""Teste de fumaça do fluxo completo do balcão, ponta a ponta.

Cobre o caminho do infográfico: criar tenant → login → cadastrar cliente/barbeiro/
serviços → agendar → WhatsApp na fila → confirmar → atender → fechar → caixa → DRE.
"""
import os
import tempfile

os.environ["BARBEARIA_DB"] = os.path.join(tempfile.mkdtemp(), "teste.db")

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_senha
from app.db import get_db, init_db
from app.main import app

cliente_http = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def preparar():
    init_db()
    with get_db() as db:
        db.execute("INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (NULL,'Admin','admin@x.com',?, 'superadmin')",
                   (hash_senha("123"),))


def cab(token, extra=None):
    return {"Authorization": f"Bearer {token}", **(extra or {})}


def test_fluxo_completo():
    # login superadmin e criação do tenant
    r = cliente_http.post("/api/auth/login", json={"email": "admin@x.com", "senha": "123"})
    assert r.status_code == 200
    admin = r.json()["token"]

    r = cliente_http.post("/api/tenants", headers=cab(admin), json={
        "nome": "Barbearia Teste", "slug": "teste",
        "gerente_nome": "Gerente", "gerente_email": "g@teste.com", "gerente_senha": "abc"})
    assert r.status_code == 200, r.text

    # login do gerente
    gerente = cliente_http.post("/api/auth/login", json={"email": "g@teste.com", "senha": "abc"}).json()["token"]

    # cadastros
    r = cliente_http.post("/api/clientes", headers=cab(gerente), json={
        "nome": "João Silva", "telefone": "34 99911-0001", "cpf": "390.533.447-05", "aniversario": "15/08"})
    assert r.status_code == 200, r.text
    cliente_id = r.json()["id"]

    # CPF inválido é recusado
    assert cliente_http.post("/api/clientes", headers=cab(gerente), json={
        "nome": "X", "telefone": "3499911000", "cpf": "111.111.111-11"}).status_code == 422

    barbeiro_id = cliente_http.post("/api/barbeiros", headers=cab(gerente), json={
        "nome": "Carlos", "modelo": "comissao", "percentual_comissao": 50}).json()["id"]
    corte = cliente_http.post("/api/servicos", headers=cab(gerente), json={
        "nome": "Corte", "preco": 45, "duracao_min": 30}).json()["id"]
    barba = cliente_http.post("/api/servicos", headers=cab(gerente), json={
        "nome": "Barba", "preco": 35, "duracao_min": 30}).json()["id"]
    r = cliente_http.post("/api/servicos/combo", headers=cab(gerente), json={
        "nome": "Combo", "preco": 70, "servico_ids": [corte, barba]})
    assert r.json()["duracao_min"] == 60

    # agendamento amanhã 10h
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:00")
    r = cliente_http.post("/api/agendamentos", headers=cab(gerente), json={
        "cliente_id": cliente_id, "barbeiro_id": barbeiro_id, "inicio": amanha,
        "servico_ids": [corte, barba]})
    assert r.status_code == 200, r.text
    ag = r.json()
    assert ag["valor_total"] == 80

    # conflito de horário no mesmo barbeiro é bloqueado
    assert cliente_http.post("/api/agendamentos", headers=cab(gerente), json={
        "cliente_id": cliente_id, "barbeiro_id": barbeiro_id,
        "inicio": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:30"),
        "servico_ids": [corte]}).status_code == 409

    # mensagens de WhatsApp entraram na fila (confirmação + lembrete)
    fila = cliente_http.get("/api/whatsapp/fila", headers=cab(gerente)).json()
    tipos = {m["tipo"] for m in fila if m["agendamento_id"] == ag["id"]}
    assert "confirmacao" in tipos

    # ciclo de status e fechamento
    for status in ("confirmado", "atendido"):
        assert cliente_http.patch(f"/api/agendamentos/{ag['id']}/status?status={status}",
                                  headers=cab(gerente)).status_code == 200
    r = cliente_http.post(f"/api/agendamentos/{ag['id']}/fechar", headers=cab(gerente),
                          json={"forma_pagamento": "pix"})
    assert r.status_code == 200
    assert r.json()["comissao_barbeiro"] == 40.0  # 50% de 80

    # caixa registrou entrada de serviço e saída de comissão
    caixa = cliente_http.get("/api/caixa", headers=cab(gerente)).json()
    categorias = {(l["tipo"], l["categoria"]) for l in caixa["lancamentos"]}
    assert ("entrada", "servico") in categorias and ("saida", "comissao") in categorias
    assert caixa["saldo"] == 40.0

    # DRE do mês reflete o resultado
    dre = cliente_http.get("/api/relatorios/dre", headers=cab(gerente)).json()
    assert dre["receita_bruta"] == 80.0
    assert dre["comissoes"] == 40.0
    assert dre["lucro_liquido"] == 40.0

    # recorrência semanal gera agendamentos futuros
    rec = cliente_http.post("/api/recorrencias", headers=cab(gerente), json={
        "cliente_id": cliente_id, "barbeiro_id": barbeiro_id, "servico_id": corte,
        "frequencia": "semanal", "dia_semana": 2, "hora": "14:00"}).json()
    r = cliente_http.post(f"/api/recorrencias/{rec['id']}/gerar?quantidade=3", headers=cab(gerente))
    assert len(r.json()["criados"]) == 3

    # isolamento multi-tenant: outro tenant não enxerga os dados
    cliente_http.post("/api/tenants", headers=cab(admin), json={
        "nome": "Outra", "slug": "outra",
        "gerente_nome": "G2", "gerente_email": "g2@outra.com", "gerente_senha": "abc"})
    g2 = cliente_http.post("/api/auth/login", json={"email": "g2@outra.com", "senha": "abc"}).json()["token"]
    assert cliente_http.get("/api/clientes", headers=cab(g2)).json() == []

    # recepção não pode criar barbeiro (papel)
    cliente_http.post("/api/tenants/meu/usuarios", headers=cab(gerente), json={
        "nome": "Recep", "email": "r@teste.com", "senha": "abc", "papel": "recepcao"})
    recep = cliente_http.post("/api/auth/login", json={"email": "r@teste.com", "senha": "abc"}).json()["token"]
    assert cliente_http.post("/api/barbeiros", headers=cab(recep), json={"nome": "X"}).status_code == 403


def test_campanha_aniversario():
    gerente = cliente_http.post("/api/auth/login", json={"email": "g@teste.com", "senha": "abc"}).json()["token"]
    r = cliente_http.post("/api/whatsapp/campanha-aniversario?mes=8", headers=cab(gerente))
    assert r.status_code == 200
    assert r.json()["mensagens_criadas"] >= 1
    # idempotente: segunda chamada não duplica
    assert cliente_http.post("/api/whatsapp/campanha-aniversario?mes=8",
                             headers=cab(gerente)).json()["mensagens_criadas"] == 0
