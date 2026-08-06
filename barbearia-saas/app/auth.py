"""Autenticação com token HMAC assinado (stdlib, sem dependência de JWT).

Papéis:
  superadmin — dono da plataforma white label; gerencia tenants (tenant_id NULL)
  gerente    — dono da barbearia; acesso total ao próprio tenant
  recepcao   — operação do balcão: agenda, clientes, caixa
"""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, Header, HTTPException

from .db import get_db, row

SECRET = os.environ.get("BARBEARIA_SECRET", "troque-este-segredo-em-producao").encode()
TOKEN_TTL = 60 * 60 * 12  # 12h de expediente


def hash_senha(senha: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.sha256((salt + senha).encode()).hexdigest()
    return f"{salt}${digest}"


def verificar_senha(senha: str, armazenada: str) -> bool:
    try:
        salt, digest = armazenada.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hashlib.sha256((salt + senha).encode()).hexdigest(), digest)


def gerar_token(usuario: dict) -> str:
    payload = {
        "uid": usuario["id"],
        "tenant_id": usuario["tenant_id"],
        "papel": usuario["papel"],
        "nome": usuario["nome"],
        "exp": int(time.time()) + TOKEN_TTL,
    }
    corpo = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    assinatura = hmac.new(SECRET, corpo.encode(), hashlib.sha256).hexdigest()
    return f"{corpo}.{assinatura}"


def decodificar_token(token: str) -> dict:
    try:
        corpo, assinatura = token.split(".", 1)
    except ValueError:
        raise HTTPException(401, "Token malformado")
    esperada = hmac.new(SECRET, corpo.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(assinatura, esperada):
        raise HTTPException(401, "Assinatura inválida")
    payload = json.loads(base64.urlsafe_b64decode(corpo))
    if payload["exp"] < time.time():
        raise HTTPException(401, "Sessão expirada, faça login novamente")
    return payload


def usuario_atual(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Não autenticado")
    return decodificar_token(authorization.removeprefix("Bearer "))


def exigir_tenant(usuario: dict = Depends(usuario_atual)) -> dict:
    """Usuário de barbearia (gerente ou recepção). Superadmin pode operar um
    tenant específico passando-o no header X-Tenant-Id."""
    if usuario["tenant_id"] is None:
        raise HTTPException(403, "Superadmin deve informar o tenant (X-Tenant-Id)")
    return usuario


def exigir_gerente(usuario: dict = Depends(exigir_tenant)) -> dict:
    if usuario["papel"] not in ("gerente",):
        raise HTTPException(403, "Apenas o gerente pode executar esta ação")
    return usuario


def exigir_superadmin(usuario: dict = Depends(usuario_atual)) -> dict:
    if usuario["papel"] != "superadmin":
        raise HTTPException(403, "Apenas o administrador da plataforma")
    return usuario


def contexto_tenant(usuario: dict = Depends(usuario_atual),
                    x_tenant_id: int | None = Header(default=None)) -> dict:
    """Resolve o tenant efetivo: o do usuário, ou o do header para superadmin."""
    if usuario["tenant_id"] is not None:
        return usuario
    if x_tenant_id is None:
        raise HTTPException(403, "Superadmin deve informar X-Tenant-Id para operar uma barbearia")
    with get_db() as db:
        t = row(db.execute("SELECT id FROM tenants WHERE id=? AND ativo=1", (x_tenant_id,)))
    if not t:
        raise HTTPException(404, "Barbearia não encontrada")
    return {**usuario, "tenant_id": x_tenant_id}
