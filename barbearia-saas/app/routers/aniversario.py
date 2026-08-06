"""Campanha de aniversário com voucher único e antifraude.

Regras (docs/LGPD.md e FASE 7):
  - mensagem só para cliente com consentimento de marketing registrado;
  - envio programado para as 08:00 (configurável) no fuso da barbearia;
  - voucher único por cliente/ano (UNIQUE no banco), intransferível, uso único,
    válido apenas na janela configurada, serviço elegível configurável;
  - 29/02 em ano não bissexto → comemora em 28/02;
  - toda alteração manual é auditada.
"""
import secrets
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..audit import auditar
from ..auth import contexto_tenant, exigir_gerente
from ..db import get_db, row, rows
from ..util import agora_tenant
from ..whatsapp_service import TEMPLATES

router = APIRouter(prefix="/api/aniversario", tags=["aniversario"])


def config_campanha(db, tenant_id: int) -> dict:
    c = row(db.execute("SELECT * FROM birthday_campaigns WHERE tenant_id=?", (tenant_id,)))
    if not c:
        db.execute("INSERT INTO birthday_campaigns (tenant_id) VALUES (?)", (tenant_id,))
        c = row(db.execute("SELECT * FROM birthday_campaigns WHERE tenant_id=?", (tenant_id,)))
    return c


class CampanhaIn(BaseModel):
    ativo: bool = True
    hora_envio: str = "08:00"
    percentual: float = 10
    servico_id: int | None = None
    validade_dias: int = 30
    cumulativo: bool = False


