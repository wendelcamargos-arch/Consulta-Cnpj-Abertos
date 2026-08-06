"""Sistema White Label SaaS para Barbearia — aplicação web multi-tenant.

Arquitetura modular: um router por domínio, isolamento por tenant_id em toda
tabela de negócio (docs/MULTI_TENANCY.md), PostgreSQL como banco operacional.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .db import get_db, init_db, is_postgres
from .routers import (agendamentos, aniversario, auth_routes, barbeiros, caixa,
                      clientes, estoque, onboarding, recorrencias, relatorios,
                      servicos, tenants, whatsapp)

APP_ENV = os.environ.get("APP_ENV", "development")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if APP_ENV == "production":
        if not os.environ.get("BARBEARIA_SECRET"):
            raise RuntimeError("BARBEARIA_SECRET é obrigatório em produção")
        if not is_postgres():
            raise RuntimeError("Produção exige PostgreSQL (DATABASE_URL)")
    init_db()
    yield


app = FastAPI(title="Barbearia White Label SaaS", version="2.0.0", lifespan=lifespan,
              docs_url="/docs" if APP_ENV != "production" else None,
              redoc_url=None)

_origens = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens or (["*"] if APP_ENV != "production" else []),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    resposta = await call_next(request)
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("X-Frame-Options", "DENY")
    resposta.headers.setdefault("Referrer-Policy", "no-referrer")
    resposta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if APP_ENV == "production":
        resposta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resposta


for modulo in (auth_routes, tenants, onboarding, clientes, barbeiros, servicos,
               agendamentos, recorrencias, whatsapp, aniversario, caixa, estoque, relatorios):
    app.include_router(modulo.router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health/live", include_in_schema=False)
def liveness():
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
def readiness():
    try:
        with get_db() as db:
            db.execute("SELECT 1").fetchone()
        return {"status": "ok", "database": "postgresql" if is_postgres() else "sqlite"}
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)


@app.get("/", include_in_schema=False)
def site():
    """Página pública comercial. O painel fica em /app."""
    return FileResponse(os.path.join(STATIC_DIR, "site.html"))


@app.get("/app", include_in_schema=False)
def painel():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/privacidade", include_in_schema=False)
def privacidade():
    return FileResponse(os.path.join(STATIC_DIR, "privacidade.html"))


@app.get("/termos", include_in_schema=False)
def termos():
    return FileResponse(os.path.join(STATIC_DIR, "termos.html"))
