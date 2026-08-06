"""Camada de banco de dados multi-tenant com dois dialetos.

PostgreSQL é o banco operacional (DATABASE_URL=postgresql://...).
SQLite é permitido apenas para teste unitário isolado (DATABASE_URL=sqlite:///...
ou variável BARBEARIA_DB legada).

A camada expõe uma interface única:
  with get_db() as db:
      db.execute(sql, params)   # placeholders '?' em ambos os dialetos
      db.insert(sql, params)    # INSERT que retorna o id gerado
Todo acesso a dado de negócio DEVE filtrar por tenant_id — ver docs/MULTI_TENANCY.md.
"""
import os
import sqlite3
from contextlib import contextmanager

from .schema import schema_postgres, schema_sqlite

_DEFAULT_SQLITE = os.path.join(os.path.dirname(__file__), "..", "barbearia.db")


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url
    legado = os.environ.get("BARBEARIA_DB", "")
    if legado:
        return f"sqlite:///{legado}"
    if os.environ.get("APP_ENV", "development") == "production":
        raise RuntimeError("DATABASE_URL (PostgreSQL) é obrigatória em produção")
    return f"sqlite:///{_DEFAULT_SQLITE}"


def is_postgres() -> bool:
    return database_url().startswith(("postgres://", "postgresql://"))


class Conexao:
    """Envelope fino sobre sqlite3/psycopg com placeholders unificados ('?')."""

    def __init__(self, conn, postgres: bool):
        self._conn = conn
        self.postgres = postgres

    def _traduzir(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.postgres else sql

    def execute(self, sql: str, params: tuple | list = ()):
        if self.postgres:
            cur = self._conn.cursor()
            cur.execute(self._traduzir(sql), tuple(params))
            return cur
        return self._conn.execute(sql, tuple(params))

    def insert(self, sql: str, params: tuple | list = ()) -> int:
        """Executa um INSERT e devolve o id gerado, em ambos os dialetos."""
        if self.postgres:
            cur = self._conn.cursor()
            cur.execute(self._traduzir(sql) + " RETURNING id", tuple(params))
            return cur.fetchone()["id"]
        return self._conn.execute(sql, tuple(params)).lastrowid

    def executescript(self, script: str) -> None:
        if self.postgres:
            with self._conn.cursor() as cur:
                cur.execute(script)
        else:
            self._conn.executescript(script)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def connect() -> Conexao:
    url = database_url()
    if url.startswith(("postgres://", "postgresql://")):
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(url, row_factory=dict_row)
        return Conexao(conn, postgres=True)
    caminho = url.removeprefix("sqlite:///")
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return Conexao(conn, postgres=False)


def init_db() -> None:
    """Cria o schema completo (idempotente). Em produção use Alembic (migrations/)."""
    db = connect()
    try:
        db.executescript(schema_postgres() if db.postgres else schema_sqlite())
        db.commit()
    finally:
        db.close()


@contextmanager
def get_db():
    db = connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def row(cur) -> dict | None:
    r = cur.fetchone()
    return dict(r) if r else None
