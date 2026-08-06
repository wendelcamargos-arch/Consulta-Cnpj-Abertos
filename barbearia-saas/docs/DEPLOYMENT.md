# Deploy

## Docker Compose (recomendado para o piloto)

```bash
cp .env.example .env         # preencha BARBEARIA_SECRET e credenciais Meta
docker compose up -d --build
docker compose ps            # health checks: db e app devem ficar healthy
```

O container da aplicação roda `alembic upgrade head` antes do uvicorn; o
`scripts/pg-init.sql` cria a extensão `btree_gist` na primeira subida do banco.

## Variáveis obrigatórias em produção

| Variável | Efeito se ausente |
|---|---|
| `APP_ENV=production` | ativa os travamentos de produção |
| `DATABASE_URL` (postgresql://) | app recusa subir |
| `BARBEARIA_SECRET` | app recusa subir |
| `ALLOWED_ORIGINS` | nenhuma origem cruzada é aceita |
| `META_*` | fila opera em modo simulado; webhook responde 503 |

Em produção o `/docs` (Swagger) fica desabilitado.

## Cron

- `POST /api/whatsapp/processar` — a cada minuto (dispara fila + retries).
- Campanha de aniversário: `POST /api/aniversario/gerar?mes=N` no dia 1º de cada mês.

## Health checks

- `GET /health/live` — processo vivo.
- `GET /health/ready` — banco acessível (503 caso contrário). Use no orquestrador.

## Atualização de versão

```bash
git pull && docker compose build app && docker compose up -d app
# migrations rodam automaticamente na subida
```

Rollback: `docker compose run --rm app python -m alembic downgrade -1` e subir a
imagem anterior. Faça backup antes de qualquer migração (BACKUP_AND_RESTORE.md).

## Checklist de go-live do piloto

1. `.env` completo, `DEMO_MODE` ausente.
2. HTTPS na frente (reverse proxy com certificado).
3. Backup agendado e restauração ENSAIADA.
4. Templates WhatsApp aprovados pela Meta.
5. Webhook verificado no painel Meta.
6. Onboarding da barbearia executado (POST /api/onboarding).
7. `GET /health/ready` retornando ok.
