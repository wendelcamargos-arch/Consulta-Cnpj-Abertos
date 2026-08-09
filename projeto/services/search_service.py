from typing import List, Optional, Tuple

from config.settings import MAX_RESULTS
from models.search import SearchResult
from services.database_service import DatabaseService


class SearchService:
    """Consulta real no DuckDB.

    Todos os filtros aceitos aqui possuem coluna correspondente na tabela
    `empresas`, então são aplicados diretamente no SQL. Ver
    `docs/filtros.md` para o mapeamento filtro -> coluna.
    """

    @staticmethod
    def _build_where(
        start_date: Optional[str],
        end_date: Optional[str],
        uf: Optional[str],
        municipio: Optional[str],
        cnae: Optional[str],
        situacao: Optional[str],
        porte: Optional[str],
        natureza: Optional[str],
        bairro: Optional[str],
        cep: Optional[str],
        capital_min: Optional[float],
        capital_max: Optional[float],
        empresa_matriz: bool,
        empresa_filial: bool,
        only_phone: bool,
        only_email: bool,
        only_website: bool,
    ) -> Tuple[List[str], List]:
        """Monta a cláusula WHERE (lista de condições) e os parâmetros.

        Reutilizado tanto pela query de resultados quanto pela de contagem para
        garantir que ambas fiquem sempre em sincronia.
        """
        where: List[str] = []
        params: List = []

        # --- Filtros originais (comportamento preservado) ---
        if start_date:
            where.append("e.data_situacao >= ?")
            params.append(start_date)
        if end_date:
            where.append("e.data_situacao <= ?")
            params.append(end_date)
        if uf:
            where.append("e.uf = ?")
            params.append(uf)
        if municipio:
            where.append("e.municipio = ?")
            params.append(municipio)
        if cnae:
            where.append("e.cnae_principal = ?")
            params.append(cnae)

        # --- Filtros novos, todos com coluna real em `empresas` ---
        if situacao:
            where.append("e.situacao_cadastral = ?")
            params.append(situacao)
        if porte:
            where.append("e.porte = ?")
            params.append(porte)
        if natureza:
            where.append("e.natureza_juridica = ?")
            params.append(natureza)
        if bairro:
            where.append("e.bairro ILIKE ?")
            params.append(f"%{bairro}%")
        if cep:
            # Compara apenas os dígitos, ignorando máscara (pontos/hífen).
            where.append("regexp_replace(e.cep, '[^0-9]', '', 'g') = ?")
            params.append("".join(ch for ch in cep if ch.isdigit()))
        if capital_min is not None:
            where.append("e.capital_social >= ?")
            params.append(capital_min)
        if capital_max is not None:
            where.append("e.capital_social <= ?")
            params.append(capital_max)

        # matriz/filial são mutuamente exclusivos: só filtra quando exatamente um
        # está marcado (marcar ambos ou nenhum = sem filtro).
        if empresa_matriz and not empresa_filial:
            where.append("e.matriz = TRUE")
        elif empresa_filial and not empresa_matriz:
            where.append("e.filial = TRUE")

        if only_phone:
            where.append("e.telefone IS NOT NULL AND e.telefone <> ''")
        if only_email:
            where.append("e.email IS NOT NULL AND e.email <> ''")
        if only_website:
            where.append("e.website IS NOT NULL AND e.website <> ''")

        return where, params

    @staticmethod
    def search(
        start_date: str,
        end_date: str,
        uf: Optional[str] = None,
        municipio: Optional[str] = None,
        cnae: Optional[str] = None,
        limit: Optional[int] = 100,
        page: int = 1,
        page_size: int = 10,
        situacao: Optional[str] = None,
        porte: Optional[str] = None,
        natureza: Optional[str] = None,
        bairro: Optional[str] = None,
        cep: Optional[str] = None,
        capital_min: Optional[float] = None,
        capital_max: Optional[float] = None,
        empresa_matriz: bool = False,
        empresa_filial: bool = False,
        only_phone: bool = False,
        only_email: bool = False,
        only_website: bool = False,
    ) -> Tuple[List[SearchResult], int]:
        where, params = SearchService._build_where(
            start_date=start_date,
            end_date=end_date,
            uf=uf,
            municipio=municipio,
            cnae=cnae,
            situacao=situacao,
            porte=porte,
            natureza=natureza,
            bairro=bairro,
            cep=cep,
            capital_min=capital_min,
            capital_max=capital_max,
            empresa_matriz=empresa_matriz,
            empresa_filial=empresa_filial,
            only_phone=only_phone,
            only_email=only_email,
            only_website=only_website,
        )
        where_clause = ("WHERE " + " AND ".join(where)) if where else ""

        # Query principal de resultados.
        sql = [
            "SELECT e.cnpj AS cnpj, e.razao_social AS nome, e.uf AS uf, e.municipio AS municipio, e.situacao_cadastral AS situacao, e.data_situacao AS data_situacao",
            "FROM empresas e",
        ]
        if where_clause:
            sql.append(where_clause)
        sql.append("GROUP BY e.cnpj, e.razao_social, e.uf, e.municipio, e.situacao_cadastral, e.data_situacao")
        sql.append("ORDER BY e.data_situacao DESC")

        # Contagem de empresas distintas com os mesmos filtros.
        count_sql = ["SELECT COUNT(DISTINCT e.cnpj) FROM empresas e"]
        if where_clause:
            count_sql.append(where_clause)
        count_query = "\n".join(count_sql)

        # Paginação. `limit` limita o total lógico; a página retorna page_size linhas.
        if limit is None:
            limit = page_size
        limit = min(int(limit), MAX_RESULTS)
        offset = max(0, (int(page) - 1) * int(page_size))
        sql.append(f"LIMIT {int(page_size)} OFFSET {int(offset)}")

        query = "\n".join(sql)

        results: List[SearchResult] = []
        total_count = 0
        with DatabaseService.get_connection() as conn:
            try:
                total_count = conn.execute(count_query, params).fetchone()[0]
            except Exception:
                total_count = 0
            try:
                rows = conn.execute(query, params).fetchall()
            except Exception:
                rows = []

        total_count_capped = min(total_count, MAX_RESULTS)

        for r in rows:
            results.append(
                SearchResult(
                    cnpj=r[0],
                    nome=r[1] or "",
                    uf=r[2] or "",
                    municipio=r[3] or "",
                    situacao=r[4] or "",
                    data_situacao=str(r[5]) if r[5] is not None else "",
                )
            )

        return results, int(total_count_capped)
