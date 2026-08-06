from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..auth import gerar_token, verificar_senha
from ..db import get_db, row

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    senha: str


@router.post("/login")
def login(dados: LoginIn):
    with get_db() as db:
        u = row(db.execute("SELECT * FROM usuarios WHERE email=? AND ativo=1", (dados.email.lower().strip(),)))
    if not u or not verificar_senha(dados.senha, u["senha_hash"]):
        raise HTTPException(401, "E-mail ou senha inválidos")
    tenant = None
    if u["tenant_id"]:
        with get_db() as db:
            tenant = row(db.execute("SELECT id, nome, slug, cor_primaria, logo_url FROM tenants WHERE id=?", (u["tenant_id"],)))
    return {
        "token": gerar_token(u),
        "usuario": {"id": u["id"], "nome": u["nome"], "papel": u["papel"], "tenant_id": u["tenant_id"]},
        "tenant": tenant,
    }
