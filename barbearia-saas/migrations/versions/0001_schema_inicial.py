"""Schema inicial completo (todas as entidades do MVP).

Revision ID: 0001
Revises:
Create Date: 2026-08-06
"""
from alembic import op

from app.schema import schema_postgres, schema_sqlite

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABELAS = [
    "audit_logs", "movimentos_estoque", "produtos", "lancamentos_caixa", "payments",
    "cash_sessions", "commissions", "birthday_vouchers", "birthday_campaigns",
    "whatsapp_events", "mensagens_whatsapp", "recurrence_occurrences",
    "agendamento_servicos", "agendamentos", "recorrencias", "combo_itens", "servicos",
    "chair_contracts", "chairs", "barber_blocks", "barbeiros", "customer_consents",
    "clientes", "password_reset_tokens", "usuarios", "tenant_settings", "tenants",
]


def upgrade() -> None:
    dialecto = op.get_bind().dialect.name
    ddl = schema_postgres() if dialecto == "postgresql" else schema_sqlite()
    for comando in _dividir(ddl):
        op.execute(comando)


def downgrade() -> None:
    for tabela in TABELAS:
        op.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE"
                   if op.get_bind().dialect.name == "postgresql"
                   else f"DROP TABLE IF EXISTS {tabela}")


def _dividir(script: str) -> list[str]:
    """Divide o DDL em comandos, preservando blocos DO $$...$$ e funções."""
    comandos, atual, em_dolar = [], [], None
    for linha in script.splitlines():
        atual.append(linha)
        for marcador in ("$do$", "$$"):
            if marcador in linha:
                ocorrencias = linha.count(marcador)
                for _ in range(ocorrencias):
                    if em_dolar is None:
                        em_dolar = marcador
                    elif em_dolar == marcador:
                        em_dolar = None
        if em_dolar is None and linha.rstrip().endswith(";"):
            comando = "\n".join(atual).strip()
            if comando and comando != ";":
                comandos.append(comando)
            atual = []
    resto = "\n".join(atual).strip()
    if resto:
        comandos.append(resto)
    return comandos
