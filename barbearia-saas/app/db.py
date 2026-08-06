"""Camada de banco de dados — SQLite com escopo multi-tenant.

Toda tabela de negócio carrega tenant_id. O acesso passa pelo helper
`tenant_db`, que injeta o tenant do usuário autenticado em cada query.
"""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("BARBEARIA_DB", os.path.join(os.path.dirname(__file__), "..", "barbearia.db"))

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    cor_primaria TEXT NOT NULL DEFAULT '#C9A227',
    logo_url TEXT DEFAULT '',
    telefone_whatsapp TEXT DEFAULT '',
    plano TEXT NOT NULL DEFAULT 'mensal',          -- mensal | anual
    mensalidade REAL NOT NULL DEFAULT 199.90,
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER REFERENCES tenants(id),      -- NULL = superadmin da plataforma
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    papel TEXT NOT NULL DEFAULT 'recepcao',        -- superadmin | gerente | recepcao
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    nome TEXT NOT NULL,
    cpf TEXT DEFAULT '',
    telefone TEXT NOT NULL,
    aniversario TEXT DEFAULT '',                   -- MM-DD
    observacoes TEXT DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS barbeiros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    nome TEXT NOT NULL,
    telefone TEXT DEFAULT '',
    modelo TEXT NOT NULL DEFAULT 'comissao',       -- comissao | aluguel_cadeira
    percentual_comissao REAL NOT NULL DEFAULT 50,  -- usado no modelo comissao
    valor_aluguel REAL NOT NULL DEFAULT 0,         -- usado no modelo aluguel_cadeira (mensal)
    hora_inicio TEXT NOT NULL DEFAULT '09:00',
    hora_fim TEXT NOT NULL DEFAULT '19:00',
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS servicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    nome TEXT NOT NULL,
    preco REAL NOT NULL,
    duracao_min INTEGER NOT NULL DEFAULT 30,
    eh_combo INTEGER NOT NULL DEFAULT 0,
    ativo INTEGER NOT NULL DEFAULT 1
);

-- itens de um combo: aponta para os serviços simples que o compõem
CREATE TABLE IF NOT EXISTS combo_itens (
    combo_id INTEGER NOT NULL REFERENCES servicos(id) ON DELETE CASCADE,
    servico_id INTEGER NOT NULL REFERENCES servicos(id),
    PRIMARY KEY (combo_id, servico_id)
);

CREATE TABLE IF NOT EXISTS agendamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    barbeiro_id INTEGER NOT NULL REFERENCES barbeiros(id),
    inicio TEXT NOT NULL,                          -- ISO: YYYY-MM-DDTHH:MM
    fim TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'agendado',       -- agendado | confirmado | atrasado | atendido | pago | cancelado | no_show
    valor_total REAL NOT NULL DEFAULT 0,
    forma_pagamento TEXT DEFAULT '',
    recorrencia_id INTEGER REFERENCES recorrencias(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agendamento_servicos (
    agendamento_id INTEGER NOT NULL REFERENCES agendamentos(id) ON DELETE CASCADE,
    servico_id INTEGER NOT NULL REFERENCES servicos(id),
    preco REAL NOT NULL,                           -- preço congelado na hora da reserva
    PRIMARY KEY (agendamento_id, servico_id)
);

CREATE TABLE IF NOT EXISTS recorrencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    barbeiro_id INTEGER NOT NULL REFERENCES barbeiros(id),
    servico_id INTEGER NOT NULL REFERENCES servicos(id),
    frequencia TEXT NOT NULL,                      -- semanal | quinzenal | mensal | anual
    dia_semana INTEGER,                            -- 0=segunda ... 6=domingo (semanal/quinzenal)
    dia_mes INTEGER,                               -- 1..28 (mensal)
    data_base TEXT,                                -- YYYY-MM-DD (anual)
    hora TEXT NOT NULL,                            -- HH:MM
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mensagens_whatsapp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    cliente_id INTEGER REFERENCES clientes(id),
    agendamento_id INTEGER REFERENCES agendamentos(id),
    telefone TEXT NOT NULL,
    tipo TEXT NOT NULL,                            -- confirmacao | lembrete | aniversario | avulsa
    texto TEXT NOT NULL,
    agendada_para TEXT NOT NULL,                   -- quando deve ser disparada
    status TEXT NOT NULL DEFAULT 'pendente',       -- pendente | enviada | erro | cancelada
    resposta TEXT DEFAULT '',                      -- confirmar | cancelar | atrasar
    enviada_em TEXT
);

CREATE TABLE IF NOT EXISTS lancamentos_caixa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    data TEXT NOT NULL,                            -- YYYY-MM-DD
    tipo TEXT NOT NULL,                            -- entrada | saida
    categoria TEXT NOT NULL,                       -- servico | produto | aluguel_cadeira | comissao | despesa_fixa | despesa_variavel | imposto | outro
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    agendamento_id INTEGER REFERENCES agendamentos(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    nome TEXT NOT NULL,
    custo REAL NOT NULL DEFAULT 0,
    preco_venda REAL NOT NULL DEFAULT 0,
    quantidade REAL NOT NULL DEFAULT 0,
    estoque_minimo REAL NOT NULL DEFAULT 0,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS movimentos_estoque (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    produto_id INTEGER NOT NULL REFERENCES produtos(id),
    tipo TEXT NOT NULL,                            -- compra | venda | consumo | ajuste
    quantidade REAL NOT NULL,                      -- positivo entra, negativo sai
    valor_unitario REAL NOT NULL DEFAULT 0,
    data TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ag_tenant_inicio ON agendamentos(tenant_id, inicio);
CREATE INDEX IF NOT EXISTS idx_msg_status ON mensagens_whatsapp(tenant_id, status, agendada_para);
CREATE INDEX IF NOT EXISTS idx_caixa_data ON lancamentos_caixa(tenant_id, data);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def row(cur) -> dict | None:
    r = cur.fetchone()
    return dict(r) if r else None
