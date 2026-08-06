"""Login com rate limit/bloqueio e recuperação de senha com token de uso único.

Anti-enumeração: login e recuperação respondem de forma idêntica para e-mail
existente ou não. O token de recuperação é entregue por canal externo (e-mail);
em desenvolvimento ele é retornado na resposta apenas quando APP_ENV != production.
"""
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..audit import auditar
from ..auth import (consumir_token_recuperacao, gerar_token, gerar_token_recuperacao,
                    hash_senha, limpar_falhas_login, login_bloqueado,
                    registrar_falha_login, verificar_senha)
from ..db import get_db, row

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    senha: str


class RecuperarIn(BaseModel):
    email: str


class RedefinirIn(BaseModel):
    token: str
    nova_senha: str


@router.post("/login")
def login(dados: LoginIn, request: Request):
    email = dados.email.lower().strip()
    chave = f"{email}|{request.client.host if request.client else '?'}"
    if login_bloqueado(chave):
        raise HTTPException(429, "Muitas tentativas — aguarde 15 minutos")
    with get_db() as db:
        u = row(db.execute("SELECT * FROM usuarios WHERE email=? AND ativo=1", (email,)))
        if not u or not verificar_senha(dados.senha, u["senha_hash"]):
            registrar_falha_login(chave)
            raise HTTPException(401, "E-mail ou senha inválidos")
        if u["tenant_id"]:
            t = row(db.execute("SELECT ativo FROM tenants WHERE id=?", (u["tenant_id"],)))
            if not t or not t["ativo"]:
                raise HTTPException(403, "Barbearia suspensa — contate a plataforma")
        limpar_falhas_login(chave)
        tenant = None
        if u["tenant_id"]:
            tenant = row(db.execute(
                "SELECT id, nome, slug, cor_primaria, logo_url FROM tenants WHERE id=?", (u["tenant_id"],)))
        auditar(db, u["tenant_id"], u["id"], "login")
    return {
        "token": gerar_token(u),
        "usuario": {"id": u["id"], "nome": u["nome"], "papel": u["papel"], "tenant_id": u["tenant_id"]},
        "tenant": tenant,
    }


@router.post("/recuperar")
def recuperar(dados: RecuperarIn):
    resposta = {"mensagem": "Se o e-mail existir, as instruções foram enviadas"}
    with get_db() as db:
        u = row(db.execute("SELECT * FROM usuarios WHERE email=? AND ativo=1",
                           (dados.email.lower().strip(),)))
        if not u:
            return resposta
        token = gerar_token_recuperacao(db, u["id"])
        auditar(db, u["tenant_id"], u["id"], "recuperacao_solicitada")
        # produção: enviar por e-mail (integração fora do escopo desta fase — docs/SECURITY.md)
        if os.environ.get("APP_ENV", "development") != "production":
            resposta["token_dev"] = token
    return resposta


@router.post("/redefinir")
def redefinir(dados: RedefinirIn):
    if len(dados.nova_senha) < 8:
        raise HTTPException(422, "A senha deve ter pelo menos 8 caracteres")
    with get_db() as db:
        usuario_id = consumir_token_recuperacao(db, dados.token)
        if not usuario_id:
            raise HTTPException(422, "Token inválido, expirado ou já utilizado")
        db.execute("UPDATE usuarios SET senha_hash=? WHERE id=?",
                   (hash_senha(dados.nova_senha), usuario_id))
        u = row(db.execute("SELECT tenant_id FROM usuarios WHERE id=?", (usuario_id,)))
        auditar(db, u["tenant_id"], usuario_id, "senha_redefinida")
    return {"mensagem": "Senha redefinida — faça login"}
