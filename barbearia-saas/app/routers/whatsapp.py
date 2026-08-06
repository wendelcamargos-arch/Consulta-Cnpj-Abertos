"""WhatsApp: fila, processamento, webhook oficial da Meta e respostas.

Webhook (Meta Cloud API):
  GET  /api/whatsapp/webhook  → verificação (hub.challenge)
  POST /api/whatsapp/webhook  → mensagens e status, com validação de assinatura
                                (X-Hub-Signature-256 + META_APP_SECRET) e
                                idempotência por evento (whatsapp_events.evento_id).
"""
import hashlib
import hmac
import json
import os
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ..audit import auditar
from ..auth import contexto_tenant
from ..db import get_db, row, rows
from ..util import agora_tenant
from ..whatsapp_service import link_wame, processar_fila

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.get("/fila")
def fila(status: str = "", pendencia: int = 0, usuario: dict = Depends(contexto_tenant)):
    condicoes, params = ["m.tenant_id=?"], [usuario["tenant_id"]]
    if status:
        condicoes.append("m.status=?")
        params.append(status)
    if pendencia:
        condicoes.append("m.pendente_recepcao=1")
    with get_db() as db:
        lista = rows(db.execute(
            f"""SELECT m.*, c.nome cliente FROM mensagens_whatsapp m
                LEFT JOIN clientes c ON c.id=m.cliente_id
                WHERE {' AND '.join(condicoes)} ORDER BY m.agendada_para DESC LIMIT 200""", params))
    for m in lista:
        m["link_wame"] = link_wame(m["telefone"], m["texto"])
    return lista


@router.post("/processar")
def processar(usuario: dict = Depends(contexto_tenant)):
    """Dispara pendentes/retries vencidos. Em produção: cron a cada minuto."""
    with get_db() as db:
        return processar_fila(db, usuario["tenant_id"], agora_tenant(db, usuario["tenant_id"]))


# ---------- interpretação de respostas ----------

RESPOSTAS = {"CONFIRMAR": "confirmar", "CANCELAR": "cancelar",
             "VOU ATRASAR": "atrasar", "ATRASAR": "atrasar"}


def _normalizar(texto: str) -> str:
    s = unicodedata.normalize("NFD", texto.strip().upper())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def interpretar_resposta(texto: str) -> str | None:
    return RESPOSTAS.get(_normalizar(texto))


def aplicar_resposta(db, mensagem: dict, resposta: str | None, texto_bruto: str) -> dict:
    """Aplica a resposta do cliente ao agendamento; ambígua vira pendência da recepção."""
    if resposta is None:
        db.execute(
            "UPDATE mensagens_whatsapp SET pendente_recepcao=1, resposta=? WHERE id=?",
            (f"ambigua: {texto_bruto[:80]}", mensagem["id"]))
        return {"resultado": "ambigua", "encaminhado_recepcao": True}
    db.execute("UPDATE mensagens_whatsapp SET resposta=?, pendente_recepcao=0 WHERE id=?",
               (resposta, mensagem["id"]))
    if mensagem["agendamento_id"]:
        novo = {"confirmar": "confirmado", "cancelar": "cancelado", "atrasar": "atrasado"}[resposta]
        db.execute(
            "UPDATE agendamentos SET status=? WHERE id=? AND status IN ('agendado','confirmado')",
            (novo, mensagem["agendamento_id"]))
        auditar(db, mensagem["tenant_id"], None, f"whatsapp_resposta_{resposta}",
                "agendamento", mensagem["agendamento_id"])
    return {"resultado": resposta}


class RespostaIn(BaseModel):
    resposta: str


@router.post("/{msg_id}/resposta")
def registrar_resposta_manual(msg_id: int, dados: RespostaIn, usuario: dict = Depends(contexto_tenant)):
    """Registro manual pela recepção (ex.: cliente respondeu por telefone)."""
    if dados.resposta not in ("confirmar", "cancelar", "atrasar"):
        raise HTTPException(422, "Resposta deve ser confirmar, cancelar ou atrasar")
    with get_db() as db:
        m = row(db.execute("SELECT * FROM mensagens_whatsapp WHERE id=? AND tenant_id=?",
                           (msg_id, usuario["tenant_id"])))
        if not m:
            raise HTTPException(404, "Mensagem não encontrada")
        return aplicar_resposta(db, m, dados.resposta, dados.resposta)


