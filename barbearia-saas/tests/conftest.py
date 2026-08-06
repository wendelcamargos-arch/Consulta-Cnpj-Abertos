"""Infra de teste.

Roda em SQLite por padrão (teste unitário isolado) e em PostgreSQL quando
DATABASE_URL apontar para ele (suíte oficial):
  DATABASE_URL=postgresql://barbearia:barbearia_dev@localhost:5432/barbearia_test pytest
"""
import os
import tempfile
import uuid

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/teste.db"
os.environ.setdefault("META_WHATSAPP_VERIFY_TOKEN", "token-verificacao-teste")
os.environ.pop("META_WHATSAPP_ACCESS_TOKEN", None)   # nunca usar credencial real em teste
os.environ.pop("META_APP_SECRET", None)

import pytest
from fastapi.testclient import TestClient

from app import auth as auth_mod
from app.db import connect, get_db, init_db, is_postgres
from app.main import app
from app.whatsapp_service import SimuladoProvider, definir_provider


def _limpar_banco():
    db = connect()
    try:
        if db.postgres:
            db.executescript("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            db.commit()
    finally:
        db.close()
    init_db()


@pytest.fixture(scope="session", autouse=True)
def preparar_banco():
    _limpar_banco()
    yield


@pytest.fixture(autouse=True)
def limpar_rate_limit():
    auth_mod._tentativas.clear()
    auth_mod._bloqueios.clear()
    yield


@pytest.fixture()
def provider():
    p = SimuladoProvider()
    definir_provider(p)
    yield p
    definir_provider(None)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def cab(token, extra=None):
    return {"Authorization": f"Bearer {token}", **(extra or {})}


@pytest.fixture(scope="session")
def admin(client):
    """Superadmin da plataforma."""
    from app.auth import hash_senha
    with get_db() as db:
        if not db.execute("SELECT id FROM usuarios WHERE email='admin@teste.com'").fetchone():
            db.execute(
                "INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (NULL,'Admin','admin@teste.com',?, 'superadmin')",
                (hash_senha("senha-admin-123"),))
    r = client.post("/api/auth/login", json={"email": "admin@teste.com", "senha": "senha-admin-123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def nova_barbearia(client, admin_token, slug=None):
    """Fábrica: cria tenant completo e retorna dict com tokens e ids básicos."""
    slug = slug or f"b{uuid.uuid4().hex[:8]}"
    r = client.post("/api/tenants", headers=cab(admin_token), json={
        "nome": f"Barbearia {slug}", "slug": slug,
        "gerente_nome": "Gerente", "gerente_email": f"gerente@{slug}.com",
        "gerente_senha": "senha-gerente-123"})
    assert r.status_code == 200, r.text
    tenant_id = r.json()["id"]
    gerente = client.post("/api/auth/login", json={
        "email": f"gerente@{slug}.com", "senha": "senha-gerente-123"}).json()["token"]
    barbeiro = client.post("/api/barbeiros", headers=cab(gerente), json={
        "nome": "Barbeiro Padrão", "modelo": "comissao", "percentual_comissao": 50}).json()["id"]
    corte = client.post("/api/servicos", headers=cab(gerente), json={
        "nome": "Corte", "preco": 50, "duracao_min": 30}).json()["id"]
    cliente_id = client.post("/api/clientes", headers=cab(gerente), json={
        "nome": "Cliente Um", "telefone": "34999000001",
        "consentimento_marketing": True}).json()["id"]
    return {"slug": slug, "tenant_id": tenant_id, "gerente": gerente,
            "barbeiro": barbeiro, "corte": corte, "cliente": cliente_id}


@pytest.fixture()
def barbearia(client, admin):
    return nova_barbearia(client, admin)


def eh_postgres():
    return is_postgres()
