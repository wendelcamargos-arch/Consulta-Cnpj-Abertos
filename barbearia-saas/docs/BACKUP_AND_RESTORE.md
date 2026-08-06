# Backup e restauração

## O que proteger

1. PostgreSQL (todos os dados de negócio).
2. `.env` (segredos — guardar em cofre, nunca no repositório).

## Backup

Diário, com retenção 30 dias (mínimo do piloto):

```bash
# docker compose
docker compose exec db pg_dump -U barbearia -Fc barbearia > backup_$(date +%F).dump
# fora do docker
pg_dump -Fc "$DATABASE_URL" > backup_$(date +%F).dump
```

Automatize via cron do host e copie para armazenamento externo (S3/B2/rclone).
Backup que nunca foi restaurado não é backup: ensaie a restauração antes do
go-live e depois mensalmente.

## Restauração

```bash
docker compose stop app
docker compose exec -T db pg_restore -U barbearia -d barbearia --clean --if-exists < backup_YYYY-MM-DD.dump
docker compose start app
curl -s localhost:8000/health/ready   # deve responder ok
```

Após restaurar, valide: login, agenda do dia, fila WhatsApp e DRE do mês.

## Perda parcial (linha/tabela)

Restaure o dump em um banco temporário e copie somente o necessário:

```bash
createdb -O barbearia restauracao_tmp
pg_restore -d restauracao_tmp backup.dump
psql -c "INSERT INTO ... SELECT ... FROM restauracao_tmp..."
```

## RPO/RTO do piloto

- RPO: até 24h (backup diário). Se inaceitável para a barbearia piloto,
  ative WAL archiving.
- RTO alvo: < 1h com o runbook acima.
