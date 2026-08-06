"""Schema do banco — fonte única, renderizada para PostgreSQL e SQLite.

PostgreSQL é o banco operacional. SQLite existe apenas para teste unitário.
Datas/horas são armazenadas como TEXT ISO-8601 (YYYY-MM-DDTHH:MM[:SS]) — ordenável
lexicograficamente nos dois dialetos; o timezone de exibição é por tenant.

Proteção contra dupla reserva concorrente (PostgreSQL):
  - lock pessimista por barbeiro (SELECT ... FOR UPDATE) na criação; e
  - constraint de exclusão GiST sobre o intervalo (quando btree_gist disponível).
"""

_TEMPLATE = """
CREATE TABLE IF NOT EXISTS tenants (
    id {pk},
    nome TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    cor_primaria TEXT NOT NULL DEFAULT '#C9A227',
    logo_url TEXT DEFAULT '',
    telefone_whatsapp TEXT DEFAULT '',
    timezone TEXT NOT NULL DEFAULT 'America/Sao_Paulo',
    plano TEXT NOT NULL DEFAULT 'mensal',
    mensalidade {money} NOT NULL DEFAULT 199.90,
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT {agora}
);

CREATE TABLE IF NOT EXISTS tenant_settings (
    id {pk},
    tenant_id INTEGER NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
    confirmacao_min INTEGER NOT NULL DEFAULT 1440,     -- confirmação principal: 24h antes
    lembrete_min INTEGER NOT NULL DEFAULT 120,         -- lembrete intermediário: 2h antes
    aviso_min INTEGER NOT NULL DEFAULT 30,             -- aviso final: 30min antes
    politica_recorrencia TEXT NOT NULL DEFAULT 'pendencia',  -- pular | sugerir | pendencia
    dias_fechados TEXT NOT NULL DEFAULT '[]'           -- JSON: dias da semana (0-6) e datas 'YYYY-MM-DD'
);

CREATE TABLE IF NOT EXISTS usuarios (
    id {pk},
    tenant_id INTEGER REFERENCES tenants(id),
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    papel TEXT NOT NULL DEFAULT 'recepcao' CHECK (papel IN ('superadmin','gerente','recepcao')),
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT {agora}
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id {pk},
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expira_em TEXT NOT NULL,
    usado INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL DEFAULT {agora}
);

CREATE TABLE IF NOT EXISTS clientes (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    nome TEXT NOT NULL,
    cpf TEXT DEFAULT '',
    telefone TEXT NOT NULL,
    aniversario TEXT DEFAULT '',
    observacoes TEXT DEFAULT '',
    criado_em TEXT NOT NULL DEFAULT {agora}
);

CREATE TABLE IF NOT EXISTS customer_consents (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL,                                -- marketing | lembretes
    concedido INTEGER NOT NULL,
    origem TEXT DEFAULT 'recepcao',
    registrado_em TEXT NOT NULL DEFAULT {agora}
);

CREATE TABLE IF NOT EXISTS barbeiros (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    nome TEXT NOT NULL,
    telefone TEXT DEFAULT '',
    modelo TEXT NOT NULL DEFAULT 'comissao' CHECK (modelo IN ('comissao','aluguel_cadeira')),
    percentual_comissao {money} NOT NULL DEFAULT 50,
    valor_aluguel {money} NOT NULL DEFAULT 0,
    hora_inicio TEXT NOT NULL DEFAULT '09:00',
    hora_fim TEXT NOT NULL DEFAULT '19:00',
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS barber_blocks (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    barbeiro_id INTEGER NOT NULL REFERENCES barbeiros(id) ON DELETE CASCADE,
    inicio TEXT NOT NULL,
    fim TEXT NOT NULL,
    motivo TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS chairs (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    nome TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS chair_contracts (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    chair_id INTEGER NOT NULL REFERENCES chairs(id),
    barbeiro_id INTEGER NOT NULL REFERENCES barbeiros(id),
    valor_mensal {money} NOT NULL,
    inicio TEXT NOT NULL,
    fim TEXT,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS servicos (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    nome TEXT NOT NULL,
    preco {money} NOT NULL CHECK (preco >= 0),
    duracao_min INTEGER NOT NULL DEFAULT 30 CHECK (duracao_min > 0),
    eh_combo INTEGER NOT NULL DEFAULT 0,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS combo_itens (
    combo_id INTEGER NOT NULL REFERENCES servicos(id) ON DELETE CASCADE,
    servico_id INTEGER NOT NULL REFERENCES servicos(id),
    PRIMARY KEY (combo_id, servico_id)
);

CREATE TABLE IF NOT EXISTS recorrencias (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    barbeiro_id INTEGER NOT NULL REFERENCES barbeiros(id),
    servico_id INTEGER NOT NULL REFERENCES servicos(id),
    frequencia TEXT NOT NULL CHECK (frequencia IN ('semanal','quinzenal','mensal','anual')),
    dia_semana INTEGER,
    dia_mes INTEGER,
    data_base TEXT,
    hora TEXT NOT NULL,
    data_inicio TEXT,
    data_fim TEXT,
    max_ocorrencias INTEGER,
    politica TEXT,                                     -- NULL = usa tenant_settings.politica_recorrencia
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT {agora}
);

CREATE TABLE IF NOT EXISTS agendamentos (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    barbeiro_id INTEGER NOT NULL REFERENCES barbeiros(id),
    inicio TEXT NOT NULL,
    fim TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'agendado'
        CHECK (status IN ('agendado','confirmado','atrasado','atendido','pago','pago_parcial','cancelado','no_show')),
    valor_total {money} NOT NULL DEFAULT 0,
    desconto {money} NOT NULL DEFAULT 0,
    forma_pagamento TEXT DEFAULT '',
    recorrencia_id INTEGER REFERENCES recorrencias(id),
    criado_em TEXT NOT NULL DEFAULT {agora},
    CHECK (fim > inicio)
);

CREATE TABLE IF NOT EXISTS agendamento_servicos (
    agendamento_id INTEGER NOT NULL REFERENCES agendamentos(id) ON DELETE CASCADE,
    servico_id INTEGER NOT NULL REFERENCES servicos(id),
    preco {money} NOT NULL,
    PRIMARY KEY (agendamento_id, servico_id)
);

CREATE TABLE IF NOT EXISTS recurrence_occurrences (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    recorrencia_id INTEGER NOT NULL REFERENCES recorrencias(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    hora TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('gerada','pulada','sugerida','pendente','cancelada')),
    motivo TEXT DEFAULT '',
    agendamento_id INTEGER REFERENCES agendamentos(id),
    criado_em TEXT NOT NULL DEFAULT {agora},
    UNIQUE (recorrencia_id, data)
);

CREATE TABLE IF NOT EXISTS mensagens_whatsapp (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    cliente_id INTEGER REFERENCES clientes(id),
    agendamento_id INTEGER REFERENCES agendamentos(id),
    telefone TEXT NOT NULL,
    tipo TEXT NOT NULL,                                -- confirmacao | lembrete | aviso_final | aniversario | avulsa
    template TEXT DEFAULT '',
    texto TEXT NOT NULL,
    agendada_para TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente'
        CHECK (status IN ('pendente','enviada','entregue','lida','erro','falha_final','cancelada')),
    provider_msg_id TEXT DEFAULT '',
    tentativas INTEGER NOT NULL DEFAULT 0,
    proximo_retry TEXT,
    resposta TEXT DEFAULT '',
    pendente_recepcao INTEGER NOT NULL DEFAULT 0,
    enviada_em TEXT
);

CREATE TABLE IF NOT EXISTS whatsapp_events (
    id {pk},
    evento_id TEXT NOT NULL UNIQUE,                    -- idempotência de webhook
    tipo TEXT NOT NULL,
    payload TEXT NOT NULL,
    processado INTEGER NOT NULL DEFAULT 0,
    recebido_em TEXT NOT NULL DEFAULT {agora}
);

CREATE TABLE IF NOT EXISTS birthday_campaigns (
    id {pk},
    tenant_id INTEGER NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
    ativo INTEGER NOT NULL DEFAULT 1,
    hora_envio TEXT NOT NULL DEFAULT '08:00',
    percentual {money} NOT NULL DEFAULT 10 CHECK (percentual > 0 AND percentual <= 100),
    servico_id INTEGER REFERENCES servicos(id),        -- NULL = qualquer serviço
    validade_dias INTEGER NOT NULL DEFAULT 30,
    cumulativo INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS birthday_vouchers (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    ano INTEGER NOT NULL,
    codigo TEXT NOT NULL UNIQUE,
    percentual {money} NOT NULL,
    servico_id INTEGER REFERENCES servicos(id),
    valido_de TEXT NOT NULL,
    valido_ate TEXT NOT NULL,
    emitido_em TEXT NOT NULL DEFAULT {agora},
    resgatado_em TEXT,
    resgatado_por INTEGER REFERENCES usuarios(id),
    agendamento_id INTEGER REFERENCES agendamentos(id),
    cancelado INTEGER NOT NULL DEFAULT 0,
    UNIQUE (tenant_id, cliente_id, ano)                -- proteção contra emissão duplicada
);

CREATE TABLE IF NOT EXISTS commissions (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    agendamento_id INTEGER NOT NULL REFERENCES agendamentos(id),
    barbeiro_id INTEGER NOT NULL REFERENCES barbeiros(id),
    percentual {money} NOT NULL,
    valor {money} NOT NULL,
    criado_em TEXT NOT NULL DEFAULT {agora}
);

CREATE TABLE IF NOT EXISTS cash_sessions (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    status TEXT NOT NULL DEFAULT 'aberta' CHECK (status IN ('aberta','fechada')),
    aberto_por INTEGER NOT NULL REFERENCES usuarios(id),
    aberto_em TEXT NOT NULL DEFAULT {agora},
    valor_inicial {money} NOT NULL DEFAULT 0,
    fechado_por INTEGER REFERENCES usuarios(id),
    fechado_em TEXT,
    valor_esperado {money},
    valor_contado {money},
    divergencia {money}
);

CREATE TABLE IF NOT EXISTS payments (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    agendamento_id INTEGER NOT NULL REFERENCES agendamentos(id),
    sessao_id INTEGER REFERENCES cash_sessions(id),
    forma TEXT NOT NULL CHECK (forma IN ('dinheiro','pix','debito','credito','outro')),
    valor {money} NOT NULL CHECK (valor > 0),
    status TEXT NOT NULL DEFAULT 'confirmado' CHECK (status IN ('confirmado','estornado')),
    criado_em TEXT NOT NULL DEFAULT {agora},
    estornado_em TEXT,
    estornado_por INTEGER REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS lancamentos_caixa (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    sessao_id INTEGER REFERENCES cash_sessions(id),
    data TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('entrada','saida')),
    categoria TEXT NOT NULL CHECK (categoria IN
        ('servico','produto','aluguel_cadeira','comissao','despesa_fixa','despesa_variavel',
         'imposto','estorno','desconto','abertura','reforco','sangria','cmv','outro')),
    descricao TEXT NOT NULL,
    valor {money} NOT NULL,
    agendamento_id INTEGER REFERENCES agendamentos(id),
    criado_em TEXT NOT NULL DEFAULT {agora}
);

CREATE TABLE IF NOT EXISTS produtos (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    nome TEXT NOT NULL,
    custo {money} NOT NULL DEFAULT 0,
    custo_medio {money} NOT NULL DEFAULT 0,            -- custo médio móvel (docs/DATABASE.md)
    preco_venda {money} NOT NULL DEFAULT 0,
    quantidade {money} NOT NULL DEFAULT 0,
    estoque_minimo {money} NOT NULL DEFAULT 0,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS movimentos_estoque (
    id {pk},
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    produto_id INTEGER NOT NULL REFERENCES produtos(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('compra','venda','consumo','ajuste','perda')),
    quantidade {money} NOT NULL,
    valor_unitario {money} NOT NULL DEFAULT 0,
    custo_unitario {money} NOT NULL DEFAULT 0,         -- custo médio no momento do movimento
    data TEXT NOT NULL DEFAULT {agora}
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id {pk},
    tenant_id INTEGER REFERENCES tenants(id),
    usuario_id INTEGER REFERENCES usuarios(id),
    acao TEXT NOT NULL,
    entidade TEXT DEFAULT '',
    entidade_id INTEGER,
    detalhe TEXT DEFAULT '',                           -- nunca gravar CPF, senha ou token
    criado_em TEXT NOT NULL DEFAULT {agora}
);

CREATE INDEX IF NOT EXISTS idx_ag_tenant_inicio ON agendamentos(tenant_id, inicio);
CREATE INDEX IF NOT EXISTS idx_ag_barbeiro ON agendamentos(barbeiro_id, inicio);
CREATE INDEX IF NOT EXISTS idx_msg_status ON mensagens_whatsapp(tenant_id, status, agendada_para);
CREATE INDEX IF NOT EXISTS idx_msg_provider ON mensagens_whatsapp(provider_msg_id);
CREATE INDEX IF NOT EXISTS idx_caixa_data ON lancamentos_caixa(tenant_id, data);
CREATE INDEX IF NOT EXISTS idx_clientes_tenant ON clientes(tenant_id, nome);
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_logs(tenant_id, criado_em);
CREATE INDEX IF NOT EXISTS idx_vouchers_cliente ON birthday_vouchers(tenant_id, cliente_id);
CREATE INDEX IF NOT EXISTS idx_payments_ag ON payments(agendamento_id);
"""

