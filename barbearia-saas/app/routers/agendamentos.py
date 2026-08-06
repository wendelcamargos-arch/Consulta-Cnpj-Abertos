"""Agenda: reserva por barbeiro/serviços/horário com proteção contra dupla reserva.

Proteções de concorrência:
  - PostgreSQL: SELECT ... FOR UPDATE no barbeiro serializa reservas concorrentes,
    e a constraint de exclusão GiST (schema.py) é a garantia final no banco.
  - SQLite (apenas testes): as escritas já são serializadas pelo arquivo único.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..audit import auditar
from ..auth import contexto_tenant
from ..db import get_db, row, rows
from ..util import agora_tenant, dia_fechado, settings_tenant
from ..whatsapp_service import agendar_mensagens_do_agendamento, cancelar_mensagens_do_agendamento

router = APIRouter(prefix="/api/agendamentos", tags=["agendamentos"])

TRANSICOES = {
    "agendado": {"confirmado", "atrasado", "atendido", "cancelado", "no_show"},
    "confirmado": {"atrasado", "atendido", "cancelado", "no_show"},
    "atrasado": {"atendido", "cancelado", "no_show"},
    "atendido": set(),           # fechamento só pelo endpoint /fechar
    "pago_parcial": set(),
    "pago": set(),
}


class AgendamentoIn(BaseModel):
    cliente_id: int
    barbeiro_id: int
    inicio: str
    servico_ids: list[int]


class ReagendarIn(BaseModel):
    inicio: str
    barbeiro_id: int | None = None


class PagamentoItem(BaseModel):
    forma: str                   # dinheiro | pix | debito | credito | outro
    valor: float | None = None   # None no último item = restante


class FechamentoIn(BaseModel):
    pagamentos: list[PagamentoItem]
    desconto: float = 0
    voucher_codigo: str = ""
    produto_ids: list[int] = []


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


def _validar_disponibilidade(db, tenant_id: int, barbeiro_id: int, inicio: str, fim: str,
                             ignorar_id: int | None = None):
    sql = """SELECT a.id, c.nome cliente FROM agendamentos a JOIN clientes c ON c.id=a.cliente_id
             WHERE a.tenant_id=? AND a.barbeiro_id=? AND a.status NOT IN ('cancelado','no_show')
               AND a.inicio < ? AND a.fim > ?"""
    params: list = [tenant_id, barbeiro_id, fim, inicio]
    if ignorar_id is not None:
        sql += " AND a.id != ?"
        params.append(ignorar_id)
    conflito = row(db.execute(sql, params))
    if conflito:
        raise HTTPException(409, f"Conflito de horário: barbeiro já atende {conflito['cliente']} nesse intervalo")
    bloqueio = row(db.execute(
        "SELECT motivo FROM barber_blocks WHERE barbeiro_id=? AND inicio < ? AND fim > ?",
        (barbeiro_id, fim, inicio)))
    if bloqueio:
        raise HTTPException(409, f"Barbeiro indisponível nesse horário ({bloqueio['motivo'] or 'bloqueio'})")


def criar_agendamento(db, tenant_id: int, dados: AgendamentoIn,
                      recorrencia_id: int | None = None) -> dict:
    try:
        inicio_dt = datetime.fromisoformat(dados.inicio)
    except ValueError:
        raise HTTPException(422, "Data/hora inválida (use YYYY-MM-DDTHH:MM)")
    cliente = row(db.execute("SELECT * FROM clientes WHERE id=? AND tenant_id=?",
                             (dados.cliente_id, tenant_id)))
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado")

    # lock pessimista por barbeiro (PostgreSQL) contra reserva concorrente
    sql_barbeiro = "SELECT * FROM barbeiros WHERE id=? AND tenant_id=? AND ativo=1"
    if db.postgres:
        sql_barbeiro += " FOR UPDATE"
    barbeiro = row(db.execute(sql_barbeiro, (dados.barbeiro_id, tenant_id)))
    if not barbeiro:
        raise HTTPException(404, "Barbeiro não encontrado")

    cfg = settings_tenant(db, tenant_id)
    if dia_fechado(cfg, inicio_dt.date()):
        raise HTTPException(422, "A barbearia não abre nesse dia")

    servicos = _carregar_servicos(db, tenant_id, dados.servico_ids)
    duracao = sum(s["duracao_min"] for s in servicos)
    valor = sum(s["preco"] for s in servicos)
    fim_dt = inicio_dt + timedelta(minutes=duracao)

    hora = inicio_dt.strftime("%H:%M")
    if not (barbeiro["hora_inicio"] <= hora and fim_dt.strftime("%H:%M") <= barbeiro["hora_fim"]):
        raise HTTPException(422, f"Fora do expediente de {barbeiro['nome']} ({barbeiro['hora_inicio']}–{barbeiro['hora_fim']})")

    inicio, fim = inicio_dt.strftime("%Y-%m-%dT%H:%M"), fim_dt.strftime("%Y-%m-%dT%H:%M")
    _validar_disponibilidade(db, tenant_id, dados.barbeiro_id, inicio, fim)

    try:
        ag_id = db.insert(
            """INSERT INTO agendamentos (tenant_id, cliente_id, barbeiro_id, inicio, fim, valor_total, recorrencia_id)
               VALUES (?,?,?,?,?,?,?)""",
            (tenant_id, dados.cliente_id, dados.barbeiro_id, inicio, fim, valor, recorrencia_id))
    except Exception as exc:  # constraint de exclusão (corrida perdida) → 409
        if "agendamentos_sem_sobreposicao" in str(exc):
            raise HTTPException(409, "Conflito de horário detectado pelo banco (reserva concorrente)")
        raise
    for s in servicos:
        db.execute("INSERT INTO agendamento_servicos (agendamento_id, servico_id, preco) VALUES (?,?,?)",
                   (ag_id, s["id"], s["preco"]))

    agendar_mensagens_do_agendamento(db, tenant_id, ag_id, cliente, barbeiro, inicio_dt,
                                     [s["nome"] for s in servicos], agora_tenant(db, tenant_id))
    return {"id": ag_id, "inicio": inicio, "fim": fim, "valor_total": valor}


@router.get("")
def listar(data: str = "", barbeiro_id: int | None = None, usuario: dict = Depends(contexto_tenant)):
    condicoes, params = ["a.tenant_id=?"], [usuario["tenant_id"]]
    if data:
        condicoes.append("a.inicio >= ? AND a.inicio < ?")
        params += [data, data + "T23:59:59"]
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
        resultado = criar_agendamento(db, usuario["tenant_id"], dados)
        auditar(db, usuario["tenant_id"], usuario["uid"], "agendamento_criado",
                "agendamento", resultado["id"])
        return resultado


@router.put("/{ag_id}")
def reagendar(ag_id: int, dados: ReagendarIn, usuario: dict = Depends(contexto_tenant)):
    """Alteração de horário e/ou barbeiro de um agendamento futuro."""
    with get_db() as db:
        ag = row(db.execute("SELECT * FROM agendamentos WHERE id=? AND tenant_id=?",
                            (ag_id, usuario["tenant_id"])))
        if not ag:
            raise HTTPException(404, "Agendamento não encontrado")
        if ag["status"] in ("pago", "pago_parcial", "cancelado", "no_show", "atendido"):
            raise HTTPException(422, f"Agendamento em status '{ag['status']}' não pode ser reagendado")
        try:
            inicio_dt = datetime.fromisoformat(dados.inicio)
        except ValueError:
            raise HTTPException(422, "Data/hora inválida")
        duracao = datetime.fromisoformat(ag["fim"]) - datetime.fromisoformat(ag["inicio"])
        fim_dt = inicio_dt + duracao
        barbeiro_id = dados.barbeiro_id or ag["barbeiro_id"]
        inicio, fim = inicio_dt.strftime("%Y-%m-%dT%H:%M"), fim_dt.strftime("%Y-%m-%dT%H:%M")
        _validar_disponibilidade(db, usuario["tenant_id"], barbeiro_id, inicio, fim, ignorar_id=ag_id)
        db.execute("UPDATE agendamentos SET inicio=?, fim=?, barbeiro_id=?, status='agendado' WHERE id=?",
                   (inicio, fim, barbeiro_id, ag_id))
        cancelar_mensagens_do_agendamento(db, ag_id)
        cliente = row(db.execute("SELECT * FROM clientes WHERE id=?", (ag["cliente_id"],)))
        barbeiro = row(db.execute("SELECT * FROM barbeiros WHERE id=?", (barbeiro_id,)))
        servicos = [s["nome"] for s in rows(db.execute(
            "SELECT s.nome FROM agendamento_servicos ags JOIN servicos s ON s.id=ags.servico_id WHERE ags.agendamento_id=?",
            (ag_id,)))]
        agendar_mensagens_do_agendamento(db, usuario["tenant_id"], ag_id, cliente, barbeiro,
                                         inicio_dt, servicos, agora_tenant(db, usuario["tenant_id"]))
        auditar(db, usuario["tenant_id"], usuario["uid"], "agendamento_reagendado", "agendamento", ag_id)
    return {"id": ag_id, "inicio": inicio, "fim": fim}


@router.patch("/{ag_id}/status")
def mudar_status(ag_id: int, status: str, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        ag = row(db.execute("SELECT * FROM agendamentos WHERE id=? AND tenant_id=?",
                            (ag_id, usuario["tenant_id"])))
        if not ag:
            raise HTTPException(404, "Agendamento não encontrado")
        if status in ("pago", "pago_parcial"):
            raise HTTPException(422, "Use o endpoint de fechamento para registrar pagamento")
        if status not in TRANSICOES.get(ag["status"], set()):
            raise HTTPException(422, f"Transição inválida: {ag['status']} → {status}")
        db.execute("UPDATE agendamentos SET status=? WHERE id=?", (status, ag_id))
        if status in ("cancelado", "no_show"):
            cancelar_mensagens_do_agendamento(db, ag_id)
        auditar(db, usuario["tenant_id"], usuario["uid"], f"agendamento_{status}", "agendamento", ag_id)
    return {"status": status}


def _sessao_aberta(db, tenant_id: int) -> int | None:
    s = row(db.execute("SELECT id FROM cash_sessions WHERE tenant_id=? AND status='aberta' ORDER BY id DESC",
                       (tenant_id,)))
    return s["id"] if s else None


def _aplicar_voucher(db, tenant_id: int, ag: dict, codigo: str, hoje: str) -> float:
    from .aniversario import resgatar_voucher   # import tardio para evitar ciclo
    return resgatar_voucher(db, tenant_id, ag, codigo, hoje)


@router.post("/{ag_id}/fechar")
def fechar(ag_id: int, dados: FechamentoIn, usuario: dict = Depends(contexto_tenant)):
    """Fechamento: serviços somados pela tabela, voucher, produtos, pagamentos
    (divididos e parciais), comissão e lançamentos de caixa."""
    if not dados.pagamentos:
        raise HTTPException(422, "Informe ao menos uma forma de pagamento")
    with get_db() as db:
        ag = row(db.execute(
            """SELECT a.*, c.nome cliente, b.nome barbeiro, b.modelo, b.percentual_comissao
               FROM agendamentos a JOIN clientes c ON c.id=a.cliente_id JOIN barbeiros b ON b.id=a.barbeiro_id
               WHERE a.id=? AND a.tenant_id=?""", (ag_id, usuario["tenant_id"])))
        if not ag:
            raise HTTPException(404, "Agendamento não encontrado")
        if ag["status"] in ("pago", "cancelado", "no_show"):
            raise HTTPException(422, f"Agendamento em status '{ag['status']}' não pode ser fechado")

        agora = agora_tenant(db, usuario["tenant_id"])
        hoje = agora.strftime("%Y-%m-%d")
        sessao_id = _sessao_aberta(db, usuario["tenant_id"])

        desconto = max(dados.desconto, 0)
        if dados.voucher_codigo:
            desconto += _aplicar_voucher(db, usuario["tenant_id"], ag, dados.voucher_codigo, hoje)

        total_produtos = 0.0
        for pid in dados.produto_ids:
            p = row(db.execute("SELECT * FROM produtos WHERE id=? AND tenant_id=? AND ativo=1",
                               (pid, usuario["tenant_id"])))
            if not p:
                raise HTTPException(404, f"Produto {pid} não encontrado")
            if p["quantidade"] < 1:
                raise HTTPException(409, f"Sem estoque de {p['nome']}")
            db.execute("UPDATE produtos SET quantidade = quantidade - 1 WHERE id=?", (pid,))
            db.execute(
                """INSERT INTO movimentos_estoque (tenant_id, produto_id, tipo, quantidade, valor_unitario, custo_unitario, data)
                   VALUES (?,?,'venda',-1,?,?,?)""",
                (usuario["tenant_id"], pid, p["preco_venda"], p["custo_medio"] or p["custo"],
                 agora.strftime("%Y-%m-%dT%H:%M")))
            db.execute(
                "INSERT INTO lancamentos_caixa (tenant_id, sessao_id, data, tipo, categoria, descricao, valor, agendamento_id) VALUES (?,?,?,?,?,?,?,?)",
                (usuario["tenant_id"], sessao_id, hoje, "entrada", "produto",
                 f"Venda {p['nome']} — {ag['cliente']}", p["preco_venda"], ag_id))
            custo = p["custo_medio"] or p["custo"]
            if custo > 0:
                db.execute(
                    "INSERT INTO lancamentos_caixa (tenant_id, sessao_id, data, tipo, categoria, descricao, valor, agendamento_id) VALUES (?,?,?,?,?,?,?,?)",
                    (usuario["tenant_id"], sessao_id, hoje, "saida", "cmv",
                     f"CMV {p['nome']}", custo, ag_id))
            total_produtos += p["preco_venda"]

        total_servicos = max(ag["valor_total"] - desconto, 0)
        total_devido = round(total_servicos + total_produtos, 2)

        ja_pago = row(db.execute(
            "SELECT COALESCE(SUM(valor),0) v FROM payments WHERE agendamento_id=? AND status='confirmado'",
            (ag_id,)))["v"]

        total_pagamentos = 0.0
        for i, pg in enumerate(dados.pagamentos):
            if pg.forma not in ("dinheiro", "pix", "debito", "credito", "outro"):
                raise HTTPException(422, f"Forma de pagamento inválida: {pg.forma}")
            valor = pg.valor if pg.valor is not None else max(total_devido - ja_pago - total_pagamentos, 0)
            if valor <= 0:
                if pg.valor is None and i == len(dados.pagamentos) - 1:
                    continue
                raise HTTPException(422, "Valor de pagamento deve ser positivo")
            db.execute(
                "INSERT INTO payments (tenant_id, agendamento_id, sessao_id, forma, valor) VALUES (?,?,?,?,?)",
                (usuario["tenant_id"], ag_id, sessao_id, pg.forma, valor))
            total_pagamentos += valor

        recebido_total = round(ja_pago + total_pagamentos, 2)
        if recebido_total > total_devido + 0.01:
            raise HTTPException(422, f"Pagamentos ({recebido_total:.2f}) excedem o devido ({total_devido:.2f})")
        quitado = abs(recebido_total - total_devido) <= 0.01

        db.execute(
            "INSERT INTO lancamentos_caixa (tenant_id, sessao_id, data, tipo, categoria, descricao, valor, agendamento_id) VALUES (?,?,?,?,?,?,?,?)",
            (usuario["tenant_id"], sessao_id, hoje, "entrada", "servico",
             f"Serviços — {ag['cliente']} ({ag['barbeiro']})", round(total_pagamentos - total_produtos, 2)
             if total_pagamentos > total_produtos else total_pagamentos, ag_id))
        if desconto > 0:
            db.execute(
                "INSERT INTO lancamentos_caixa (tenant_id, sessao_id, data, tipo, categoria, descricao, valor, agendamento_id) VALUES (?,?,?,?,?,?,?,?)",
                (usuario["tenant_id"], sessao_id, hoje, "saida", "desconto",
                 f"Desconto — {ag['cliente']}", desconto, ag_id))

        comissao = 0.0
        if quitado and ag["modelo"] == "comissao" and ag["percentual_comissao"] > 0:
            comissao = round(total_servicos * ag["percentual_comissao"] / 100, 2)
            if comissao > 0:
                db.execute(
                    "INSERT INTO commissions (tenant_id, agendamento_id, barbeiro_id, percentual, valor) VALUES (?,?,?,?,?)",
                    (usuario["tenant_id"], ag_id, ag["barbeiro_id"], ag["percentual_comissao"], comissao))
                db.execute(
                    "INSERT INTO lancamentos_caixa (tenant_id, sessao_id, data, tipo, categoria, descricao, valor, agendamento_id) VALUES (?,?,?,?,?,?,?,?)",
                    (usuario["tenant_id"], sessao_id, hoje, "saida", "comissao",
                     f"Comissão {ag['percentual_comissao']:.0f}% — {ag['barbeiro']}", comissao, ag_id))

        novo_status = "pago" if quitado else "pago_parcial"
        db.execute("UPDATE agendamentos SET status=?, forma_pagamento=?, valor_total=?, desconto=? WHERE id=?",
                   (novo_status, ",".join(p.forma for p in dados.pagamentos), total_servicos, desconto, ag_id))
        auditar(db, usuario["tenant_id"], usuario["uid"], "fechamento", "agendamento", ag_id,
                f"status={novo_status} recebido={recebido_total:.2f}")
    return {"status": novo_status, "total_devido": total_devido, "recebido": recebido_total,
            "saldo_restante": round(total_devido - recebido_total, 2),
            "desconto": desconto, "comissao_barbeiro": comissao}


@router.post("/{ag_id}/estorno")
def estornar(ag_id: int, payment_id: int, usuario: dict = Depends(contexto_tenant)):
    """Estorna um pagamento confirmado: reverte caixa e reabre o saldo."""
    with get_db() as db:
        pg = row(db.execute(
            "SELECT * FROM payments WHERE id=? AND agendamento_id=? AND tenant_id=?",
            (payment_id, ag_id, usuario["tenant_id"])))
        if not pg:
            raise HTTPException(404, "Pagamento não encontrado")
        if pg["status"] == "estornado":
            raise HTTPException(422, "Pagamento já estornado")
        agora = agora_tenant(db, usuario["tenant_id"])
        db.execute("UPDATE payments SET status='estornado', estornado_em=?, estornado_por=? WHERE id=?",
                   (agora.strftime("%Y-%m-%dT%H:%M"), usuario["uid"], payment_id))
        db.execute(
            "INSERT INTO lancamentos_caixa (tenant_id, sessao_id, data, tipo, categoria, descricao, valor, agendamento_id) VALUES (?,?,?,?,?,?,?,?)",
            (usuario["tenant_id"], _sessao_aberta(db, usuario["tenant_id"]),
             agora.strftime("%Y-%m-%d"), "saida", "estorno",
             f"Estorno pagamento #{payment_id} ({pg['forma']})", pg["valor"], ag_id))
        db.execute("UPDATE agendamentos SET status='pago_parcial' WHERE id=? AND status='pago'", (ag_id,))
        auditar(db, usuario["tenant_id"], usuario["uid"], "estorno", "payment", payment_id,
                f"valor={pg['valor']:.2f}")
    return {"mensagem": "Pagamento estornado", "valor": pg["valor"]}


@router.get("/{ag_id}/pagamentos")
def pagamentos(ag_id: int, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return rows(db.execute(
            "SELECT * FROM payments WHERE agendamento_id=? AND tenant_id=? ORDER BY id",
            (ag_id, usuario["tenant_id"])))
