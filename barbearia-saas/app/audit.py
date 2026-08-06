"""Audit log de ações críticas.

Regra fixa: o campo detalhe NUNCA recebe CPF, senha, token ou telefone completo.
"""


def auditar(db, tenant_id: int | None, usuario_id: int | None, acao: str,
            entidade: str = "", entidade_id: int | None = None, detalhe: str = "") -> None:
    db.execute(
        "INSERT INTO audit_logs (tenant_id, usuario_id, acao, entidade, entidade_id, detalhe) VALUES (?,?,?,?,?,?)",
        (tenant_id, usuario_id, acao, entidade, entidade_id, detalhe[:500]))
