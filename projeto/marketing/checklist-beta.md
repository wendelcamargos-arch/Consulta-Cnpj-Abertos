# Checklist de homologação beta fechada

## 1. Fluxo principal
- [x] A aplicação sobe sem falhas críticas.
- [x] O endpoint /search responde com 200 e mensagem clara em caso de zero resultados.
- [x] O endpoint /export/excel e /export/csv estão disponíveis para uso.
- [x] A interface permite preencher período, UF e município e disparar a pesquisa.
- [x] A interface exibe mensagem clara quando não há resultados.

## 2. Validação de risco
- [x] Validação de datas e intervalo máximo funcionando.
- [x] Validação de limite e parâmetros obrigatórios funcionando.
- [x] Base estável para pequenas consultas de teste.
- [ ] Validar com 10 escritórios reais em ambiente controlado.
- [ ] Confirmar se os campos exportados atendem às necessidades do time comercial.

## 3. Itens obrigatórios antes do beta
- [x] Mensagens de erro/sem resultado mais claras para o usuário.
- [x] Fluxo de busca e exportação alinhado ao backend real.
- [ ] Definir um processo simples de suporte para os primeiros usuários.
- [ ] Criar um canal de recebimento de bugs e pedidos de ajuste.

## 4. Melhorias para versão 1.1
- [x] Adicionar paginação real no backend para navegação mais ampla (page/page_size/offset).
- [ ] Melhorar mapeamento de colunas para exportação.
- [x] Incluir filtros mais completos compatíveis com a base (todos os filtros do
      SearchRequest implementados no SQL — ver `docs/filtros.md`).
- [ ] Adicionar autenticação/controle de acesso para uso comercial.

## 5. Endurecimento para o beta (esta rodada)
- [x] Caminho do DuckDB unificado numa fonte única de verdade que respeita
      `CNPJ_DATABASE_FILE` (config/settings.py). O setting não é mais ignorado.
- [x] `render.yaml` válido para deploy no Render (uvicorn + disco persistente + env vars).
- [x] UI × backend alinhados: filtros implementados no SQL e grade de resultados
      enxugada para as colunas realmente entregues (sem colunas vazias).
- [x] Pipeline de ingestão adaptado ao formato REAL da Receita (arquivos
      posicionais, sem cabeçalho, latin-1; JOIN Empresas×Estabelecimentos).
- [x] Teste automatizado provando que `/search` retorna dados reais de SP
      (tests/test_real_data.py) — ingestão de 20k+ empresas em < 1s.
- [ ] Baixar a base nacional real da Receita no ambiente de produção
      (bloqueado neste sandbox pela política de rede; o importador já está pronto
      para o layout oficial e roda em ambiente com acesso aos domínios da RF).

## 6. O que ainda falta para o beta comercial
- [ ] **Login / autenticação** de usuários (controle de acesso).
- [ ] **Pagamento / assinatura** (cobrança dos escritórios).
- [ ] Definir processo de suporte e canal de bugs (itens da seção 3).
