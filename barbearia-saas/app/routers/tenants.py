"""Painel administrativo da plataforma white label: gestão de barbearias (tenants)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import exigir_superadmin, exigir_gerente, hash_senha
from ..db import get_db, row, rows

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


class TenantIn(BaseModel):
    nome: str
    slug: str
    cor_primaria: str = "#C9A227"
    logo_url: str = ""
    telefone_whatsapp: str = ""
    plano: str = "mensal"
    mensalidade: float = 199.90
    gerente_nome: str
    gerente_email: str
    gerente_senha: str


class TenantConfigIn(BaseModel):
    nome: str | None = None
    cor_primaria: str | None = None
    logo_url: str | None = None
    telefone_whatsapp: str | None = None


@router.get("", dependencies=[Depends(exigir_superadmin)])
def listar():
    with get_db() as db:
        lista = rows(db.execute("SELECT * FROM tenants ORDER BY nome"))
        for t in lista:
            t["total_clientes"] = row(db.execute(
                "SELECT COUNT(*) c FROM clientes WHERE tenant_id=?", (t["id"],)))["c"]
            t["total_agendamentos"] = row(db.execute(
                "SELECT COUNT(*) c FROM agendamentos WHERE tenant_id=?", (t["id"],)))["c"]
    return lista


@router.post("", dependencies=[Depends(exigir_superadmin)])
def criar(dados: TenantIn):
    with get_db() as db:
        if row(db.execute("SELECT id FROM tenants WHERE slug=?", (dados.slug,))):
            raise HTTPException(409, "Já existe uma barbearia com esse slug")
        if row(db.execute("SELECT id FROM usuarios WHERE email=?", (dados.gerente_email.lower(),))):
            raise HTTPException(409, "Já existe um usuário com esse e-mail")
        cur = db.execute(
            "INSERT INTO tenants (nome, slug, cor_primaria, logo_url, telefone_whatsapp, plano, mensalidade) VALUES (?,?,?,?,?,?,?)",
            (dados.nome, dados.slug, dados.cor_primaria, dados.logo_url,
             dados.telefone_whatsapp, dados.plano, dados.mensalidade))
        tenant_id = cur.lastrowid
        db.execute(
            "INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (?,?,?,?, 'gerente')",
            (tenant_id, dados.gerente_nome, dados.gerente_email.lower(), hash_senha(dados.gerente_senha)))
    return {"id": tenant_id, "mensagem": f"Barbearia '{dados.nome}' criada com login de gerente"}


@router.patch("/{tenant_id}/ativo", dependencies=[Depends(exigir_superadmin)])
def alternar_ativo(tenant_id: int):
    with get_db() as db:
        t = row(db.execute("SELECT ativo FROM tenants WHERE id=?", (tenant_id,)))
        if not t:
            raise HTTPException(404, "Barbearia não encontrada")
        novo = 0 if t["ativo"] else 1
        db.execute("UPDATE tenants SET ativo=? WHERE id=?", (novo, tenant_id))
    return {"ativo": novo}


@router.get("/meu")
def meu_tenant(usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        return row(db.execute("SELECT * FROM tenants WHERE id=?", (usuario["tenant_id"],)))


@router.patch("/meu")
def configurar_meu(dados: TenantConfigIn, usuario: dict = Depends(exigir_gerente)):
    campos = {k: v for k, v in dados.model_dump().items() if v is not None}
    if not campos:
        return {"mensagem": "Nada para atualizar"}
    sets = ", ".join(f"{k}=?" for k in campos)
    with get_db() as db:
        db.execute(f"UPDATE tenants SET {sets} WHERE id=?", (*campos.values(), usuario["tenant_id"]))
    return {"mensagem": "Identidade visual atualizada"}


class UsuarioIn(BaseModel):
    nome: str
    email: str
    senha: str
    papel: str = "recepcao"


@router.post("/meu/usuarios")
def criar_usuario(dados: UsuarioIn, usuario: dict = Depends(exigir_gerente)):
    if dados.papel not in ("gerente", "recepcao"):
        raise HTTPException(422, "Papel deve ser gerente ou recepcao")
    with get_db() as db:
        if row(db.execute("SELECT id FROM usuarios WHERE email=?", (dados.email.lower(),))):
            raise HTTPException(409, "E-mail já cadastrado")
        db.execute("INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (?,?,?,?,?)",
                   (usuario["tenant_id"], dados.nome, dados.email.lower(), hash_senha(dados.senha), dados.papel))
    return {"mensagem": f"Usuário {dados.nome} ({dados.papel}) criado"}
