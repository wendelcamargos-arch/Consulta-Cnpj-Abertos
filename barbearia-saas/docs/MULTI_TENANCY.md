# Multi-tenancy

## Modelo

Banco compartilhado com discriminador `tenant_id` em toda tabela de negócio.
Não há isolamento "por convenção" solta: o escopo é aplicado por um mecanismo
central e comprovado por testes de acesso cruzado.

## Mecanismo central

1. O token de sessão carrega `tenant_id` assinado (HMAC) — `app/auth.py`.
2. Toda rota de negócio depende de `contexto_tenant`, que:
   - resolve o tenant do usuário (ou o header `X-Tenant-Id` para superadmin);
   - **bloqueia tenants suspensos** em cada requisição, não só no login.
3. Toda query dos routers filtra por `tenant_id=?` vindo exclusivamente desse
   contexto — nunca do corpo da requisição.
4. Recursos referenciados (barbeiro, serviço, cliente, voucher…) são revalidados
   contra o tenant do contexto antes do uso; id de outro tenant responde 404/422.

## Prova por teste (tests/test_tenancy.py)

- tenant A não lê dados de B (listagem e acesso direto por id);
- tenant A não altera nem exclui recursos de B;
- tenant A não usa barbeiro/serviço de B em um agendamento;
- suspensão corta sessões ativas e novos logins; reativação restaura;
- superadmin só opera um tenant declarando `X-Tenant-Id`.

## Limites conhecidos

- Isolamento é lógico (mesmo banco). Para exigência regulatória de isolamento
  físico, o desenho comporta migrar um tenant para schema/banco próprio.
- `whatsapp_events` é global por desenho (idempotência de webhook da Meta,
  que chega sem tenant); o roteamento ao tenant acontece pela mensagem original.
- Row-Level Security do PostgreSQL é candidata a segunda camada de defesa
  pós-piloto (hoje a única via de acesso ao banco é a aplicação).
