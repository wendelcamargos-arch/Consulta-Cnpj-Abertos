"""Painel administrativo da plataforma e configurações do tenant."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..audit import auditar
from ..auth import exigir_gerente, exigir_superadmin, hash_senha
from ..db import get_db, row, rows
from ..util import settings_tenant

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


class TenantIn(BaseModel):
    nome: str
    slug: str
    cor_primaria: str = "#C9A227"
    logo_url: str = ""
    telefone_whatsapp: str = ""
    timezone: str = "America/Sao_Paulo"
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
    timezone: str | None = None


class SettingsIn(BaseModel):
    confirmacao_min: int | None = None
    lembrete_min: int | None = None
    aviso_min: int | None = None
    politica_recorrencia: str | None = None
    dias_fechados: list | None = None


class UsuarioIn(BaseModel):
    nome: str
    email: str
    senha: str
    papel: str = "recepcao"


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


@router.post("")
def criar(dados: TenantIn, usuario: dict = Depends(exigir_superadmin)):
    with get_db() as db:
        if row(db.execute("SELECT id FROM tenants WHERE slug=?", (dados.slug,))):
            raise HTTPException(409, "Já existe uma barbearia com esse slug")
        if row(db.execute("SELECT id FROM usuarios WHERE email=?", (dados.gerente_email.lower(),))):
            raise HTTPException(409, "Já existe um usuário com esse e-mail")
        tenant_id = db.insert(
            """INSERT INTO tenants (nome, slug, cor_primaria, logo_url, telefone_whatsapp, timezone, plano, mensalidade)
               VALUES (?,?,?,?,?,?,?,?)""",
            (dados.nome, dados.slug, dados.cor_primaria, dados.logo_url,
             dados.telefone_whatsapp, dados.timezone, dados.plano, dados.mensalidade))
        db.execute("INSERT INTO tenant_settings (tenant_id) VALUES (?)", (tenant_id,))
        db.execute("INSERT INTO birthday_campaigns (tenant_id) VALUES (?)", (tenant_id,))
        db.execute(
            "INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (?,?,?,?, 'gerente')",
            (tenant_id, dados.gerente_nome, dados.gerente_email.lower(), hash_senha(dados.gerente_senha)))
        auditar(db, tenant_id, usuario["uid"], "tenant_criado", "tenant", tenant_id, dados.slug)
    return {"id": tenant_id, "mensagem": f"Barbearia '{dados.nome}' criada com login de gerente"}


@router.patch("/{tenant_id}/ativo")
def alternar_ativo(tenant_id: int, usuario: dict = Depends(exigir_superadmin)):
    with get_db() as db:
        t = row(db.execute("SELECT ativo FROM tenants WHERE id=?", (tenant_id,)))
        if not t:
            raise HTTPException(404, "Barbearia não encontrada")
        novo = 0 if t["ativo"] else 1
        db.execute("UPDATE tenants SET ativo=? WHERE id=?", (novo, tenant_id))
        auditar(db, tenant_id, usuario["uid"],
                "tenant_reativado" if novo else "tenant_suspenso", "tenant", tenant_id)
    return {"ativo": novo}


@router.get("/meu")
def meu_tenant(usuario: dict = Depends(exigir_gerente)):
    with get_db() as db:
        t = row(db.execute("SELECT * FROM tenants WHERE id=?", (usuario["tenant_id"],)))
        t["settings"] = settings_tenant(db, usuario["tenant_id"])
        return t


@router.patch("/meu")
def configurar_meu(dados: TenantConfigIn, usuario: dict = Depends(exigir_gerente)):
    campos = {k: v for k, v in dados.model_dump().items() if v is not None}
    if not campos:
        return {"mensagem": "Nada para atualizar"}
    sets = ", ".join(f"{k}=?" for k in campos)
    with get_db() as db:
        db.execute(f"UPDATE tenants SET {sets} WHERE id=?", (*campos.values(), usuario["tenant_id"]))
        auditar(db, usuario["tenant_id"], usuario["uid"], "tenant_configurado")
    return {"mensagem": "Identidade visual atualizada"}


@router.patch("/meu/settings")
def configurar_settings(dados: SettingsIn, usuario: dict = Depends(exigir_gerente)):
    if dados.politica_recorrencia and dados.politica_recorrencia not in ("pular", "sugerir", "pendencia"):
        raise HTTPException(422, "Política deve ser pular, sugerir ou pendencia")
    with get_db() as db:
        settings_tenant(db, usuario["tenant_id"])   # garante a linha
        campos = {}
        for k in ("confirmacao_min", "lembrete_min", "aviso_min", "politica_recorrencia"):
            v = getattr(dados, k)
            if v is not None:
                campos[k] = v
        if dados.dias_fechados is not None:
            campos["dias_fechados"] = json.dumps(dados.dias_fechados)
        if campos:
            sets = ", ".join(f"{k}=?" for k in campos)
            db.execute(f"UPDATE tenant_settings SET {sets} WHERE tenant_id=?",
                       (*campos.values(), usuario["tenant_id"]))
        auditar(db, usuario["tenant_id"], usuario["uid"], "settings_atualizados")
    return {"mensagem": "Configurações atualizadas"}


@router.post("/meu/usuarios")
def criar_usuario(dados: UsuarioIn, usuario: dict = Depends(exigir_gerente)):
    if dados.papel not in ("gerente", "recepcao"):
        raise HTTPException(422, "Papel deve ser gerente ou recepcao")
    if len(dados.senha) < 8:
        raise HTTPException(422, "A senha deve ter pelo menos 8 caracteres")
    with get_db() as db:
        if row(db.execute("SELECT id FROM usuarios WHERE email=?", (dados.email.lower(),))):
            raise HTTPException(409, "E-mail já cadastrado")
        db.execute("INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (?,?,?,?,?)",
                   (usuario["tenant_id"], dados.nome, dados.email.lower(),
                    hash_senha(dados.senha), dados.papel))
        auditar(db, usuario["tenant_id"], usuario["uid"], "usuario_criado", detalhe=dados.papel)
    return {"mensagem": f"Usuário {dados.nome} ({dados.papel}) criado"}
