# Fluxo do webhook WhatsApp

## Verificação (GET /api/whatsapp/webhook)

A Meta chama com `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge`.
Se o token confere com `META_WHATSAPP_VERIFY_TOKEN`, respondemos o challenge
em texto puro. Sem variável configurada → 503.

## Eventos (POST /api/whatsapp/webhook)

1. **Assinatura**: `X-Hub-Signature-256 = sha256=HMAC(app_secret, corpo_bruto)`.
   Inválida → 403. Produção sem `META_APP_SECRET` → 503.
2. **Idempotência**: cada status/mensagem gera `evento_id`
   (`status:<wamid>:<status>` / `msg:<wamid>`) gravado com UNIQUE em
   `whatsapp_events`. Evento repetido → contado como duplicado e ignorado.
3. **Statuses** (`sent`/`delivered`/`read`/`failed`) atualizam
   `mensagens_whatsapp.status` pelo `provider_msg_id`. Eventos fora de ordem não
   rebaixam estado (ex.: `delivered` depois de `read` é ignorado).
4. **Mensagens do cliente**: texto ou botão é normalizado e interpretado
   (CONFIRMAR/CANCELAR/VOU ATRASAR). A resposta é aplicada à última confirmação
   enviada para aquele telefone e reflete no status do agendamento. Resposta
   ambígua marca `pendente_recepcao=1` — a recepção vê a fila em
   `GET /api/whatsapp/fila?pendencia=1` e resolve manualmente
   (`POST /api/whatsapp/{id}/resposta`).

## Estados da mensagem

```
pendente ──envio ok──▶ enviada ──webhook──▶ entregue ──▶ lida
   │ envio falha                          (failed)──▶ erro
   ▼
  erro ──backoff 1/5/15min──▶ reenvio ──4ª falha──▶ falha_final (dead-letter)
cancelada (agendamento cancelado/reagendado antes do envio)
```

## Roteamento multi-tenant

O webhook da Meta não traz o tenant. O vínculo é feito pela mensagem de
confirmação original (telefone → última confirmação aguardando resposta), que
carrega `tenant_id`. Deploys com um número por barbearia devem armazenar o
`phone_number_id` por tenant — evolução prevista, registrada como limitação atual.

## Testes

`tests/test_whatsapp.py` cobre: verificação, assinatura inválida/válida,
duplicidade, ordem de eventos, retry até dead-letter e as quatro interpretações
de resposta.
