# Catálogo de templates WhatsApp

Templates a registrar na Meta (categoria sugerida entre parênteses). O nome do
template usado fica gravado em `mensagens_whatsapp.template` para auditoria.

## confirmacao_agendamento (utility)

> Olá, {{1}}! 👋 Seu horário na {{2}} é às {{3}} ({{4}}). Pode confirmar?

Botões de resposta rápida: **CONFIRMAR** · **CANCELAR** · **VOU ATRASAR**
Disparo: `confirmacao_min` antes do horário (padrão 24h; configurável por tenant).

## lembrete_agendamento (utility)

> Olá, {{1}}! Lembrando: sua agenda na {{2}} está marcada para {{3}} às {{4}}. Até lá! ✂️

Disparo: `lembrete_min` antes (padrão 2h).

## aviso_final (utility)

> {{1}}, seu horário na {{2}} é daqui a pouco, às {{3}}. Estamos te esperando! 💈

Disparo: `aviso_min` antes (padrão 30min).

## aniversario_cliente (marketing)

> Feliz aniversário, {{1}}! 🎉 A {{2}} preparou um presente: {{3}}% de desconto.
> Código: {{4}}. Válido conforme regulamento.

Disparo: 08:00 (configurável) do dia do aniversário, **somente com consentimento
de marketing registrado**.

## Regras de interpretação de resposta (webhook)

| Resposta normalizada (sem acento, maiúscula) | Efeito |
|---|---|
| CONFIRMAR | agendamento → confirmado |
| CANCELAR | agendamento → cancelado |
| VOU ATRASAR / ATRASAR | agendamento → atrasado |
| qualquer outra coisa | pendência da recepção (`pendente_recepcao=1`), agendamento intacto |

## Observações

- Aprovação de template pela Meta leva de minutos a dias; planeje antes do piloto.
- Alterar o texto aqui exige atualizar o template na Meta e o gerador em
  `app/whatsapp_service.py` (TEMPLATES) juntos.
