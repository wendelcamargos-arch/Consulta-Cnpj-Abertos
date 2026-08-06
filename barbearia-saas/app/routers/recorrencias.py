"""Recorrência robusta: semanal, quinzenal, mensal e anual.

Cada geração materializa ocorrências (recurrence_occurrences) com resultado
auditável. Conflitos NUNCA geram reserva silenciosa — a política do tenant
(ou da recorrência) decide:
  pular     → registra 'pulada' com motivo
  sugerir   → procura horário alternativo no mesmo dia (passos de 30min) e agenda
  pendencia → registra 'pendente' para a recepção resolver
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..audit import auditar
from ..auth import contexto_tenant
from ..db import get_db, row, rows
from ..util import agora_tenant, dia_fechado, settings_tenant
from .agendamentos import AgendamentoIn, cancelar_mensagens_do_agendamento, criar_agendamento

router = APIRouter(prefix="/api/recorrencias", tags=["recorrencias"])


class RecorrenciaIn(BaseModel):
    cliente_id: int
    barbeiro_id: int
    servico_id: int
    frequencia: str
    hora: str
    dia_semana: int | None = None
    dia_mes: int | None = None
    data_base: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    max_ocorrencias: int | None = None
    politica: str | None = None      # NULL = usa a política do tenant


def proximas_datas(rec: dict, quantidade: int, hoje: date) -> list[date]:
    inicio = max(hoje, date.fromisoformat(rec["data_inicio"])) if rec.get("data_inicio") else hoje
    limite = date.fromisoformat(rec["data_fim"]) if rec.get("data_fim") else None
    datas: list[date] = []
    if rec["frequencia"] in ("semanal", "quinzenal"):
        passo = 7 if rec["frequencia"] == "semanal" else 14
        d = inicio + timedelta(days=(rec["dia_semana"] - inicio.weekday()) % 7 or 7)
        while len(datas) < quantidade and (not limite or d <= limite):
            datas.append(d)
            d += timedelta(days=passo)
    elif rec["frequencia"] == "mensal":
        ano, mes = inicio.year, inicio.month
        while len(datas) < quantidade:
            d = date(ano, mes, rec["dia_mes"])
            if d > inicio and (not limite or d <= limite):
                datas.append(d)
            elif limite and d > limite:
                break
            mes += 1
            if mes > 12:
                mes, ano = 1, ano + 1
    else:  # anual
        base = date.fromisoformat(rec["data_base"])
        ano = inicio.year
        while len(datas) < quantidade:
            dia, mes = base.day, base.month
            if mes == 2 and dia == 29:
                try:
                    d = date(ano, 2, 29)
                except ValueError:
                    d = date(ano, 2, 28)   # 29/02 em ano não bissexto → 28/02
            else:
                d = date(ano, mes, dia)
            if d > inicio and (not limite or d <= limite):
                datas.append(d)
            elif limite and d > limite:
                break
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


@router.get("/{rec_id}/ocorrencias")
def ocorrencias(rec_id: int, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return rows(db.execute(
            "SELECT * FROM recurrence_occurrences WHERE recorrencia_id=? AND tenant_id=? ORDER BY data",
            (rec_id, usuario["tenant_id"])))


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
    if dados.politica and dados.politica not in ("pular", "sugerir", "pendencia"):
        raise HTTPException(422, "Política deve ser pular, sugerir ou pendencia")
    with get_db() as db:
        rec_id = db.insert(
            """INSERT INTO recorrencias (tenant_id, cliente_id, barbeiro_id, servico_id, frequencia,
                                         dia_semana, dia_mes, data_base, hora,
                                         data_inicio, data_fim, max_ocorrencias, politica)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (usuario["tenant_id"], dados.cliente_id, dados.barbeiro_id, dados.servico_id,
             dados.frequencia, dados.dia_semana, dados.dia_mes, dados.data_base, dados.hora,
             dados.data_inicio, dados.data_fim, dados.max_ocorrencias, dados.politica))
        auditar(db, usuario["tenant_id"], usuario["uid"], "recorrencia_criada", "recorrencia", rec_id)
        return {"id": rec_id}


