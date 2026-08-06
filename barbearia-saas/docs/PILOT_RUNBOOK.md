# Runbook do piloto controlado

## Objetivo

Validar com 1–5 barbearias reais: redução de no-show, adoção da recorrência e
disposição a pagar — antes de qualquer lançamento público.

## Semana 0 — preparação

- [ ] Deploy conforme DEPLOYMENT.md (checklist de go-live completo).
- [ ] Templates WhatsApp aprovados; webhook verificado.
- [ ] Backup agendado e restauração ensaiada.
- [ ] Onboarding da barbearia piloto (`POST /api/onboarding`) com horários,
      barbeiros, serviços e usuários reais.
- [ ] Treinamento de 30 min com a recepção (agendar, fechar conta, abrir/fechar caixa).

## Operação diária

| Quando | Quem | O quê |
|---|---|---|
| Abertura | recepção | abrir sessão de caixa com fundo de troco |
| Contínuo | sistema | cron dispara fila WhatsApp a cada minuto |
| Contínuo | recepção | resolver pendências (`fila?pendencia=1`) e atrasos |
| Fechamento | recepção | fechar sessão contando a gaveta; anotar divergência |
| Semanal | gerente | gerar recorrências (`/gerar`), revisar KPIs e DRE parcial |
| Dia 1º | gerente | campanha de aniversário do mês; cobrar aluguéis de cadeira |

## Incidentes

| Sintoma | Ação |
|---|---|
| `/health/ready` 503 | verificar container do banco; `docker compose logs db` |
| Mensagens em `falha_final` | checar validade do token Meta; reprocessar após corrigir |
| Webhook sem eventos | reverificar assinatura/verify token no painel Meta |
| Divergência de caixa recorrente | auditoria da sessão (`/api/caixa/sessoes` + audit_logs) |
| Suspeita de fraude em voucher | cancelar voucher (auditado) e revisar `audit_logs` |

## Métricas de sucesso do piloto (4 semanas)

1. Taxa de no-show antes × depois (KPI `taxa_no_show_pct`).
2. % da agenda coberta por recorrência.
3. Taxa de resposta às confirmações WhatsApp.
4. Divergência média de caixa.
5. NPS verbal do dono + disposição a pagar (proposta de preço ancorada na
   pesquisa — docs/PRODUCT_POSITIONING.md).

## Critério de GO para lançamento

≥3 barbearias operando 4 semanas, no-show reduzido de forma mensurável,
nenhuma perda de dados, e ≥2 donos aceitando pagar o preço proposto.
