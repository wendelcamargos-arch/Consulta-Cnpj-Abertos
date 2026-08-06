# Banco de dados

PostgreSQL 16 é o banco operacional. SQLite é permitido apenas em teste unitário
isolado (o conftest usa arquivo temporário). Em produção `DATABASE_URL` é
obrigatória e a aplicação recusa subir sem PostgreSQL (`app/main.py`, lifespan).

## Migrations

```bash
python -m alembic upgrade head      # aplica
python -m alembic downgrade -1      # reverte
```

`migrations/versions/0001_schema_inicial.py` renderiza `app/schema.py` no dialeto
da conexão. Pré-requisito PostgreSQL: extensão `btree_gist` (criada pelo
`scripts/pg-init.sql` no docker-compose, ou manualmente por um superusuário).

## Entidades (27)

tenants · tenant_settings · usuarios · password_reset_tokens · clientes ·
customer_consents · barbeiros · barber_blocks · chairs · chair_contracts ·
servicos · combo_itens · recorrencias · recurrence_occurrences · agendamentos ·
agendamento_servicos · mensagens_whatsapp · whatsapp_events · birthday_campaigns ·
birthday_vouchers · commissions · cash_sessions · payments · lancamentos_caixa ·
produtos · movimentos_estoque · audit_logs

Toda entidade de negócio da barbearia carrega `tenant_id` (ver MULTI_TENANCY.md).

## Integridade

- FKs em todas as relações; CHECKs de domínio (status, categorias, formas de pagamento).
- UNIQUEs: `tenants.slug`, `usuarios.email`, `whatsapp_events.evento_id`,
  `birthday_vouchers.codigo`, `birthday_vouchers(tenant, cliente, ano)`,
  `recurrence_occurrences(recorrencia, data)`.
- **Anti-dupla-reserva** (PostgreSQL): constraint `agendamentos_sem_sobreposicao`
  — `EXCLUDE USING gist (barbeiro_id WITH =, tsrange(imm_ts(inicio), imm_ts(fim)) WITH &&)`
  para status ativos; somada ao `SELECT ... FOR UPDATE` do barbeiro na criação.
  Testada com escrita concorrente em `tests/test_agenda.py`.

## Convenções de valor

- Datas/horas: TEXT ISO-8601 no fuso do tenant (`tenants.timezone`, zoneinfo).
- Dinheiro: DOUBLE PRECISION, arredondado a 2 casas na aplicação (gerencial, não contábil).
- **Custo médio móvel** (estoque): a cada compra,
  `novo = (qtd_atual*custo_medio + qtd_compra*custo_compra) / qtd_total`;
  saídas gravam `custo_unitario` vigente no movimento — base do CMV no DRE.

## DRE (regime de caixa, gerencial)

Receita bruta (servico+produto+aluguel_cadeira+outro) − descontos − estornos −
impostos = receita líquida; − comissões − CMV − despesas variáveis = margem de
contribuição; − despesas fixas − outras = resultado. Categorias de sessão
(abertura/reforco/sangria) ficam fora do DRE por serem movimentação, não resultado.
