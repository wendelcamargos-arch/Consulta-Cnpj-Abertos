"""Onboarding da barbearia: criação completa do tenant em um passo (superadmin)
e checklist de configuração para o gerente.

Cobre: identificação (nome/CNPJ/telefone/endereço), timezone, horário de
funcionamento, barbeiros (comissão ou cadeira), serviços/preços, identidade
visual, configuração de WhatsApp e lembretes, e convite de usuários.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..audit import auditar
from ..auth import exigir_gerente, exigir_superadmin, hash_senha
from ..db import get_db, row

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class BarbeiroOnb(BaseModel):
    nome: str
    modelo: str = "comissao"
    percentual_comissao: float = 50
    valor_aluguel: float = 0
    hora_inicio: str = "09:00"
    hora_fim: str = "19:00"


class ServicoOnb(BaseModel):
    nome: str
    preco: float
    duracao_min: int = 30


class UsuarioOnb(BaseModel):
    nome: str
    email: str
    senha: str
    papel: str = "recepcao"


class OnboardingIn(BaseModel):
    # 1-5: identificação
    nome: str
    cnpj: str = ""
    telefone: str = ""
    endereco: str = ""
    timezone: str = "America/Sao_Paulo"
    slug: str
    # 6: horário de funcionamento (dias fechados: 0=segunda..6=domingo)
    dias_fechados: list = [6]
    # 7-10: equipe e serviços
    barbeiros: list[BarbeiroOnb] = []
    servicos: list[ServicoOnb] = []
    # 11: identidade visual
    cor_primaria: str = "#C9A227"
    logo_url: str = ""
    # 12-13: WhatsApp e lembretes
    telefone_whatsapp: str = ""
    confirmacao_min: int = 1440
    lembrete_min: int = 120
    aviso_min: int = 30
    # 14: acessos
    gerente: UsuarioOnb
    usuarios: list[UsuarioOnb] = []
    plano: str = "mensal"
    mensalidade: float = 199.90


@router.post("")
def onboarding_completo(dados: OnboardingIn, usuario: dict = Depends(exigir_superadmin)):
    """Cria a barbearia inteira de uma vez a partir do formulário de onboarding."""
    with get_db() as db:
        if row(db.execute("SELECT id FROM tenants WHERE slug=?", (dados.slug,))):
            raise HTTPException(409, "Slug já em uso")
        if row(db.execute("SELECT id FROM usuarios WHERE email=?", (dados.gerente.email.lower(),))):
            raise HTTPException(409, "E-mail do gerente já cadastrado")
        tenant_id = db.insert(
            """INSERT INTO tenants (nome, slug, cor_primaria, logo_url, telefone_whatsapp, timezone, plano, mensalidade)
               VALUES (?,?,?,?,?,?,?,?)""",
            (dados.nome, dados.slug, dados.cor_primaria, dados.logo_url,
             dados.telefone_whatsapp, dados.timezone, dados.plano, dados.mensalidade))
        db.execute(
            """INSERT INTO tenant_settings (tenant_id, confirmacao_min, lembrete_min, aviso_min, dias_fechados)
               VALUES (?,?,?,?,?)""",
            (tenant_id, dados.confirmacao_min, dados.lembrete_min, dados.aviso_min,
             json.dumps(dados.dias_fechados)))
        db.execute("INSERT INTO birthday_campaigns (tenant_id) VALUES (?)", (tenant_id,))
        db.execute("INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (?,?,?,?,'gerente')",
                   (tenant_id, dados.gerente.nome, dados.gerente.email.lower(),
                    hash_senha(dados.gerente.senha)))
        for u in dados.usuarios:
            if u.papel not in ("gerente", "recepcao"):
                raise HTTPException(422, f"Papel inválido: {u.papel}")
            if row(db.execute("SELECT id FROM usuarios WHERE email=?", (u.email.lower(),))):
                raise HTTPException(409, f"E-mail já cadastrado: {u.email}")
            db.execute("INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (?,?,?,?,?)",
                       (tenant_id, u.nome, u.email.lower(), hash_senha(u.senha), u.papel))
        for b in dados.barbeiros:
            db.execute(
                """INSERT INTO barbeiros (tenant_id, nome, modelo, percentual_comissao, valor_aluguel, hora_inicio, hora_fim)
                   VALUES (?,?,?,?,?,?,?)""",
                (tenant_id, b.nome, b.modelo, b.percentual_comissao, b.valor_aluguel,
                 b.hora_inicio, b.hora_fim))
        for s in dados.servicos:
            db.execute("INSERT INTO servicos (tenant_id, nome, preco, duracao_min) VALUES (?,?,?,?)",
                       (tenant_id, s.nome, s.preco, s.duracao_min))
        auditar(db, tenant_id, usuario["uid"], "onboarding_completo", "tenant", tenant_id,
                f"barbeiros={len(dados.barbeiros)} servicos={len(dados.servicos)}")
    return {"tenant_id": tenant_id,
            "mensagem": f"Barbearia '{dados.nome}' criada com {len(dados.barbeiros)} barbeiro(s) e {len(dados.servicos)} serviço(s)"}


@router.get("/checklist")
def checklist(usuario: dict = Depends(exigir_gerente)):
    """Checklist de configuração do tenant — guia o gerente no primeiro acesso."""
    t = usuario["tenant_id"]
    with get_db() as db:
        def existe(sql, params=()):
            return bool(row(db.execute(sql, (t, *params))))
        itens = {
            "identidade_visual": existe("SELECT id FROM tenants WHERE id=? AND logo_url != ''"),
            "whatsapp_numero": existe("SELECT id FROM tenants WHERE id=? AND telefone_whatsapp != ''"),
            "barbeiros_cadastrados": existe("SELECT id FROM barbeiros WHERE tenant_id=? AND ativo=1"),
            "servicos_cadastrados": existe("SELECT id FROM servicos WHERE tenant_id=? AND ativo=1"),
            "clientes_cadastrados": existe("SELECT id FROM clientes WHERE tenant_id=?"),
            "lembretes_configurados": existe("SELECT id FROM tenant_settings WHERE tenant_id=?"),
            "campanha_aniversario": existe("SELECT id FROM birthday_campaigns WHERE tenant_id=? AND ativo=1"),
            "usuarios_equipe": existe("SELECT id FROM usuarios WHERE tenant_id=? AND papel='recepcao'"),
            "caixa_aberto_alguma_vez": existe("SELECT id FROM cash_sessions WHERE tenant_id=?"),
        }
    itens["completo"] = all(itens.values())
    return itens
