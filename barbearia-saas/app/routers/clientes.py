"""CRM do cliente: nome, CPF validado, telefone, aniversário e consentimentos LGPD.

CPF: finalidade, base legal, retenção e anonimização documentadas em docs/LGPD.md.
Consentimento de marketing é registrado em customer_consents e exigido pela
campanha de aniversário.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import contexto_tenant
from ..db import get_db, row, rows

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


def validar_cpf(cpf: str) -> str:
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


def normalizar_aniversario(valor: str) -> str:
    if not valor:
        return ""
    m = re.fullmatch(r"(\d{2})/(\d{2})", valor)
    if m:
        return f"{m.group(2)}-{m.group(1)}"
    m = re.fullmatch(r"(?:\d{4}-)?(\d{2})-(\d{2})", valor)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    raise HTTPException(422, "Aniversário deve ser DD/MM ou MM-DD")


class ClienteIn(BaseModel):
    nome: str
    telefone: str
    cpf: str = ""
    aniversario: str = ""
    observacoes: str = ""
    consentimento_marketing: bool | None = None
    consentimento_lembretes: bool | None = None


def _registrar_consentimentos(db, tenant_id: int, cliente_id: int, dados: ClienteIn):
    for tipo, valor in (("marketing", dados.consentimento_marketing),
                        ("lembretes", dados.consentimento_lembretes)):
        if valor is None:
            continue
        atual = row(db.execute(
            "SELECT concedido FROM customer_consents WHERE cliente_id=? AND tipo=? ORDER BY id DESC LIMIT 1",
            (cliente_id, tipo)))
        if atual is None or bool(atual["concedido"]) != valor:
            db.execute(
                "INSERT INTO customer_consents (tenant_id, cliente_id, tipo, concedido) VALUES (?,?,?,?)",
                (tenant_id, cliente_id, tipo, int(valor)))


@router.get("")
def listar(busca: str = "", usuario: dict = Depends(contexto_tenant)):
    filtro = f"%{busca}%"
    with get_db() as db:
        lista = rows(db.execute(
            """SELECT c.*,
                      (SELECT COUNT(*) FROM agendamentos a WHERE a.cliente_id=c.id AND a.status IN ('atendido','pago','pago_parcial')) visitas,
                      (SELECT MAX(inicio) FROM agendamentos a WHERE a.cliente_id=c.id) ultima_visita
               FROM clientes c
               WHERE c.tenant_id=? AND (c.nome LIKE ? OR c.telefone LIKE ? OR c.cpf LIKE ?)
               ORDER BY c.nome""",
            (usuario["tenant_id"], filtro, filtro, filtro)))
        for c in lista:
            consent = row(db.execute(
                "SELECT concedido FROM customer_consents WHERE cliente_id=? AND tipo='marketing' ORDER BY id DESC LIMIT 1",
                (c["id"],)))
            c["consentimento_marketing"] = bool(consent["concedido"]) if consent else False
    return lista


@router.get("/aniversariantes")
def aniversariantes(mes: int, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return rows(db.execute(
            "SELECT * FROM clientes WHERE tenant_id=? AND aniversario LIKE ? ORDER BY aniversario",
            (usuario["tenant_id"], f"{mes:02d}-%")))


@router.get("/{cliente_id}/historico")
def historico(cliente_id: int, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        cliente = row(db.execute("SELECT * FROM clientes WHERE id=? AND tenant_id=?",
                                 (cliente_id, usuario["tenant_id"])))
        if not cliente:
            raise HTTPException(404, "Cliente não encontrado")
        atendimentos = rows(db.execute(
            """SELECT a.id, a.inicio, a.status, a.valor_total, b.nome barbeiro
               FROM agendamentos a JOIN barbeiros b ON b.id=a.barbeiro_id
               WHERE a.cliente_id=? ORDER BY a.inicio DESC LIMIT 50""", (cliente_id,)))
        consentimentos = rows(db.execute(
            "SELECT tipo, concedido, registrado_em FROM customer_consents WHERE cliente_id=? ORDER BY id DESC",
            (cliente_id,)))
    return {"cliente": cliente, "atendimentos": atendimentos, "consentimentos": consentimentos}


@router.post("")
def criar(dados: ClienteIn, usuario: dict = Depends(contexto_tenant)):
    cpf = validar_cpf(dados.cpf)
    telefone = normalizar_telefone(dados.telefone)
    aniversario = normalizar_aniversario(dados.aniversario)
    with get_db() as db:
        if cpf and row(db.execute("SELECT id FROM clientes WHERE tenant_id=? AND cpf=?",
                                  (usuario["tenant_id"], cpf))):
            raise HTTPException(409, "Já existe cliente com esse CPF")
        cliente_id = db.insert(
            "INSERT INTO clientes (tenant_id, nome, cpf, telefone, aniversario, observacoes) VALUES (?,?,?,?,?,?)",
            (usuario["tenant_id"], dados.nome.strip(), cpf, telefone, aniversario, dados.observacoes))
        _registrar_consentimentos(db, usuario["tenant_id"], cliente_id, dados)
        return {"id": cliente_id}


@router.put("/{cliente_id}")
def atualizar(cliente_id: int, dados: ClienteIn, usuario: dict = Depends(contexto_tenant)):
    cpf = validar_cpf(dados.cpf)
    telefone = normalizar_telefone(dados.telefone)
    aniversario = normalizar_aniversario(dados.aniversario)
    with get_db() as db:
        if not row(db.execute("SELECT id FROM clientes WHERE id=? AND tenant_id=?",
                              (cliente_id, usuario["tenant_id"]))):
            raise HTTPException(404, "Cliente não encontrado")
        db.execute(
            "UPDATE clientes SET nome=?, cpf=?, telefone=?, aniversario=?, observacoes=? WHERE id=? AND tenant_id=?",
            (dados.nome.strip(), cpf, telefone, aniversario, dados.observacoes,
             cliente_id, usuario["tenant_id"]))
        _registrar_consentimentos(db, usuario["tenant_id"], cliente_id, dados)
    return {"mensagem": "Cliente atualizado"}
