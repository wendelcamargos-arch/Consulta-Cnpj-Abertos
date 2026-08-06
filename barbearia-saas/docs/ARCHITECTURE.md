# Arquitetura

## Visão geral

Monolito modular FastAPI servindo API JSON + frontend estático, com PostgreSQL
como banco operacional. Escolha deliberada para o estágio de piloto: um processo,
um banco, um deploy — com fronteiras de módulo claras para extrair serviços
depois, se a escala exigir.

```
static/site.html         página pública comercial (/)
static/index.html+app.js painel SPA (/app)
app/main.py              bootstrap, middlewares, health, CORS
app/db.py                camada de acesso (PostgreSQL/psycopg · SQLite p/ teste)
app/schema.py            DDL fonte única, renderizada por dialeto
app/auth.py              bcrypt, token HMAC, RBAC, rate limit, reset de senha
app/audit.py             trilha de auditoria
app/util.py              relógio por tenant (zoneinfo), tenant_settings
app/whatsapp_service.py  providers (Meta Cloud API | simulado), fila, retry
app/routers/*.py         um router por domínio (13 módulos)
migrations/              Alembic (0001 = schema completo)
```

## Decisões e trade-offs

| Decisão | Motivo | Custo aceito |
|---|---|---|
| Monolito modular | 1 pessoa mantém; deploy único; latência zero entre módulos | extração futura exige disciplina de fronteira |
| SQL parametrizado direto (sem ORM) | queries auditáveis, sem mágica de sessão | migrações de schema manuais (mitigado pelo Alembic) |
| Datas como TEXT ISO-8601 | idêntico nos 2 dialetos, ordenável | constraint de intervalo exige função imutável (`imm_ts`) |
| Fila WhatsApp no banco | sem broker; auditável; retry simples | throughput limitado (suficiente p/ piloto) |
| Processamento por cron HTTP | sem worker dedicado | latência de até 1 min no disparo |

## Fluxo do balcão

login → agenda (lock por barbeiro + constraint GiST) → fila WhatsApp
(3 momentos configuráveis) → webhook de resposta → atendimento → fechamento
(pagamentos divididos/parciais, voucher, produtos) → caixa/comissão → DRE.

## Pontos de extensão

- `ProvedorMensageria` (whatsapp_service.py): novo canal = nova subclasse.
- Gateway de pagamento: interface a introduzir em `payments` (fora do escopo do MVP;
  o fechamento já registra formas/valores por transação).
- Extração de serviço: cada router depende só de `db/auth/util/audit` — um
  serviço candidato leva consigo suas tabelas.
