# Filtros: UI × Backend (alinhamento)

Comparação entre os filtros declarados em `models/search.py` (`SearchRequest`) e o
que `services/search_service.py` (`SearchService.search`) aplica no SQL.

## Decisão

**Todos os filtros do `SearchRequest` têm coluna correspondente na tabela
`empresas`, então foram IMPLEMENTADOS no SQL** (nenhum precisou ser escondido por
falta de lastro). O formulário visível expõe hoje um subconjunto; os demais ficam
prontos no backend para a UI da v1.1.

| Filtro (SearchRequest) | Coluna em `empresas`      | Status backend | Exposto na UI hoje |
|------------------------|---------------------------|----------------|--------------------|
| start_date / end_date  | `data_situacao`           | ✅ implementado | ✅ sim             |
| uf                     | `uf`                      | ✅ implementado | ✅ sim             |
| municipio              | `municipio`               | ✅ implementado | ✅ sim             |
| cnae                   | `cnae_principal`          | ✅ implementado | ✅ sim (novo)      |
| situacao               | `situacao_cadastral`      | ✅ implementado | ⬜ v1.1            |
| porte                  | `porte`                   | ✅ implementado | ⬜ v1.1            |
| natureza               | `natureza_juridica`       | ✅ implementado | ⬜ v1.1            |
| bairro                 | `bairro` (ILIKE)          | ✅ implementado | ⬜ v1.1            |
| cep                    | `cep` (só dígitos)        | ✅ implementado | ⬜ v1.1            |
| capital_min/max        | `capital_social`          | ✅ implementado | ⬜ v1.1            |
| empresa_matriz         | `matriz`                  | ✅ implementado | ⬜ v1.1            |
| empresa_filial         | `filial`                  | ✅ implementado | ⬜ v1.1            |
| only_phone             | `telefone` (not null/'')  | ✅ implementado | ⬜ v1.1            |
| only_email             | `email` (not null/'')     | ✅ implementado | ⬜ v1.1            |
| only_website           | `website` (not null/'')   | ✅ implementado | ⬜ v1.1            |

Regras especiais:
- `empresa_matriz` + `empresa_filial`: mutuamente exclusivos. Marcar os dois (ou
  nenhum) = sem filtro; apenas um marcado aplica o filtro correspondente.
- `cep`: comparação por dígitos, ignorando máscara (`01001-000` == `01001000`).
- `bairro`: `ILIKE %valor%` (busca parcial, case-insensitive).

## Frontend — o que foi escondido

O backend só **retorna** 6 campos por empresa (`SearchResult`: cnpj, nome, uf,
municipio, situacao, data_situacao). A grade de resultados antes mostrava ~24
colunas (telefone, e-mail, website, capital social, etc.) **sempre vazias**.
Essas colunas foram **removidas** da grade e das exportações do cliente
(`static/app.js`) para não prometer dados que a base ainda não entrega. Quando o
pipeline de importação passar a popular contato/endereço e o `SearchResult` for
enriquecido, as colunas voltam.
