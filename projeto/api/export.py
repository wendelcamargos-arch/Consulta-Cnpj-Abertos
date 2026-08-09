from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.logger import logger
from fastapi.responses import StreamingResponse

from models.search import SearchRequest
from services.export_service import ExportService
from services.search_service import SearchService

router = APIRouter()


def validate_export_request(search_request: SearchRequest) -> None:
    if search_request.start_date is None:
        raise HTTPException(status_code=422, detail="Data Inicial obrigatória.")

    if search_request.end_date is None:
        raise HTTPException(status_code=422, detail="Data Final obrigatória.")

    start = date.fromisoformat(search_request.start_date)
    end = date.fromisoformat(search_request.end_date)

    if end < start:
        raise HTTPException(status_code=422, detail="Data Final deve ser maior ou igual à Data Inicial.")

    if (end - start).days > 10:
        raise HTTPException(status_code=422, detail="Intervalo máximo de 10 dias.")


@router.get("/export/excel")
def export_excel(
    start_date: str = Query(...),
    end_date: str = Query(...),
    uf: str | None = Query(None),
    municipio: str | None = Query(None),
    cnae: str | None = Query(None),
    limit: int | None = Query(100),
):
    logger.info('Exportação Excel solicitada com filtros: %s', {
        'start_date': start_date,
        'end_date': end_date,
        'uf': uf,
        'municipio': municipio,
        'cnae': cnae,
        'limit': limit,
    })

    search_request = SearchRequest.model_validate({
        "startDate": start_date,
        "endDate": end_date,
        "uf": uf,
        "municipio": municipio,
        "cnae": cnae,
        "limit": limit,
        "page": 1,
        "pageSize": limit or 100,
    })
    validate_export_request(search_request)

    results, total_count = SearchService.search(
        start_date=search_request.start_date,
        end_date=search_request.end_date,
        uf=search_request.uf,
        municipio=search_request.municipio,
        cnae=search_request.cnae,
        limit=search_request.limit,
        page=1,
        page_size=search_request.limit or 100,
    )
    if not results:
        raise HTTPException(status_code=404, detail="Nenhum resultado para os filtros fornecidos.")

    workbook_bytes = ExportService.create_excel_workbook(results)
    filename = f"cnpj_hunter_{search_request.start_date}_{search_request.end_date}.xlsx"

    return StreamingResponse(
        workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/csv")
def export_csv(
    start_date: str = Query(...),
    end_date: str = Query(...),
    uf: str | None = Query(None),
    municipio: str | None = Query(None),
    cnae: str | None = Query(None),
    limit: int | None = Query(100),
):
    logger.info('Exportação CSV solicitada com filtros: %s', {
        'start_date': start_date,
        'end_date': end_date,
        'uf': uf,
        'municipio': municipio,
        'cnae': cnae,
        'limit': limit,
    })

    search_request = SearchRequest.model_validate({
        "startDate": start_date,
        "endDate": end_date,
        "uf": uf,
        "municipio": municipio,
        "cnae": cnae,
        "limit": limit,
        "page": 1,
        "pageSize": limit or 100,
    })
    validate_export_request(search_request)

    results, total_count = SearchService.search(
        start_date=search_request.start_date,
        end_date=search_request.end_date,
        uf=search_request.uf,
        municipio=search_request.municipio,
        cnae=search_request.cnae,
        limit=search_request.limit,
        page=1,
        page_size=search_request.limit or 100,
    )
    if not results:
        raise HTTPException(status_code=404, detail="Nenhum resultado para os filtros fornecidos.")

    csv_bytes = ExportService.create_csv_bytes(results)
    filename = f"cnpj_hunter_{search_request.start_date}_{search_request.end_date}.csv"

    return StreamingResponse(
        csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export", response_model=None)
def export_post(search_request: SearchRequest = Body(...)):
    """Compatibilidade com frontend: aceita POST JSON e retorna Excel do resultado."""
    logger.info('Exportação (POST) solicitada com filtros: %s', search_request.model_dump())
    # Reuse validation
    if search_request.start_date is None or search_request.end_date is None:
        raise HTTPException(status_code=422, detail="Data Inicial/Final obrigatórias.")

    results, total_count = SearchService.search(
        start_date=search_request.start_date,
        end_date=search_request.end_date,
        uf=search_request.uf,
        municipio=search_request.municipio,
        cnae=search_request.cnae,
        limit=search_request.limit,
        page=1,
        page_size=search_request.limit or 10000,
        situacao=search_request.situacao,
        porte=search_request.porte,
        natureza=search_request.natureza,
        bairro=search_request.bairro,
        cep=search_request.cep,
        capital_min=search_request.capital_min,
        capital_max=search_request.capital_max,
        empresa_matriz=search_request.empresa_matriz,
        empresa_filial=search_request.empresa_filial,
        only_phone=search_request.only_phone,
        only_email=search_request.only_email,
        only_website=search_request.only_website,
    )
    if not results:
        raise HTTPException(status_code=404, detail="Nenhum resultado para os filtros fornecidos.")

    workbook_bytes = ExportService.create_excel_workbook(results)
    filename = f"cnpj_hunter_{search_request.start_date}_{search_request.end_date}.xlsx"

    return StreamingResponse(
        workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