@router.get("/campanha")
def obter_campanha(usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return config_campanha(db, usuario["tenant_id"])


@router.put("/campanha")
def configurar_campanha(dados: CampanhaIn, usuario: dict = Depends(exigir_gerente)):
    if not (0 < dados.percentual <= 100):
        raise HTTPException(422, "Percentual deve estar entre 0 e 100")
    with get_db() as db:
        config_campanha(db, usuario["tenant_id"])
        db.execute(
            """UPDATE birthday_campaigns SET ativo=?, hora_envio=?, percentual=?, servico_id=?,
               validade_dias=?, cumulativo=? WHERE tenant_id=?""",
            (int(dados.ativo), dados.hora_envio, dados.percentual, dados.servico_id,
             dados.validade_dias, int(dados.cumulativo), usuario["tenant_id"]))
        auditar(db, usuario["tenant_id"], usuario["uid"], "campanha_aniversario_configurada")
    return {"mensagem": "Campanha atualizada"}


def data_aniversario_no_ano(aniversario_mm_dd: str, ano: int) -> date | None:
    """MM-DD → date no ano; 29/02 vira 28/02 em ano não bissexto."""
    try:
        mes, dia = int(aniversario_mm_dd[:2]), int(aniversario_mm_dd[3:5])
    except (ValueError, IndexError):
        return None
    try:
        return date(ano, mes, dia)
    except ValueError:
        if mes == 2 and dia == 29:
            return date(ano, 2, 28)
        return None


@router.post("/gerar")
def gerar_campanha(mes: int, usuario: dict = Depends(contexto_tenant)):
    """Emite vouchers e enfileira mensagens para aniversariantes do mês com consentimento."""
    if not 1 <= mes <= 12:
        raise HTTPException(422, "Mês inválido")
    with get_db() as db:
        cfg = config_campanha(db, usuario["tenant_id"])
        if not cfg["ativo"]:
            raise HTTPException(422, "Campanha de aniversário está desativada")
        barbearia = row(db.execute("SELECT nome FROM tenants WHERE id=?", (usuario["tenant_id"],)))["nome"]
        agora = agora_tenant(db, usuario["tenant_id"])
        ano = agora.year

        aniversariantes = rows(db.execute(
            "SELECT * FROM clientes WHERE tenant_id=? AND aniversario LIKE ?",
            (usuario["tenant_id"], f"{mes:02d}-%")))
        emitidos, sem_consentimento, ja_emitidos = 0, 0, 0
        for c in aniversariantes:
            consent = row(db.execute(
                """SELECT concedido FROM customer_consents WHERE cliente_id=? AND tipo='marketing'
                   ORDER BY id DESC LIMIT 1""", (c["id"],)))
            if not consent or not consent["concedido"]:
                sem_consentimento += 1
                continue
            if row(db.execute(
                    "SELECT id FROM birthday_vouchers WHERE tenant_id=? AND cliente_id=? AND ano=?",
                    (usuario["tenant_id"], c["id"], ano))):
                ja_emitidos += 1
                continue
            aniversario = data_aniversario_no_ano(c["aniversario"], ano)
            if not aniversario:
                continue
            codigo = f"NIVER-{secrets.token_hex(4).upper()}"
            db.execute(
                """INSERT INTO birthday_vouchers (tenant_id, cliente_id, ano, codigo, percentual,
                                                  servico_id, valido_de, valido_ate)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (usuario["tenant_id"], c["id"], ano, codigo, cfg["percentual"], cfg["servico_id"],
                 aniversario.isoformat(),
                 (aniversario + timedelta(days=cfg["validade_dias"])).isoformat()))
            texto = TEMPLATES["aniversario_cliente"](c["nome"], barbearia, cfg["percentual"]) + \
                f" Código: {codigo}"
            db.execute(
                """INSERT INTO mensagens_whatsapp (tenant_id, cliente_id, telefone, tipo, template, texto, agendada_para)
                   VALUES (?,?,?,?,?,?,?)""",
                (usuario["tenant_id"], c["id"], c["telefone"], "aniversario",
                 "aniversario_cliente", texto,
                 f"{aniversario.isoformat()}T{cfg['hora_envio']}"))
            emitidos += 1
        auditar(db, usuario["tenant_id"], usuario["uid"], "campanha_aniversario_gerada",
                detalhe=f"mes={mes} emitidos={emitidos}")
    return {"aniversariantes": len(aniversariantes), "vouchers_emitidos": emitidos,
            "sem_consentimento": sem_consentimento, "ja_emitidos": ja_emitidos}


@router.get("/vouchers")
def listar_vouchers(usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return rows(db.execute(
            """SELECT v.*, c.nome cliente FROM birthday_vouchers v JOIN clientes c ON c.id=v.cliente_id
               WHERE v.tenant_id=? ORDER BY v.emitido_em DESC LIMIT 200""", (usuario["tenant_id"],)))


def resgatar_voucher(db, tenant_id: int, agendamento: dict, codigo: str, hoje: str) -> float:
    """Valida e resgata um voucher no fechamento. Retorna o valor do desconto.
    Chamado dentro da transação do fechamento (routers/agendamentos.py)."""
    v = row(db.execute("SELECT * FROM birthday_vouchers WHERE codigo=? AND tenant_id=?",
                       (codigo.strip().upper(), tenant_id)))
    if not v:
        raise HTTPException(404, "Voucher não encontrado")
    if v["cancelado"]:
        raise HTTPException(422, "Voucher cancelado")
    if v["resgatado_em"]:
        raise HTTPException(422, "Voucher já utilizado (uso único)")
    if v["cliente_id"] != agendamento["cliente_id"]:
        raise HTTPException(422, "Voucher é intransferível — pertence a outro cliente")
    if not (v["valido_de"] <= hoje <= v["valido_ate"]):
        raise HTTPException(422, f"Voucher fora da validade ({v['valido_de']} a {v['valido_ate']})")
    if v["servico_id"]:
        tem = row(db.execute(
            "SELECT 1 ok FROM agendamento_servicos WHERE agendamento_id=? AND servico_id=?",
            (agendamento["id"], v["servico_id"])))
        if not tem:
            raise HTTPException(422, "Voucher válido apenas para o serviço elegível configurado")
    cfg = config_campanha(db, tenant_id)
    if not cfg["cumulativo"] and agendamento.get("desconto", 0) > 0:
        raise HTTPException(422, "Voucher não cumulativo com outros descontos")
    desconto = round(agendamento["valor_total"] * v["percentual"] / 100, 2)
    db.execute(
        "UPDATE birthday_vouchers SET resgatado_em=?, agendamento_id=? WHERE id=?",
        (hoje, agendamento["id"], v["id"]))
    auditar(db, tenant_id, None, "voucher_resgatado", "voucher", v["id"],
            f"agendamento={agendamento['id']} desconto={desconto:.2f}")
    return desconto


@router.post("/vouchers/{voucher_id}/cancelar")
def cancelar_voucher(voucher_id: int, usuario: dict = Depends(exigir_gerente)):
    """Cancelamento manual (fraude/erro) — sempre auditado."""
    with get_db() as db:
        v = row(db.execute("SELECT * FROM birthday_vouchers WHERE id=? AND tenant_id=?",
                           (voucher_id, usuario["tenant_id"])))
        if not v:
            raise HTTPException(404, "Voucher não encontrado")
        if v["resgatado_em"]:
            raise HTTPException(422, "Voucher já resgatado não pode ser cancelado")
        db.execute("UPDATE birthday_vouchers SET cancelado=1 WHERE id=?", (voucher_id,))
        auditar(db, usuario["tenant_id"], usuario["uid"], "voucher_cancelado_manual",
                "voucher", voucher_id)
    return {"mensagem": "Voucher cancelado"}