def _sugerir_horario(db, tenant_id: int, rec: dict, d: date, duracao: int) -> str | None:
    """Procura slot livre no mesmo dia, passos de 30min dentro do expediente."""
    b = row(db.execute("SELECT * FROM barbeiros WHERE id=?", (rec["barbeiro_id"],)))
    base = datetime.fromisoformat(f"{d.isoformat()}T{b['hora_inicio']}")
    fim_expediente = datetime.fromisoformat(f"{d.isoformat()}T{b['hora_fim']}")
    atual = base
    while atual + timedelta(minutes=duracao) <= fim_expediente:
        inicio = atual.strftime("%Y-%m-%dT%H:%M")
        fim = (atual + timedelta(minutes=duracao)).strftime("%Y-%m-%dT%H:%M")
        ocupado = row(db.execute(
            """SELECT id FROM agendamentos WHERE barbeiro_id=? AND status NOT IN ('cancelado','no_show')
               AND inicio < ? AND fim > ?""", (rec["barbeiro_id"], fim, inicio)))
        bloqueado = row(db.execute(
            "SELECT id FROM barber_blocks WHERE barbeiro_id=? AND inicio < ? AND fim > ?",
            (rec["barbeiro_id"], fim, inicio)))
        if not ocupado and not bloqueado:
            return atual.strftime("%H:%M")
        atual += timedelta(minutes=30)
    return None


@router.post("/{rec_id}/gerar")
def gerar(rec_id: int, quantidade: int = 4, usuario: dict = Depends(contexto_tenant)):
    quantidade = min(max(quantidade, 1), 12)
    resultado = {"criados": [], "pulados": [], "pendentes": [], "sugeridos": []}
    with get_db() as db:
        rec = row(db.execute("SELECT * FROM recorrencias WHERE id=? AND tenant_id=? AND ativo=1",
                             (rec_id, usuario["tenant_id"])))
        if not rec:
            raise HTTPException(404, "Recorrência não encontrada")
        cfg = settings_tenant(db, usuario["tenant_id"])
        politica = rec["politica"] or cfg["politica_recorrencia"]
        servico = row(db.execute("SELECT * FROM servicos WHERE id=?", (rec["servico_id"],)))

        if rec["max_ocorrencias"]:
            geradas = row(db.execute(
                "SELECT COUNT(*) c FROM recurrence_occurrences WHERE recorrencia_id=? AND status IN ('gerada','sugerida')",
                (rec_id,)))["c"]
            quantidade = min(quantidade, max(rec["max_ocorrencias"] - geradas, 0))

        hoje = agora_tenant(db, usuario["tenant_id"]).date()
        for d in proximas_datas(rec, quantidade, hoje):
            if row(db.execute("SELECT id FROM recurrence_occurrences WHERE recorrencia_id=? AND data=?",
                              (rec_id, d.isoformat()))):
                continue  # ocorrência já tratada

            def registrar(status: str, motivo: str = "", ag_id: int | None = None, hora: str | None = None):
                db.execute(
                    """INSERT INTO recurrence_occurrences (tenant_id, recorrencia_id, data, hora, status, motivo, agendamento_id)
                       VALUES (?,?,?,?,?,?,?)""",
                    (usuario["tenant_id"], rec_id, d.isoformat(), hora or rec["hora"], status, motivo, ag_id))

            if dia_fechado(cfg, d):
                if politica == "pular":
                    registrar("pulada", "dia fechado")
                    resultado["pulados"].append({"data": d.isoformat(), "motivo": "dia fechado"})
                else:
                    registrar("pendente", "dia fechado")
                    resultado["pendentes"].append({"data": d.isoformat(), "motivo": "dia fechado"})
                continue

            def tentar(hora: str):
                return criar_agendamento(
                    db, usuario["tenant_id"],
                    AgendamentoIn(cliente_id=rec["cliente_id"], barbeiro_id=rec["barbeiro_id"],
                                  inicio=f"{d.isoformat()}T{hora}", servico_ids=[rec["servico_id"]]),
                    recorrencia_id=rec_id)

            try:
                ag = tentar(rec["hora"])
                registrar("gerada", ag_id=ag["id"])
                resultado["criados"].append(ag)
            except HTTPException as exc:
                if politica == "pular":
                    registrar("pulada", exc.detail)
                    resultado["pulados"].append({"data": d.isoformat(), "motivo": exc.detail})
                elif politica == "sugerir":
                    alternativa = _sugerir_horario(db, usuario["tenant_id"], rec, d, servico["duracao_min"])
                    if alternativa:
                        ag = tentar(alternativa)
                        registrar("sugerida", f"horário original {rec['hora']} ocupado", ag["id"], alternativa)
                        resultado["sugeridos"].append({"data": d.isoformat(), "hora": alternativa})
                    else:
                        registrar("pendente", f"sem horário livre ({exc.detail})")
                        resultado["pendentes"].append({"data": d.isoformat(), "motivo": "sem horário livre"})
                else:
                    registrar("pendente", exc.detail)
                    resultado["pendentes"].append({"data": d.isoformat(), "motivo": exc.detail})
    return resultado


