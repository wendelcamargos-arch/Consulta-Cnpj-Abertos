"""Fila de mensagens WhatsApp: processamento, respostas e campanha de aniversário."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import contexto_tenant
from ..db import get_db, row, rows
from ..whatsapp_service import enviar_via_provedor, link_wame, template_aniversario

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@router.get("/fila")
def fila(status: str = "", usuario: dict = Depends(contexto_tenant)):
    condicoes, params = ["m.tenant_id=?"], [usuario["tenant_id"]]
    if status:
        condicoes.append("m.status=?")
        params.append(status)
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
    """Dispara todas as mensagens pendentes cujo horário já chegou.
    Em produção, chame este endpoint por um cron (ex.: a cada minuto)."""
    agora = datetime.now().strftime("%Y-%m-%dT%H:%M")
    enviadas, erros = 0, 0
    with get_db() as db:
        pendentes = rows(db.execute(
            "SELECT * FROM mensagens_whatsapp WHERE tenant_id=? AND status='pendente' AND agendada_para<=?",
            (usuario["tenant_id"], agora)))
        for m in pendentes:
            ok, detalhe = enviar_via_provedor(m["telefone"], m["texto"])
            db.execute("UPDATE mensagens_whatsapp SET status=?, enviada_em=? WHERE id=?",
                       ("enviada" if ok else "erro", agora, m["id"]))
            enviadas += ok
            erros += not ok
    return {"enviadas": enviadas, "erros": erros}


class RespostaIn(BaseModel):
    resposta: str  # confirmar | cancelar | atrasar


@router.post("/{msg_id}/resposta")
def registrar_resposta(msg_id: int, dados: RespostaIn, usuario: dict = Depends(contexto_tenant)):
    """Registra a resposta do cliente (em produção chega via webhook do provedor)
    e reflete o status no agendamento."""
    if dados.resposta not in ("confirmar", "cancelar", "atrasar"):
        raise HTTPException(422, "Resposta deve ser confirmar, cancelar ou atrasar")
    with get_db() as db:
        m = row(db.execute("SELECT * FROM mensagens_whatsapp WHERE id=? AND tenant_id=?",
                           (msg_id, usuario["tenant_id"])))
        if not m:
            raise HTTPException(404, "Mensagem não encontrada")
        db.execute("UPDATE mensagens_whatsapp SET resposta=? WHERE id=?", (dados.resposta, msg_id))
        if m["agendamento_id"]:
            novo_status = {"confirmar": "confirmado", "cancelar": "cancelado", "atrasar": "atrasado"}[dados.resposta]
            db.execute("UPDATE agendamentos SET status=? WHERE id=? AND status IN ('agendado','confirmado')",
                       (novo_status, m["agendamento_id"]))
    return {"mensagem": f"Resposta '{dados.resposta}' registrada"}


@router.post("/campanha-aniversario")
def campanha_aniversario(mes: int, usuario: dict = Depends(contexto_tenant)):
    """Gera mensagens de aniversário para todos os aniversariantes do mês."""
    if not 1 <= mes <= 12:
        raise HTTPException(422, "Mês inválido")
    agora = datetime.now()
    criadas = 0
    with get_db() as db:
        barbearia = row(db.execute("SELECT nome FROM tenants WHERE id=?", (usuario["tenant_id"],)))["nome"]
        aniversariantes = rows(db.execute(
            "SELECT * FROM clientes WHERE tenant_id=? AND aniversario LIKE ?",
            (usuario["tenant_id"], f"{mes:02d}-%")))
        for c in aniversariantes:
            dia = c["aniversario"].split("-")[1]
            envio = f"{agora.year}-{mes:02d}-{dia}T09:00"
            if row(db.execute(
                    """SELECT id FROM mensagens_whatsapp WHERE tenant_id=? AND cliente_id=?
                       AND tipo='aniversario' AND agendada_para=?""",
                    (usuario["tenant_id"], c["id"], envio))):
                continue
            db.execute(
                """INSERT INTO mensagens_whatsapp (tenant_id, cliente_id, telefone, tipo, texto, agendada_para)
                   VALUES (?,?,?,?,?,?)""",
                (usuario["tenant_id"], c["id"], c["telefone"], "aniversario",
                 template_aniversario(c["nome"], barbearia), envio))
            criadas += 1
    return {"aniversariantes": len(aniversariantes), "mensagens_criadas": criadas}
