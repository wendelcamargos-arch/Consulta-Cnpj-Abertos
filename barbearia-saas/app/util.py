"""Utilitários compartilhados: relógio por tenant e configurações."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .db import row


def timezone_tenant(db, tenant_id: int) -> ZoneInfo:
    t = row(db.execute("SELECT timezone FROM tenants WHERE id=?", (tenant_id,)))
    try:
        return ZoneInfo((t or {}).get("timezone") or "America/Sao_Paulo")
    except Exception:
        return ZoneInfo("America/Sao_Paulo")


def agora_tenant(db, tenant_id: int) -> datetime:
    """Hora atual no fuso da barbearia (naive, para comparação com TEXT ISO)."""
    return datetime.now(timezone_tenant(db, tenant_id)).replace(tzinfo=None)


def settings_tenant(db, tenant_id: int) -> dict:
    s = row(db.execute("SELECT * FROM tenant_settings WHERE tenant_id=?", (tenant_id,)))
    if not s:
        db.execute("INSERT INTO tenant_settings (tenant_id) VALUES (?)", (tenant_id,))
        s = row(db.execute("SELECT * FROM tenant_settings WHERE tenant_id=?", (tenant_id,)))
    s["dias_fechados"] = json.loads(s.get("dias_fechados") or "[]")
    return s


def dia_fechado(settings: dict, data) -> bool:
    """dias_fechados aceita dias da semana (int 0=segunda..6=domingo) e datas 'YYYY-MM-DD'."""
    fechados = settings.get("dias_fechados") or []
    return data.weekday() in [d for d in fechados if isinstance(d, int)] or \
        data.isoformat() in [d for d in fechados if isinstance(d, str)]