@router.delete("/{rec_id}/ocorrencia/{data}")
def cancelar_ocorrencia(rec_id: int, data: str, usuario: dict = Depends(contexto_tenant)):
    """Cancela UMA ocorrência da série (e o agendamento gerado, se houver)."""
    with get_db() as db:
        oc = row(db.execute(
            "SELECT * FROM recurrence_occurrences WHERE recorrencia_id=? AND data=? AND tenant_id=?",
            (rec_id, data, usuario["tenant_id"])))
        if not oc:
            raise HTTPException(404, "Ocorrência não encontrada")
        if oc["agendamento_id"]:
            db.execute("UPDATE agendamentos SET status='cancelado' WHERE id=? AND status NOT IN ('pago','pago_parcial')",
                       (oc["agendamento_id"],))
            cancelar_mensagens_do_agendamento(db, oc["agendamento_id"])
        db.execute("UPDATE recurrence_occurrences SET status='cancelada' WHERE id=?", (oc["id"],))
        auditar(db, usuario["tenant_id"], usuario["uid"], "ocorrencia_cancelada", "recorrencia", rec_id, data)
    return {"mensagem": f"Ocorrência de {data} cancelada"}


@router.delete("/{rec_id}")
def encerrar(rec_id: int, cancelar_futuros: bool = False, usuario: dict = Depends(contexto_tenant)):
    """Encerra a série. cancelar_futuros=true também cancela agendamentos futuros já gerados."""
    with get_db() as db:
        rec = row(db.execute("SELECT id FROM recorrencias WHERE id=? AND tenant_id=?",
                             (rec_id, usuario["tenant_id"])))
        if not rec:
            raise HTTPException(404, "Recorrência não encontrada")
        db.execute("UPDATE recorrencias SET ativo=0 WHERE id=?", (rec_id,))
        cancelados = 0
        if cancelar_futuros:
            agora = agora_tenant(db, usuario["tenant_id"]).strftime("%Y-%m-%dT%H:%M")
            futuros = rows(db.execute(
                """SELECT id FROM agendamentos WHERE recorrencia_id=? AND inicio>?
                   AND status NOT IN ('pago','pago_parcial','cancelado','no_show')""", (rec_id, agora)))
            for ag in futuros:
                db.execute("UPDATE agendamentos SET status='cancelado' WHERE id=?", (ag["id"],))
                cancelar_mensagens_do_agendamento(db, ag["id"])
                cancelados += 1
        auditar(db, usuario["tenant_id"], usuario["uid"], "recorrencia_encerrada", "recorrencia", rec_id,
                f"futuros_cancelados={cancelados}")
    return {"mensagem": "Recorrência encerrada", "agendamentos_cancelados": cancelados}