# ---------- webhook oficial Meta ----------

@router.get("/webhook", response_class=PlainTextResponse)
def webhook_verificacao(hub_mode: str = Query(default="", alias="hub.mode"),
                        hub_verify_token: str = Query(default="", alias="hub.verify_token"),
                        hub_challenge: str = Query(default="", alias="hub.challenge")):
    esperado = os.environ.get("META_WHATSAPP_VERIFY_TOKEN", "")
    if not esperado:
        raise HTTPException(503, "META_WHATSAPP_VERIFY_TOKEN não configurado")
    if hub_mode == "subscribe" and hmac.compare_digest(hub_verify_token, esperado):
        return hub_challenge
    raise HTTPException(403, "Token de verificação inválido")


def _validar_assinatura(corpo: bytes, cabecalho: str) -> None:
    segredo = os.environ.get("META_APP_SECRET", "")
    if not segredo:
        if os.environ.get("APP_ENV", "development") == "production":
            raise HTTPException(503, "META_APP_SECRET não configurado")
        return  # desenvolvimento sem credenciais: aceita (documentado em docs/SECURITY.md)
    esperada = "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(cabecalho or "", esperada):
        raise HTTPException(403, "Assinatura do webhook inválida")


def _evento_ja_processado(db, evento_id: str, tipo: str, payload: str) -> bool:
    if row(db.execute("SELECT id FROM whatsapp_events WHERE evento_id=?", (evento_id,))):
        return True
    db.execute("INSERT INTO whatsapp_events (evento_id, tipo, payload, processado) VALUES (?,?,?,1)",
               (evento_id, tipo, payload[:2000]))
    return False


STATUS_MAP = {"sent": "enviada", "delivered": "entregue", "read": "lida", "failed": "erro"}


@router.post("/webhook")
async def webhook_eventos(request: Request):
    corpo = await request.body()
    _validar_assinatura(corpo, request.headers.get("X-Hub-Signature-256", ""))
    try:
        payload = json.loads(corpo)
    except json.JSONDecodeError:
        raise HTTPException(422, "Payload inválido")

    resultados = {"status_atualizados": 0, "respostas": 0, "duplicados": 0, "ignorados": 0}
    with get_db() as db:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                valor = change.get("value", {})
                for st in valor.get("statuses", []):
                    ev_id = f"status:{st.get('id')}:{st.get('status')}"
                    if _evento_ja_processado(db, ev_id, "status", json.dumps(st)):
                        resultados["duplicados"] += 1
                        continue
                    novo = STATUS_MAP.get(st.get("status", ""))
                    if not novo:
                        resultados["ignorados"] += 1
                        continue
                    # nunca rebaixar 'lida' para 'entregue' (eventos fora de ordem)
                    db.execute(
                        """UPDATE mensagens_whatsapp SET status=? WHERE provider_msg_id=?
                           AND status NOT IN ('lida','falha_final','cancelada')""",
                        (novo, st.get("id", "")))
                    resultados["status_atualizados"] += 1
                for msg in valor.get("messages", []):
                    ev_id = f"msg:{msg.get('id')}"
                    if _evento_ja_processado(db, ev_id, "mensagem", json.dumps(msg)):
                        resultados["duplicados"] += 1
                        continue
                    texto = (msg.get("text") or {}).get("body", "") or \
                            (msg.get("button") or {}).get("text", "")
                    telefone = (msg.get("from") or "").removeprefix("55")
                    pendente = row(db.execute(
                        """SELECT * FROM mensagens_whatsapp
                           WHERE telefone=? AND tipo='confirmacao' AND status IN ('enviada','entregue','lida')
                             AND resposta='' ORDER BY agendada_para DESC LIMIT 1""", (telefone,)))
                    if pendente:
                        aplicar_resposta(db, pendente, interpretar_resposta(texto), texto)
                        resultados["respostas"] += 1
                    else:
                        resultados["ignorados"] += 1
    return resultados
