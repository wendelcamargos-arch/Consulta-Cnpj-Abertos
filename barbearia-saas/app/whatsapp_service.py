"""Mensageria WhatsApp — arquitetura oficial Meta Cloud API.

Camadas:
  ProvedorMensageria (abstrato) → MetaCloudProvider | SimuladoProvider
  Fila em banco (mensagens_whatsapp) com estados:
    pendente → enviada → entregue → lida        (status via webhook)
    pendente → erro → (retry com backoff) → falha_final
  Webhook com verificação de assinatura e idempotência em app/routers/whatsapp.py.

Momentos de lembrete configuráveis por tenant (tenant_settings):
  confirmacao_min (padrão 1440 = 24h) · lembrete_min (120 = 2h) · aviso_min (30).

Automação não oficial (WhatsApp Web/QR Code) NÃO é usada. O link wa.me aparece
apenas como conveniência de disparo manual pela recepção, nunca como canal
automatizado.
"""
import json
import os
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from .util import settings_tenant

RETRY_BACKOFF_MIN = [1, 5, 15]      # minutos entre tentativas; depois falha_final
MAX_TENTATIVAS = len(RETRY_BACKOFF_MIN) + 1

TEMPLATES = {
    "confirmacao_agendamento": lambda c, b, hora, servicos:
        (f"Olá, {c.split()[0]}! 👋 Seu horário na {b} é às {hora} "
         f"({', '.join(servicos)}). Pode confirmar? Responda: CONFIRMAR · CANCELAR · VOU ATRASAR"),
    "lembrete_agendamento": lambda c, b, data, hora:
        f"Olá, {c.split()[0]}! Lembrando: sua agenda na {b} está marcada para {data} às {hora}. Até lá! ✂️",
    "aviso_final": lambda c, b, hora:
        f"{c.split()[0]}, seu horário na {b} é daqui a pouco, às {hora}. Estamos te esperando! 💈",
    "aniversario_cliente": lambda c, b, pct:
        (f"Feliz aniversário, {c.split()[0]}! 🎉 A {b} preparou um presente: "
         f"{pct:g}% de desconto. Apresente este voucher ao agendar. Válido conforme regulamento."),
}


class ProvedorMensageria(ABC):
    @abstractmethod
    def enviar(self, telefone: str, texto: str) -> tuple[bool, str, str]:
        """Retorna (ok, provider_msg_id, detalhe)."""


class SimuladoProvider(ProvedorMensageria):
    """Desenvolvimento/teste: nunca toca a rede."""

    def __init__(self):
        self.enviadas: list[dict] = []
        self.falhar = False          # testes podem forçar falha

    def enviar(self, telefone: str, texto: str) -> tuple[bool, str, str]:
        if self.falhar:
            return False, "", "falha simulada"
        self.enviadas.append({"telefone": telefone, "texto": texto})
        return True, f"sim-{len(self.enviadas)}", "simulado"


