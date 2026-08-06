# 💈 Barbearia OS — White Label SaaS para Barbearias

Sistema operacional de **recorrência e redução de faltas** para barbearias:
agenda recorrente, confirmações pelo WhatsApp oficial (Meta Cloud API), gestão
de cadeiras e visão financeira (caixa por sessão, estoque com custo médio, DRE).

Multi-tenant white label: cada barbearia com marca própria; painel administrativo
da plataforma para operar os tenants.

## Estado

MVP tecnicamente apto a **piloto controlado** — não é lançamento público.
Pesquisa de mercado, posicionamento e plano de validação: `docs/MARKET_RESEARCH.md`,
`docs/COMPETITIVE_MATRIX.md`, `docs/PRODUCT_POSITIONING.md`.

## Stack

FastAPI · **PostgreSQL 16** (Alembic; SQLite apenas em teste unitário) ·
SPA vanilla JS · Docker Compose. Arquitetura: `docs/ARCHITECTURE.md`.

## Rodar (desenvolvimento)

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://barbearia:senha@localhost:5432/barbearia_dev
python -m alembic upgrade head
DEMO_MODE=1 python -m app.seed          # dados demo (proibido em produção)
uvicorn app.main:app --reload           # site em /, painel em /app
```

Ou com Docker: `cp .env.example .env` e `docker compose up -d --build`
(`docs/DEPLOYMENT.md`).

## Testes

```bash
python -m pytest tests/ -q                                          # SQLite (unitário)
DATABASE_URL=postgresql://barbearia:senha@localhost:5432/barbearia_test \
  python -m pytest tests/ -q --cov=app                              # suíte oficial
```

Cobrem: autenticação (rate limit, RBAC, recuperação de senha, seed bloqueado),
isolamento multi-tenant (leitura/escrita/exclusão cruzada, suspensão), agenda
(conflitos, concorrência no banco, bloqueios, dia fechado), recorrência (4
frequências, políticas pular/sugerir/pendência, 29/02), WhatsApp (fila, retry,
dead-letter, webhook com assinatura e idempotência, respostas), aniversário
(consentimento, voucher único/intransferível/validade), financeiro (pagamento
dividido/parcial, estorno, comissão, aluguel com contrato, sessão de caixa com
divergência, DRE) e estoque (custo médio, perda, mínimo).

## Documentação

| Tema | Arquivo |
|---|---|
| Arquitetura / Banco / Multi-tenancy | `docs/ARCHITECTURE.md` · `docs/DATABASE.md` · `docs/MULTI_TENANCY.md` |
| Segurança / LGPD | `docs/SECURITY.md` · `docs/LGPD.md` |
| WhatsApp (setup, templates, webhook) | `docs/WHATSAPP_META_SETUP.md` · `docs/WHATSAPP_TEMPLATE_CATALOG.md` · `docs/WHATSAPP_WEBHOOK_FLOW.md` |
| Operação | `docs/DEPLOYMENT.md` · `docs/BACKUP_AND_RESTORE.md` · `docs/PILOT_RUNBOOK.md` |
| Mercado | `docs/MARKET_RESEARCH.md` · `docs/COMPETITIVE_MATRIX.md` · `docs/PRODUCT_POSITIONING.md` |
