"""Automação WhatsApp: templates, fila de envio e integração com provedor.

Em produção, configure META_WA_TOKEN e META_WA_PHONE_ID (WhatsApp Cloud API).
Sem credenciais, o sistema opera em modo simulado: as mensagens entram na fila,
são marcadas como enviadas pelo processador e ficam auditáveis na tela WhatsApp —
com link wa.me pronto para disparo manual pela recepção.
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

META_WA_TOKEN = os.environ.get("META_WA_TOKEN", "")
META_WA_PHONE_ID = os.environ.get("META_WA_PHONE_ID", "")

MESES = {"01": "janeiro", "02": "fevereiro", "03": "março", "04": "abril", "05": "maio",
         "06": "junho", "07": "julho", "08": "agosto", "09": "setembro", "10": "outubro",
         "11": "novembro", "12": "dezembro"}


def template_confirmacao(cliente: str, barbearia: str, hora: str, servicos: list[str]) -> str:
    return (f"Olá, {cliente.split()[0]}! 👋 Seu horário na {barbearia} é hoje às {hora} "
            f"({', '.join(servicos)}). Pode confirmar? Responda: ✅ Confirmar · ❌ Cancelar · ⏰ Vou atrasar")


def template_lembrete(cliente: str, barbearia: str, data: str, hora: str) -> str:
    return (f"Olá, {cliente.split()[0]}! Lembrando: sua agenda na {barbearia} "
            f"está marcada para {data} às {hora}. Até lá! ✂️")


def template_aniversario(cliente: str, barbearia: str) -> str:
    return (f"Feliz aniversário, {cliente.split()[0]}! 🎉 A {barbearia} preparou um presente: "
            f"10% de desconto em qualquer serviço este mês. Agende seu horário!")


def link_wame(telefone: str, texto: str) -> str:
    numero = telefone if telefone.startswith("55") else f"55{telefone}"
    return f"https://wa.me/{numero}?text={urllib.parse.quote(texto)}"


def agendar_mensagens_do_agendamento(db, tenant_id: int, ag_id: int, cliente: dict,
                                     barbeiro: dict, inicio: datetime, servicos: list[str]) -> None:
    """Cria na fila: lembrete na véspera (19h) e confirmação 30 min antes."""
    barbearia = db.execute("SELECT nome FROM tenants WHERE id=?", (tenant_id,)).fetchone()["nome"]
    hora = inicio.strftime("%H:%M")
    data_fmt = inicio.strftime("%d/%m")

    confirmacao = inicio - timedelta(minutes=30)
    db.execute(
        """INSERT INTO mensagens_whatsapp (tenant_id, cliente_id, agendamento_id, telefone, tipo, texto, agendada_para)
           VALUES (?,?,?,?,?,?,?)""",
        (tenant_id, cliente["id"], ag_id, cliente["telefone"], "confirmacao",
         template_confirmacao(cliente["nome"], barbearia, hora, servicos),
         confirmacao.strftime("%Y-%m-%dT%H:%M")))

    vespera = (inicio - timedelta(days=1)).replace(hour=19, minute=0)
    if vespera > datetime.now():
        db.execute(
            """INSERT INTO mensagens_whatsapp (tenant_id, cliente_id, agendamento_id, telefone, tipo, texto, agendada_para)
               VALUES (?,?,?,?,?,?,?)""",
            (tenant_id, cliente["id"], ag_id, cliente["telefone"], "lembrete",
             template_lembrete(cliente["nome"], barbearia, data_fmt, hora),
             vespera.strftime("%Y-%m-%dT%H:%M")))


def cancelar_mensagens_do_agendamento(db, ag_id: int) -> None:
    db.execute("UPDATE mensagens_whatsapp SET status='cancelada' WHERE agendamento_id=? AND status='pendente'", (ag_id,))


def enviar_via_provedor(telefone: str, texto: str) -> tuple[bool, str]:
    """Dispara pela WhatsApp Cloud API quando configurada; senão, simula."""
    if not (META_WA_TOKEN and META_WA_PHONE_ID):
        return True, "simulado"
    numero = telefone if telefone.startswith("55") else f"55{telefone}"
    corpo = json.dumps({"messaging_product": "whatsapp", "to": numero,
                        "type": "text", "text": {"body": texto}}).encode()
    req = urllib.request.Request(
        f"https://graph.facebook.com/v21.0/{META_WA_PHONE_ID}/messages", data=corpo,
        headers={"Authorization": f"Bearer {META_WA_TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, resp.read().decode()[:200]
    except Exception as exc:  # rede/credencial: registra o erro sem derrubar a fila
        return False, str(exc)[:200]