class MetaCloudProvider(ProvedorMensageria):
    """WhatsApp Business Cloud API oficial (graph.facebook.com)."""

    def __init__(self):
        self.token = os.environ["META_WHATSAPP_ACCESS_TOKEN"]
        self.phone_id = os.environ["META_WHATSAPP_PHONE_NUMBER_ID"]

    def enviar(self, telefone: str, texto: str) -> tuple[bool, str, str]:
        numero = telefone if telefone.startswith("55") else f"55{telefone}"
        corpo = json.dumps({"messaging_product": "whatsapp", "to": numero,
                            "type": "text", "text": {"body": texto}}).encode()
        req = urllib.request.Request(
            f"https://graph.facebook.com/v21.0/{self.phone_id}/messages", data=corpo,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                dados = json.loads(resp.read())
                msg_id = (dados.get("messages") or [{}])[0].get("id", "")
                return True, msg_id, "ok"
        except Exception as exc:
            return False, "", str(exc)[:200]


_provider: ProvedorMensageria | None = None


def obter_provider() -> ProvedorMensageria:
    global _provider
    if _provider is None:
        if os.environ.get("META_WHATSAPP_ACCESS_TOKEN") and os.environ.get("META_WHATSAPP_PHONE_NUMBER_ID"):
            _provider = MetaCloudProvider()
        else:
            _provider = SimuladoProvider()
    return _provider


def definir_provider(p: ProvedorMensageria | None) -> None:
    """Injeção para testes."""
    global _provider
    _provider = p


def link_wame(telefone: str, texto: str) -> str:
    numero = telefone if telefone.startswith("55") else f"55{telefone}"
    return f"https://wa.me/{numero}?text={urllib.parse.quote(texto)}"


def _enfileirar(db, tenant_id: int, cliente: dict, ag_id: int | None, tipo: str,
                template: str, texto: str, quando: datetime) -> None:
    db.execute(
        """INSERT INTO mensagens_whatsapp
           (tenant_id, cliente_id, agendamento_id, telefone, tipo, template, texto, agendada_para)
           VALUES (?,?,?,?,?,?,?,?)""",
        (tenant_id, cliente["id"], ag_id, cliente["telefone"], tipo, template, texto,
         quando.strftime("%Y-%m-%dT%H:%M")))


def agendar_mensagens_do_agendamento(db, tenant_id: int, ag_id: int, cliente: dict,
                                     barbeiro: dict, inicio: datetime,
                                     servicos: list[str], agora: datetime) -> None:
    """Enfileira os três momentos configuráveis do tenant (pula os já passados)."""
    from .db import row
    barbearia = row(db.execute("SELECT nome FROM tenants WHERE id=?", (tenant_id,)))["nome"]
    cfg = settings_tenant(db, tenant_id)
    hora = inicio.strftime("%H:%M")
    data_fmt = inicio.strftime("%d/%m")

    momentos = [
        ("confirmacao", "confirmacao_agendamento", cfg["confirmacao_min"],
         TEMPLATES["confirmacao_agendamento"](cliente["nome"], barbearia, hora, servicos)),
        ("lembrete", "lembrete_agendamento", cfg["lembrete_min"],
         TEMPLATES["lembrete_agendamento"](cliente["nome"], barbearia, data_fmt, hora)),
        ("aviso_final", "aviso_final", cfg["aviso_min"],
         TEMPLATES["aviso_final"](cliente["nome"], barbearia, hora)),
    ]
    for tipo, template, minutos, texto in momentos:
        quando = inicio - timedelta(minutes=minutos)
        if quando > agora:
            _enfileirar(db, tenant_id, cliente, ag_id, tipo, template, texto, quando)


def cancelar_mensagens_do_agendamento(db, ag_id: int) -> None:
    db.execute(
        "UPDATE mensagens_whatsapp SET status='cancelada' WHERE agendamento_id=? AND status='pendente'",
        (ag_id,))


def processar_fila(db, tenant_id: int, agora: datetime) -> dict:
    """Dispara pendentes vencidas e reprocessa erros cujo backoff venceu."""
    from .db import rows
    marca = agora.strftime("%Y-%m-%dT%H:%M")
    provider = obter_provider()
    enviadas = erros = finais = 0
    pendentes = rows(db.execute(
        """SELECT * FROM mensagens_whatsapp
           WHERE tenant_id=? AND (
             (status='pendente' AND agendada_para<=?) OR
             (status='erro' AND proximo_retry IS NOT NULL AND proximo_retry<=?))""",
        (tenant_id, marca, marca)))
    for m in pendentes:
        ok, provider_id, _detalhe = provider.enviar(m["telefone"], m["texto"])
        tentativas = m["tentativas"] + 1
        if ok:
            db.execute(
                "UPDATE mensagens_whatsapp SET status='enviada', provider_msg_id=?, tentativas=?, enviada_em=?, proximo_retry=NULL WHERE id=?",
                (provider_id, tentativas, marca, m["id"]))
            enviadas += 1
        elif tentativas >= MAX_TENTATIVAS:
            db.execute(
                "UPDATE mensagens_whatsapp SET status='falha_final', tentativas=?, proximo_retry=NULL WHERE id=?",
                (tentativas, m["id"]))
            finais += 1
        else:
            retry = agora + timedelta(minutes=RETRY_BACKOFF_MIN[tentativas - 1])
            db.execute(
                "UPDATE mensagens_whatsapp SET status='erro', tentativas=?, proximo_retry=? WHERE id=?",
                (tentativas, retry.strftime("%Y-%m-%dT%H:%M"), m["id"]))
            erros += 1
    return {"enviadas": enviadas, "erros": erros, "falhas_finais": finais}
