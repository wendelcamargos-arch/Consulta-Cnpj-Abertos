from datetime import date
from typing import Dict

from fastapi import APIRouter, HTTPException
from fastapi.logger import logger

from models.search import SearchRequest, SearchResponse
from services.search_service import SearchService

router = APIRouter()

@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest):
    logger.info("Recebida pesquisa com filtros: %s", request.model_dump())

    if request.start_date is None:
        raise HTTPException(status_code=422, detail="Data Inicial obrigatória.")

    if request.end_date is None:
        raise HTTPException(status_code=422, detail="Data Final obrigatória.")

    start = date.fromisoformat(request.start_date)
    end = date.fromisoformat(request.end_date)

    if end < start:
        raise HTTPException(status_code=422, detail="Data Final deve ser maior ou igual à Data Inicial.")

    if (end - start).days > 10:
        raise HTTPException(status_code=422, detail="Intervalo máximo de 10 dias.")

    if request.limit is None:
        raise HTTPException(status_code=422, detail="Limite obrigatório.")

    if request.capital_min is not None and request.capital_max is not None:
        if request.capital_min > request.capital_max:
            raise HTTPException(status_code=422, detail="Capital mínimo não pode ser maior que Capital máximo.")

    try:
        results, total_count = SearchService.search(
            start_date=request.start_date,
            end_date=request.end_date,
            uf=request.uf,
            municipio=request.municipio,
            cnae=request.cnae,
            limit=request.limit,
            page=request.page or 1,
            page_size=request.page_size or 10,
            situacao=request.situacao,
            porte=request.porte,
            natureza=request.natureza,
            bairro=request.bairro,
            cep=request.cep,
            capital_min=request.capital_min,
            capital_max=request.capital_max,
            empresa_matriz=request.empresa_matriz,
            empresa_filial=request.empresa_filial,
            only_phone=request.only_phone,
            only_email=request.only_email,
            only_website=request.only_website,
        )
    except Exception as exc:
        logger.exception("Erro ao executar busca: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao executar busca no banco de dados.")

    page = int(request.page or 1)
    page_size = int(request.page_size or 10)
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

    message = "Pesquisa executada com sucesso."
    if total_count == 0:
        message = "Nenhum resultado encontrado para os filtros informados."

    response = SearchResponse(
        success=True,
        message=message,
        filters={
            "startDate": request.start_date,
            "endDate": request.end_date,
            "uf": request.uf,
            "municipio": request.municipio,
            "cnae": request.cnae,
            "limit": request.limit,
            "page": page,
            "pageSize": page_size,
        },
        results=results,
        total_count=total_count,
        total_pages=total_pages,
        current_page=page,
        has_next=page < total_pages,
        has_previous=page > 1,
    )

    logger.info("Pesquisa validada e executada com sucesso.")
    return response
