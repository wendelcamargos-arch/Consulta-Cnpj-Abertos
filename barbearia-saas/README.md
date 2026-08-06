# 💈 Sistema White Label SaaS para Barbearia

Aplicação web multi-tenant para gestão de barbearias, construída a partir da pesquisa
de mercado do setor: agendamentos confusos, alto no-show, cadastro incompleto,
ausência de recorrência e gestão fraca de caixa/estoque/DRE.

## Módulos (MVP prioritário do infográfico ✔)

| Módulo | O que faz |
|---|---|
| **Agenda Inteligente** | Agendamento por barbeiro, serviço e horário; detecção de conflito; fluxo agendado → confirmado → atendido → pago |
| **WhatsApp Automação** | Confirmação 30 min antes, lembrete na véspera, campanha de aniversário; fila auditável; integração WhatsApp Cloud API (ou modo simulado + link wa.me) |
| **CRM do Cliente** | Nome, CPF (validado), telefone, aniversário, histórico de visitas |
| **Recorrência** | Reservas semanais, quinzenais, mensais e anuais; geração automática dos próximos horários |
| **Financeiro (Caixa)** | Entradas/saídas por categoria; lançamentos automáticos no fechamento do atendimento |
| **Estoque** | Produtos com custo/venda, movimentos, alerta de estoque mínimo, venda no fechamento |
| **Gestão de Cadeiras** | Barbeiro por comissão (% configurável) ou aluguel de cadeira (valor fixo mensal lançado no caixa) |
| **Combos** | Pacotes de serviços com preço fechado e duração somada |
| **Relatórios** | DRE gerencial mensal, desempenho por barbeiro, KPIs (no-show, ticket médio, taxa de confirmação) |
| **White Label** | Cada barbearia com nome, cor e logo próprios; painel administrativo da plataforma (tenants, MRR, suspensão) |

## Arquitetura

- **Backend:** FastAPI modular — um router por domínio (`app/routers/`), isolamento
  multi-tenant por `tenant_id` em toda tabela de negócio, autenticação por token
  HMAC com papéis (`superadmin` / `gerente` / `recepcao`).
- **Banco:** SQLite (WAL) — zero configuração para rodar; a camada `app/db.py`
  centraliza o acesso e a migração para Postgres é direta (mesmo SQL parametrizado).
- **Frontend:** SPA vanilla JS servida pelo próprio backend (`static/`), tema
  preto/dourado com cor primária personalizável por tenant.

## Rodar

```bash
pip install fastapi "uvicorn[standard]"
python -m app.seed                      # dados de demonstração
uvicorn app.main:app --reload           # http://localhost:8000
```

Logins de demonstração:

| Papel | Login | Senha |
|---|---|---|
| Plataforma (admin) | admin@plataforma.com | admin123 |
| Gerente Barbearia Prime | gerente@prime.com | gerente123 |
| Recepção Barbearia Prime | recepcao@prime.com | recepcao123 |

## WhatsApp em produção

Defina as variáveis e a fila passa a disparar de verdade pela Cloud API da Meta:

```bash
export META_WA_TOKEN="..."       # token permanente do app Meta
export META_WA_PHONE_ID="..."    # phone number ID
```

Agende `POST /api/whatsapp/processar` num cron (a cada minuto). Sem credenciais,
o sistema simula o envio e oferece o link `wa.me` para disparo manual pela recepção.

> ⚠️ Templates de mensagem ativa (fora da janela de 24h) precisam ser aprovados
> pela Meta antes do uso em produção.

## Segurança e LGPD

- Senhas com hash salgado; tokens expiram em 12h.
- CPF validado por dígito verificador e armazenado apenas com finalidade de cadastro.
- Dados isolados por tenant em todas as queries.
- Em produção: defina `BARBEARIA_SECRET`, use HTTPS e faça backup do banco
  (`BARBEARIA_DB` aponta o caminho do arquivo).

## Testes

```bash
pip install pytest httpx
pytest tests/ -v
```
