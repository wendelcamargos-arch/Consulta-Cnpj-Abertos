# LGPD — tratamento de dados pessoais

## Inventário de dados

| Dado | Onde | Finalidade | Base legal (LGPD art. 7º) |
|---|---|---|---|
| Nome, telefone do cliente | `clientes` | agendamento e lembretes | V (execução de contrato) |
| Aniversário (MM-DD) | `clientes` | campanha de aniversário | I (consentimento) |
| CPF (opcional) | `clientes` | identificação única e antifraude de voucher | V + IX (legítimo interesse) |
| Consentimentos | `customer_consents` | prova de opt-in de marketing/lembretes | I |
| E-mail/senha da equipe | `usuarios` | autenticação | V |
| Trilha de auditoria | `audit_logs` | segurança e responsabilização | IX |

## CPF — regras específicas

- **Finalidade**: impedir cadastro duplicado e fraude no resgate de vouchers
  (voucher é vinculado ao cliente; CPF ancora a identidade). Regra do owner:
  campo mantido no cadastro.
- **Validação**: dígitos verificadores; armazenado apenas dígitos.
- **Acesso**: papéis gerente/recepção do próprio tenant.
- **Retenção**: enquanto durar a relação com a barbearia.
- **Anonimização**: a pedido do titular, `nome/cpf/telefone/aniversario` são
  substituídos por valores anonimizados em até 30 dias, preservando lançamentos
  financeiros (obrigação legal) sem vínculo identificável.
- **Proibições**: CPF nunca aparece em logs, auditoria ou mensagens WhatsApp.

## Consentimento de marketing

Registrado por evento em `customer_consents` (tipo, concedido, origem, data) —
histórico completo, não flag sobrescrita. A campanha de aniversário só emite
voucher/mensagem com consentimento vigente (testado em `tests/test_aniversario.py`).
Revogação: novo registro com `concedido=0`, efeito imediato.

## Direitos do titular

Acesso/correção pela recepção (`/api/clientes`); histórico consultável
(`/{id}/historico`); revogação de consentimento; exclusão/anonimização conforme
acima. Encarregado: contato da plataforma na Política de Privacidade
(`static/privacidade.html`).

## Segurança aplicada

Ver SECURITY.md — isolamento por tenant testado, bcrypt, auditoria sem dados
sensíveis, HTTPS obrigatório em produção.
