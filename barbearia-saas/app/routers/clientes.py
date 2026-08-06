"""CRM do cliente: nome, CPF, telefone e aniversário."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import contexto_tenant
from ..db import get_db, row, rows

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


def validar_cpf(cpf: str) -> str:
    """Normaliza e valida CPF pelos dígitos verificadores. Vazio é permitido."""
    digitos = re.sub(r"\D", "", cpf)
    if not digitos:
        return ""
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        raise HTTPException(422, "CPF inválido")
    for pos in (9, 10):
        soma = sum(int(digitos[i]) * ((pos + 1) - i) for i in range(pos))
        dv = (soma * 10) % 11 % 10
        if dv != int(digitos[pos]):
            raise HTTPException(422, "CPF inválido")
    return digitos


def normalizar_telefone(telefone: str) -> str:
    digitos = re.sub(r"\D", "", telefone)
    if len(digitos) < 10:
        raise HTTPException(422, "Telefone deve ter DDD + número")
    return digitos


class ClienteIn(BaseModel):
    nome: str
    telefone: str
    cpf: str = ""
    aniversario: str = ""      # MM-DD ou DD/MM
    observacoes: str = ""


def normalizar_aniversario(valor: str) -> str:
    if not valor:
        return ""
    m = re.fullmatch(r"(\d{2})/(\d{2})", valor)          # DD/MM
    if m:
        return f"{m.group(2)}-{m.group(1)}"
    m = re.fullmatch(r"(?:\d{4}-)?(\d{2})-(\d{2})", valor)  # [YYYY-]MM-DD
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    raise HTTPException(422, "Aniversário deve ser DD/MM ou MM-DD")


@router.get("")
def listar(busca: str = "", usuario: dict = Depends(contexto_tenant)):
    filtro = f"%{busca}%"
    with get_db() as db:
        return rows(db.execute(
            """SELECT c.*,
                      (SELECT COUNT(*) FROM agendamentos a WHERE a.cliente_id=c.id AND a.status IN ('atendido','pago')) visitas,
                      (SELECT MAX(inicio) FROM agendamentos a WHERE a.cliente_id=c.id) ultima_visita
               FROM clientes c
               WHERE c.tenant_id=? AND (c.nome LIKE ? OR c.telefone LIKE ? OR c.cpf LIKE ?)
               ORDER BY c.nome""",
            (usuario["tenant_id"], filtro, filtro, filtro)))


@router.get("/aniversariantes")
def aniversariantes(mes: int, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return rows(db.execute(
            "SELECT * FROM clientes WHERE tenant_id=? AND aniversario LIKE ? ORDER BY aniversario",
            (usuario["tenant_id"], f"{mes:02d}-%")))


@router.post("")
def criar(dados: ClienteIn, usuario: dict = Depends(contexto_tenant)):
    cpf = validar_cpf(dados.cpf)
    telefone = normalizar_telefone(dados.telefone)
    aniversario = normalizar_aniversario(dados.aniversario)
    with get_db() as db:
        if cpf and row(db.execute("SELECT id FROM clientes WHERE tenant_id=? AND cpf=?", (usuario["tenant_id"], cpf))):
            raise HTTPException(409, "Já existe cliente com esse CPF")
        cur = db.execute(
            "INSERT INTO clientes (tenant_id, nome, cpf, telefone, aniversario, observacoes) VALUES (?,?,?,?,?,?)",
            (usuario["tenant_id"], dados.nome.strip(), cpf, telefone, aniversario, dados.observacoes))
        return {"id": cur.lastrowid}


@router.put("/{cliente_id}")
def atualizar(cliente_id: int, dados: ClienteIn, usuario: dict = Depends(contexto_tenant)):
    cpf = validar_cpf(dados.cpf)
    telefone = normalizar_telefone(dados.telefone)
    aniversario = normalizar_aniversario(dados.aniversario)
    with get_db() as db:
        if not row(db.execute("SELECT id FROM clientes WHERE id=? AND tenant_id=?", (cliente_id, usuario["tenant_id"]))):
            raise HTTPException(404, "Cliente não encontrado")
        db.execute(
            "UPDATE clientes SET nome=?, cpf=?, telefone=?, aniversario=?, observacoes=? WHERE id=? AND tenant_id=?",
            (dados.nome.strip(), cpf, telefone, aniversario, dados.observacoes, cliente_id, usuario["tenant_id"]))
    return {"mensagem": "Cliente atualizado"}
