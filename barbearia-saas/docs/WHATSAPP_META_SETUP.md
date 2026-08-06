# WhatsApp Business Cloud API — configuração (Meta)

A automação usa exclusivamente a **API oficial** (Cloud API). Não há e não deve
haver automação por WhatsApp Web/QR Code — viola os termos da Meta e arrisca o
banimento do número da barbearia. O link `wa.me` existe apenas como conveniência
de disparo manual pela recepção.

## Passo a passo

1. **Meta Business Portfolio**: crie/possua um portfólio verificado em
   business.facebook.com.
2. **App Meta for Developers** (developers.facebook.com): tipo Business, adicione
   o produto *WhatsApp*.
3. **Número**: registre o número da barbearia (não pode estar ativo num app
   WhatsApp comum). Anote o **Phone Number ID** e o **WhatsApp Business Account ID**.
4. **Token permanente**: crie um System User no Business Manager com permissão
   `whatsapp_business_messaging`, gere o token e guarde-o como segredo.
5. **Webhook**: em App → WhatsApp → Configuration:
   - Callback URL: `https://SEU_DOMINIO/api/whatsapp/webhook`
   - Verify token: o mesmo valor de `META_WHATSAPP_VERIFY_TOKEN`
   - Assine os campos `messages` (inclui statuses).
6. **App Secret**: em App Settings → Basic, copie o App Secret
   (`META_APP_SECRET`) — usado para validar a assinatura dos webhooks.
7. **Templates**: registre e aguarde aprovação dos templates do catálogo
   (WHATSAPP_TEMPLATE_CATALOG.md). Mensagens ativas fora da janela de 24h só
   podem usar template aprovado.

## Variáveis de ambiente

```
META_WHATSAPP_ACCESS_TOKEN=...        # token permanente do System User
META_WHATSAPP_PHONE_NUMBER_ID=...
META_WHATSAPP_BUSINESS_ACCOUNT_ID=...
META_WHATSAPP_VERIFY_TOKEN=...        # escolhido por você, igual ao painel Meta
META_APP_SECRET=...                   # App Secret do app Meta
```

Sem `META_WHATSAPP_ACCESS_TOKEN`/`PHONE_NUMBER_ID`, o sistema opera com o
provider **simulado** (fila auditável, nada sai para a rede) — modo correto para
desenvolvimento e homologação.

## Processamento da fila

Agende um cron para `POST /api/whatsapp/processar` (a cada minuto) autenticado
com um usuário de recepção/gerente do tenant. Retry automático com backoff
1/5/15 min; após 4 tentativas a mensagem vai a `falha_final` (dead-letter visível
na tela WhatsApp).

## Custos (verificar tabela vigente da Meta)

A Cloud API cobra por conversa iniciada (categoria utility/marketing varia por
país). Confirme os valores atuais em business.whatsapp.com/products/platform-pricing
antes de precificar o plano — não asuma valores desta doc como atuais.
