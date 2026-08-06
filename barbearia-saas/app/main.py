"""Sistema White Label SaaS para Barbearia — aplicação web.

Arquitetura modular multi-tenant: cada módulo é um router independente e todo
dado de negócio é isolado por tenant_id. O painel administrativo da plataforma
(superadmin) gerencia as barbearias; cada barbearia opera com login próprio.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .routers import (agendamentos, auth_routes, barbeiros, caixa, clientes,
                      estoque, recorrencias, relatorios, servicos, tenants, whatsapp)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Barbearia White Label SaaS", version="1.0.0", lifespan=lifespan)

for modulo in (auth_routes, tenants, clientes, barbeiros, servicos,
               agendamentos, recorrencias, whatsapp, caixa, estoque, relatorios):
    app.include_router(modulo.router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
