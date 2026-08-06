"""Autenticação: login, rate limit, RBAC, expiração, recuperação, seed bloqueado."""

import pytest

from app import auth as auth_mod
from tests.conftest import cab, nova_barbearia


def test_login_valido_e_invalido(client, admin, barbearia):
    ok = client.post("/api/auth/login", json={
        "email": f"gerente@{barbearia['slug']}.com", "senha": "senha-gerente-123"})
    assert ok.status_code == 200
    assert ok.json()["usuario"]["papel"] == "gerente"

    errado = client.post("/api/auth/login", json={
        "email": f"gerente@{barbearia['slug']}.com", "senha": "senha-errada"})
    assert errado.status_code == 401
    # anti-enumeração: e-mail inexistente responde igual
    fantasma = client.post("/api/auth/login", json={"email": "nao@existe.com", "senha": "x"})
    assert fantasma.status_code == 401
    assert errado.json()["detail"] == fantasma.json()["detail"]


def test_rate_limit_bloqueia_apos_tentativas(client, barbearia):
    email = f"gerente@{barbearia['slug']}.com"
    for _ in range(5):
        r = client.post("/api/auth/login", json={"email": email, "senha": "errada"})
        assert r.status_code == 401
    bloqueado = client.post("/api/auth/login", json={"email": email, "senha": "senha-gerente-123"})
    assert bloqueado.status_code == 429


def test_rbac_recepcao_nao_gerencia(client, barbearia):
    client.post("/api/tenants/meu/usuarios", headers=cab(barbearia["gerente"]), json={
        "nome": "Recep", "email": f"recep@{barbearia['slug']}.com",
        "senha": "senha-recep-123", "papel": "recepcao"})
    recep = client.post("/api/auth/login", json={
        "email": f"recep@{barbearia['slug']}.com", "senha": "senha-recep-123"}).json()["token"]
    assert client.post("/api/barbeiros", headers=cab(recep), json={"nome": "X"}).status_code == 403
    assert client.post("/api/servicos", headers=cab(recep),
                       json={"nome": "X", "preco": 1}).status_code == 403
    assert client.get("/api/tenants", headers=cab(recep)).status_code == 403
    # mas opera o balcão
    assert client.get("/api/agendamentos", headers=cab(recep)).status_code == 200


def test_token_expirado_e_assinatura(client, barbearia):
    original = auth_mod.TOKEN_TTL
    auth_mod.TOKEN_TTL = -1
    try:
        vencido = auth_mod.gerar_token({"id": 1, "tenant_id": barbearia["tenant_id"],
                                        "papel": "gerente", "nome": "X"})
    finally:
        auth_mod.TOKEN_TTL = original
    assert client.get("/api/clientes", headers=cab(vencido)).status_code == 401
    adulterado = barbearia["gerente"][:-4] + "0000"
    assert client.get("/api/clientes", headers=cab(adulterado)).status_code == 401
    assert client.get("/api/clientes").status_code == 401


def test_recuperacao_de_senha_token_uso_unico(client, admin):
    b = nova_barbearia(client, admin)
    email = f"gerente@{b['slug']}.com"
    r = client.post("/api/auth/recuperar", json={"email": email})
    assert r.status_code == 200
    token = r.json()["token_dev"]                       # exposto apenas fora de produção
    # anti-enumeração: e-mail inexistente responde 200 igual (sem token)
    r2 = client.post("/api/auth/recuperar", json={"email": "ninguem@nada.com"})
    assert r2.status_code == 200 and "token_dev" not in r2.json()

    assert client.post("/api/auth/redefinir", json={
        "token": token, "nova_senha": "curta"}).status_code == 422
    assert client.post("/api/auth/redefinir", json={
        "token": token, "nova_senha": "nova-senha-forte-1"}).status_code == 200
    # uso único
    assert client.post("/api/auth/redefinir", json={
        "token": token, "nova_senha": "outra-senha-forte"}).status_code == 422
    assert client.post("/api/auth/login", json={
        "email": email, "senha": "nova-senha-forte-1"}).status_code == 200


def test_seed_demo_bloqueado_em_producao(monkeypatch):
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "app.seed"],
                       env={"APP_ENV": "production", "PATH": "/usr/bin:/bin",
                            "DATABASE_URL": "postgresql://x:x@localhost/nada"},
                       capture_output=True, text=True, cwd=".")
    assert r.returncode == 1
    assert "proibido em produção" in r.stderr

    r2 = subprocess.run([sys.executable, "-m", "app.seed"],
                        env={"PATH": "/usr/bin:/bin"},   # sem DEMO_MODE
                        capture_output=True, text=True, cwd=".")
    assert r2.returncode == 1
    assert "DEMO_MODE" in r2.stderr


def test_senhas_nunca_em_texto_puro():
    from app.db import get_db
    with get_db() as db:
        linhas = db.execute("SELECT senha_hash FROM usuarios").fetchall()
    assert linhas
    for linha in linhas:
        assert dict(linha)["senha_hash"].startswith("$2")   # bcrypt


@pytest.mark.parametrize("papel_esperado", ["superadmin"])
def test_superadmin_precisa_de_header_para_operar_tenant(client, admin, papel_esperado):
    assert client.get("/api/clientes", headers=cab(admin)).status_code == 403
