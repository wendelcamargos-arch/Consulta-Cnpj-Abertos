"""Agenda inteligente: reserva por barbeiro, serviços e horário.

Fluxo do balcão (o mesmo do infográfico):
  recepção faz login → agenda cliente com barbeiro e horário → seleciona serviços
  → WhatsApp confirma 30 min antes → cliente responde → atendimento
  → serviços somados pela tabela de preços → pagamento e fechamento no caixa.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import contexto_tenant
from ..db import get_db, row, rows
from ..whatsapp_service import agendar_mensagens_do_agendamento, cancelar_mensagens_do_agendamento

router = APIRouter(prefix="/api/agendamentos", tags=["agendamentos"])

TRANSICOES = {
    "agendado": {"confirmado", "atrasado", "atendido", "cancelado", "no_show"},
    "confirmado": {"atrasado", "atendido", "cancelado", "no_show"},
    "atrasado": {"atendido", "cancelado", "no_show"},
    "atendido": {"pago"},
}


class AgendamentoIn(BaseModel):
    cliente_id: int
    barbeiro_id: int
    inicio: str                  # YYYY-MM-DDTHH:MM
    servico_ids: list[int]


class PagamentoIn(BaseModel):
    forma_pagamento: str         # dinheiro | pix | debito | credito
    desconto: float = 0
    produto_ids: list[int] = []  # produtos vendidos junto ao fechamento


def _carregar_servicos(db, tenant_id: int, servico_ids: list[int]) -> list[dict]:
    if not servico_ids:
        raise HTTPException(422, "Selecione ao menos um serviço")
    marcadores = ",".join("?" * len(servico_ids))
    servicos = rows(db.execute(
        f"SELECT * FROM servicos WHERE tenant_id=? AND ativo=1 AND id IN ({marcadores})",
        (tenant_id, *servico_ids)))
    if len(servicos) != len(set(servico_ids)):
        raise HTTPException(422, "Serviço inválido para esta barbearia")
    return servicos


def _validar_conflito(db, tenant_id: int, barbeiro_id: int, inicio: str, fim: str,
                      ignorar_id: int | None = None):
    conflito = row(db.execute(
        """SELECT a.id, c.nome cliente FROM agendamentos a JOIN clientes c ON c.id=a.cliente_id
           WHERE a.tenant_id=? AND a.barbeiro_id=? AND a.status NOT IN ('cancelado','no_show')
             AND a.inicio < ? AND a.fim > ? AND (? IS NULL OR a.id != ?)""",
        (tenant_id, barbeiro_id, fim, inicio, ignorar_id, ignorar_id)))
    if conflito:
        raise HTTPException(409, f"Conflito de horário: barbeiro já atende {conflito['cliente']} nesse intervalo")


def criar_agendamento(db, tenant_id: int, dados: AgendamentoIn, recorrencia_id: int | None = None) -> dict:
    """Núcleo da criação — reutilizado pela geração de recorrências."""
    try:
        inicio_dt = datetime.fromisoformat(dados.inicio)
    except ValueError:
        raise HTTPException(422, "Data/hora inválida (use YYYY-MM-DDTHH:MM)")
    cliente = row(db.execute("SELECT * FROM clientes WHERE id=? AND tenant_id=?", (dados.cliente_id, tenant_id)))
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado")
    barbeiro = row(db.execute("SELECT * FROM barbeiros WHERE id=? AND tenant_id=? AND ativo=1",
                              (dados.barbeiro_id, tenant_id)))
    if not barbeiro:
        raise HTTPException(404, "Barbeiro não encontrado")

    servicos = _carregar_servicos(db, tenant_id, dados.servico_ids)
    duracao = sum(s["duracao_min"] for s in servicos)
    valor = sum(s["preco"] for s in servicos)
    fim_dt = inicio_dt + timedelta(minutes=duracao)

    hora = inicio_dt.strftime("%H:%M")
    if not (barbeiro["hora_inicio"] <= hora and fim_dt.strftime("%H:%M") <= barbeiro["hora_fim"]):
        raise HTTPException(422, f"Fora do expediente de {barbeiro['nome']} ({barbeiro['hora_inicio']}–{barbeiro['hora_fim']})")

    inicio, fim = inicio_dt.strftime("%Y-%m-%dT%H:%M"), fim_dt.strftime("%Y-%m-%dT%H:%M")
    _validar_conflito(db, tenant_id, dados.barbeiro_id, inicio, fim)

    cur = db.execute(
        """INSERT INTO agendamentos (tenant_id, cliente_id, barbeiro_id, inicio, fim, valor_total, recorrencia_id)
           VALUES (?,?,?,?,?,?,?)""",
        (tenant_id, dados.cliente_id, dados.barbeiro_id, inicio, fim, valor, recorrencia_id))
    ag_id = cur.lastrowid
    for s in servicos:
        db.execute("INSERT INTO agendamento_servicos (agendamento_id, servico_id, preco) VALUES (?,?,?)",
                   (ag_id, s["id"], s["preco"]))

    agendar_mensagens_do_agendamento(db, tenant_id, ag_id, cliente, barbeiro, inicio_dt,
                                     [s["nome"] for s in servicos])
    return {"id": ag_id, "inicio": inicio, "fim": fim, "valor_total": valor}


@router.get("")
def listar(data: str = "", barbeiro_id: int | None = None, usuario: dict = Depends(contexto_tenant)):
    """Agenda do dia (data=YYYY-MM-DD) ou geral, com filtro opcional por barbeiro."""
    condicoes, params = ["a.tenant_id=?"], [usuario["tenant_id"]]
    if data:
        condicoes.append("a.inicio LIKE ?")
        params.append(f"{data}%")
    if barbeiro_id:
        condicoes.append("a.barbeiro_id=?")
        params.append(barbeiro_id)
    with get_db() as db:
        lista = rows(db.execute(
            f"""SELECT a.*, c.nome cliente, c.telefone, b.nome barbeiro
                FROM agendamentos a
                JOIN clientes c ON c.id=a.cliente_id
                JOIN barbeiros b ON b.id=a.barbeiro_id
                WHERE {' AND '.join(condicoes)}
                ORDER BY a.inicio""", params))
        for a in lista:
            a["servicos"] = rows(db.execute(
                """SELECT s.nome, ags.preco FROM agendamento_servicos ags
                   JOIN servicos s ON s.id=ags.servico_id WHERE ags.agendamento_id=?""", (a["id"],)))
    return lista


@router.post("")
def criar(dados: AgendamentoIn, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return criar_agendamento(db, usuario["tenant_id"], dados)


@router.patch("/{ag_id}/status")
def mudar_status(ag_id: int, status: str, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        ag = row(db.execute("SELECT * FROM agendamentos WHERE id=? AND tenant_id=?", (ag_id, usuario["tenant_id"])))
        if not ag:
            raise HTTPException(404, "Agendamento não encontrado")
        if status == "pago":
            raise HTTPException(422, "Use o endpoint de fechamento para registrar pagamento")
        if status not in TRANSICOES.get(ag["status"], set()):
            raise HTTPException(422, f"Transição inválida: {ag['status']} → {status}")
        db.execute("UPDATE agendamentos SET status=? WHERE id=?", (status, ag_id))
        if status in ("cancelado", "no_show"):
            cancelar_mensagens_do_agendamento(db, ag_id)
    return {"status": status}


@router.post("/{ag_id}/fechar")
def fechar(ag_id: int, dados: PagamentoIn, usuario: dict = Depends(contexto_tenant)):
    """Fechamento: soma serviços pela tabela, vende produtos, lança caixa e comissão."""
    with get_db() as db:
        ag = row(db.execute(
            """SELECT a.*, c.nome cliente, b.nome barbeiro, b.modelo, b.percentual_comissao
               FROM agendamentos a JOIN clientes c ON c.id=a.cliente_id JOIN barbeiros b ON b.id=a.barbeiro_id
               WHERE a.id=? AND a.tenant_id=?""", (ag_id, usuario["tenant_id"])))
        if not ag:
            raise HTTPException(404, "Agendamento não encontrado")
        if ag["status"] not in ("atendido", "confirmado", "agendado", "atrasado"):
            raise HTTPException(422, f"Agendamento em status '{ag['status']}' não pode ser fechado")

        total_servicos = ag["valor_total"]
        total_produtos = 0.0
        data_hoje = datetime.now().strftime("%Y-%m-%d")
        for pid in dados.produto_ids:
            p = row(db.execute("SELECT * FROM produtos WHERE id=? AND tenant_id=? AND ativo=1",
                               (pid, usuario["tenant_id"])))
            if not p:
                raise HTTPException(404, f"Produto {pid} não encontrado")
            if p["quantidade"] < 1:
                raise HTTPException(409, f"Sem estoque de {p['nome']}")
            db.execute("UPDATE produtos SET quantidade = quantidade - 1 WHERE id=?", (pid,))
            db.execute(
                "INSERT INTO movimentos_estoque (tenant_id, produto_id, tipo, quantidade, valor_unitario) VALUES (?,?,'venda',-1,?)",
                (usuario["tenant_id"], pid, p["preco_venda"]))
            db.execute(
                "INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor, agendamento_id) VALUES (?,?,?,?,?,?,?)",
                (usuario["tenant_id"], data_hoje, "entrada", "produto",
                 f"Venda {p['nome']} — {ag['cliente']}", p["preco_venda"], ag_id))
            total_produtos += p["preco_venda"]

        total = max(total_servicos - dados.desconto, 0)
        db.execute(
            "INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor, agendamento_id) VALUES (?,?,?,?,?,?,?)",
            (usuario["tenant_id"], data_hoje, "entrada", "servico",
             f"Serviços — {ag['cliente']} ({ag['barbeiro']})", total, ag_id))

        comissao = 0.0
        if ag["modelo"] == "comissao" and ag["percentual_comissao"] > 0:
            comissao = round(total * ag["percentual_comissao"] / 100, 2)
            db.execute(
                "INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor, agendamento_id) VALUES (?,?,?,?,?,?,?)",
                (usuario["tenant_id"], data_hoje, "saida", "comissao",
                 f"Comissão {ag['percentual_comissao']:.0f}% — {ag['barbeiro']}", comissao, ag_id))

        db.execute("UPDATE agendamentos SET status='pago', forma_pagamento=?, valor_total=? WHERE id=?",
                   (dados.forma_pagamento, total, ag_id))
    return {"total_servicos": total, "total_produtos": total_produtos,
            "comissao_barbeiro": comissao, "total_recebido": total + total_produtos}