# Reforço PostgreSQL: constraint de exclusão impede dupla reserva mesmo sob
# concorrência de processos. Requer btree_gist; se o usuário do banco não puder
# criar a extensão, o lock pessimista da aplicação continua protegendo.
_PG_EXTRA = """
DO $do$ BEGIN
  BEGIN
    CREATE EXTENSION IF NOT EXISTS btree_gist;
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
END $do$;

CREATE OR REPLACE FUNCTION imm_ts(t TEXT) RETURNS timestamp
LANGUAGE sql IMMUTABLE AS 'SELECT t::timestamp';

DO $do$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'btree_gist')
     AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'agendamentos_sem_sobreposicao') THEN
    ALTER TABLE agendamentos ADD CONSTRAINT agendamentos_sem_sobreposicao
      EXCLUDE USING gist (
        barbeiro_id WITH =,
        tsrange(imm_ts(inicio), imm_ts(fim)) WITH &&
      ) WHERE (status NOT IN ('cancelado','no_show'));
  END IF;
END $do$;
"""


def schema_postgres() -> str:
    ddl = _TEMPLATE.format(
        pk="BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
        money="DOUBLE PRECISION",
        agora="to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS')")
    return ddl + _PG_EXTRA


def schema_sqlite() -> str:
    return "PRAGMA foreign_keys=ON;\n" + _TEMPLATE.format(
        pk="INTEGER PRIMARY KEY AUTOINCREMENT",
        money="REAL",
        agora="(strftime('%Y-%m-%dT%H:%M:%S','now'))")
