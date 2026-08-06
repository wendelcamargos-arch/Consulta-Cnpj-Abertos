"""Recorrência nativa: reservas semanais, quinzenais, mensais ou anuais.

A recorrência é um contrato de horário; a geração materializa os próximos
agendamentos reais (com fila de WhatsApp), pulando os que conflitarem.
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import contexto_tenant
from ..db import get_db, row, rows
from .agendamentos import AgendamentoIn, criar_agendamento

router = APIRouter(prefix="/api/recorrencias", tags=["recorrencias"])


class RecorrenciaIn(BaseModel):
    cliente_id: int
    barbeiro_id: int
    servico_id: int
    frequencia: str              # semanal | quinzenal | mensal | anual
    hora: str                    # HH:MM
    dia_semana: int | None = None   # 0=segunda ... 6=domingo
    dia_mes: int | None = None      # 1..28
    data_base: str | None = None    # YYYY-MM-DD (anual)


def proximas_datas(rec: dict, quantidade: int) -> list[date]:
    hoje = date.today()
    datas: list[date] = []
    if rec["frequencia"] in ("semanal", "quinzenal"):
        passo = 7 if rec["frequencia"] == "semanal" else 14
        d = hoje + timedelta(days=(rec["dia_semana"] - hoje.weekday()) % 7 or 7)
        while len(datas) < quantidade:
            datas.append(d)
            d += timedelta(days=passo)
    elif rec["frequencia"] == "mensal":
        ano, mes = hoje.year, hoje.month
        while len(datas) < quantidade:
            d = date(ano, mes, rec["dia_mes"])
            if d > hoje:
                datas.append(d)
            mes += 1
            if mes > 12:
                mes, ano = 1, ano + 1
    else:  # anual
        base = date.fromisoformat(rec["data_base"])
        ano = hoje.year
        while len(datas) < quantidade:
            d = base.replace(year=ano)
            if d > hoje:
                datas.append(d)
            ano += 1
    return datas


@router.get("")
def listar(usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return rows(db.execute(
            """SELECT r.*, c.nome cliente, b.nome barbeiro, s.nome servico, s.preco
               FROM recorrencias r
               JOIN clientes c ON c.id=r.cliente_id
               JOIN barbeiros b ON b.id=r.barbeiro_id
               JOIN servicos s ON s.id=r.servico_id
               WHERE r.tenant_id=? AND r.ativo=1 ORDER BY r.frequencia, r.hora""",
            (usuario["tenant_id"],)))


@router.post("")
def criar(dados: RecorrenciaIn, usuario: dict = Depends(contexto_tenant)):
    if dados.frequencia not in ("semanal", "quinzenal", "mensal", "anual"):
        raise HTTPException(422, "Frequência inválida")
    if dados.frequencia in ("semanal", "quinzenal") and dados.dia_semana is None:
        raise HTTPException(422, "Informe o dia da semana (0=segunda ... 6=domingo)")
    if dados.frequencia == "mensal" and not (dados.dia_mes and 1 <= dados.dia_mes <= 28):
        raise HTTPException(422, "Informe o dia do mês (1 a 28)")
    if dados.frequencia == "anual" and not dados.data_base:
        raise HTTPException(422, "Informe a data base (YYYY-MM-DD)")
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO recorrencias (tenant_id, cliente_id, barbeiro_id, servico_id, frequencia,
                                         dia_semana, dia_mes, data_base, hora)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (usuario["tenant_id"], dados.cliente_id, dados.barbeiro_id, dados.servico_id,
             dados.frequencia, dados.dia_semana, dados.dia_mes, dados.data_base, dados.hora))
        return {"id": cur.lastrowid}


@router.post("/{rec_id}/gerar")
def gerar(rec_id: int, quantidade: int = 4, usuario: dict = Depends(contexto_tenant)):
    """Materializa os próximos N agendamentos da recorrência."""
    quantidade = min(max(quantidade, 1), 12)
    criados, pulados = [], []
    with get_db() as db:
        rec = row(db.execute("SELECT * FROM recorrencias WHERE id=? AND tenant_id=? AND ativo=1",
                             (rec_id, usuario["tenant_id"])))
        if not rec:
            raise HTTPException(404, "Recorrência não encontrada")
        for d in proximas_datas(rec, quantidade):
            inicio = f"{d.isoformat()}T{rec['hora']}"
            ja_existe = row(db.execute(
                "SELECT id FROM agendamentos WHERE recorrencia_id=? AND inicio=?", (rec_id, inicio)))
            if ja_existe:
                pulados.append({"inicio": inicio, "motivo": "já gerado"})
                continue
            try:
                ag = criar_agendamento(
                    db, usuario["tenant_id"],
                    AgendamentoIn(cliente_id=rec["cliente_id"], barbeiro_id=rec["barbeiro_id"],
                                  inicio=inicio, servico_ids=[rec["servico_id"]]),
                    recorrencia_id=rec_id)
                criados.append(ag)
            except HTTPException as exc:
                pulados.append({"inicio": inicio, "motivo": exc.detail})
    return {"criados": criados, "pulados": pulados}


@router.delete("/{rec_id}")
def encerrar(rec_id: int, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        db.execute("UPDATE recorrencias SET ativo=0 WHERE id=? AND tenant_id=?", (rec_id, usuario["tenant_id"]))
    return {"mensagem": "Recorrência encerrada (agendamentos já gerados são mantidos)"}
