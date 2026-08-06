"""Relatórios gerenciais: DRE mensal, desempenho por barbeiro e indicadores."""
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import contexto_tenant
from ..db import get_db, row, rows

router = APIRouter(prefix="/api/relatorios", tags=["relatorios"])


def _soma(db, tenant_id: int, competencia: str, tipo: str, categorias: tuple[str, ...]) -> float:
    marcadores = ",".join("?" * len(categorias))
    r = row(db.execute(
        f"""SELECT COALESCE(SUM(valor),0) v FROM lancamentos_caixa
            WHERE tenant_id=? AND tipo=? AND categoria IN ({marcadores}) AND data LIKE ?""",
        (tenant_id, tipo, *categorias, f"{competencia}%")))
    return round(r["v"], 2)


@router.get("/dre")
def dre(competencia: str = "", usuario: dict = Depends(contexto_tenant)):
    """DRE gerencial do mês (competencia = YYYY-MM), regime de caixa."""
    competencia = competencia or date.today().strftime("%Y-%m")
    t = usuario["tenant_id"]
    with get_db() as db:
        receita_servicos = _soma(db, t, competencia, "entrada", ("servico",))
        receita_produtos = _soma(db, t, competencia, "entrada", ("produto",))
        receita_alugueis = _soma(db, t, competencia, "entrada", ("aluguel_cadeira",))
        outras_receitas = _soma(db, t, competencia, "entrada", ("outro",))
        receita_bruta = round(receita_servicos + receita_produtos + receita_alugueis + outras_receitas, 2)

        impostos = _soma(db, t, competencia, "saida", ("imposto",))
        receita_liquida = round(receita_bruta - impostos, 2)

        comissoes = _soma(db, t, competencia, "saida", ("comissao",))
        custos_variaveis = _soma(db, t, competencia, "saida", ("despesa_variavel",))
        margem_contribuicao = round(receita_liquida - comissoes - custos_variaveis, 2)

        despesas_fixas = _soma(db, t, competencia, "saida", ("despesa_fixa",))
        outras_saidas = _soma(db, t, competencia, "saida", ("outro",))
        resultado = round(margem_contribuicao - despesas_fixas - outras_saidas, 2)

    return {
        "competencia": competencia,
        "receita_bruta": receita_bruta,
        "detalhe_receita": {"servicos": receita_servicos, "produtos": receita_produtos,
                            "aluguel_cadeiras": receita_alugueis, "outras": outras_receitas},
        "impostos": impostos,
        "receita_liquida": receita_liquida,
        "comissoes": comissoes,
        "custos_variaveis": custos_variaveis,
        "margem_contribuicao": margem_contribuicao,
        "despesas_fixas": despesas_fixas,
        "outras_saidas": outras_saidas,
        "lucro_liquido": resultado,
        "margem_liquida_pct": round(resultado / receita_bruta * 100, 1) if receita_bruta else 0,
    }


@router.get("/barbeiros")
def desempenho_barbeiros(competencia: str = "", usuario: dict = Depends(contexto_tenant)):
    competencia = competencia or date.today().strftime("%Y-%m")
    with get_db() as db:
        return rows(db.execute(
            """SELECT b.id, b.nome, b.modelo,
                      COUNT(a.id) atendimentos,
                      COALESCE(SUM(CASE WHEN a.status='pago' THEN a.valor_total END),0) faturamento,
                      SUM(CASE WHEN a.status='no_show' THEN 1 ELSE 0 END) no_shows
               FROM barbeiros b
               LEFT JOIN agendamentos a ON a.barbeiro_id=b.id AND a.inicio LIKE ?
               WHERE b.tenant_id=? AND b.ativo=1
               GROUP BY b.id ORDER BY faturamento DESC""",
            (f"{competencia}%", usuario["tenant_id"])))


@router.get("/indicadores")
def indicadores(competencia: str = "", usuario: dict = Depends(contexto_tenant)):
    """KPIs do mês: total de atendimentos, taxa de no-show, ticket médio, taxa de confirmação."""
    competencia = competencia or date.today().strftime("%Y-%m")
    t = usuario["tenant_id"]
    with get_db() as db:
        ags = row(db.execute(
            """SELECT COUNT(*) total,
                      SUM(CASE WHEN status='no_show' THEN 1 ELSE 0 END) no_shows,
                      SUM(CASE WHEN status='cancelado' THEN 1 ELSE 0 END) cancelados,
                      SUM(CASE WHEN status='pago' THEN 1 ELSE 0 END) pagos,
                      COALESCE(SUM(CASE WHEN status='pago' THEN valor_total END),0) faturado
               FROM agendamentos WHERE tenant_id=? AND inicio LIKE ?""", (t, f"{competencia}%")))
        msgs = row(db.execute(
            """SELECT COUNT(*) enviadas,
                      SUM(CASE WHEN resposta='confirmar' THEN 1 ELSE 0 END) confirmadas
               FROM mensagens_whatsapp
               WHERE tenant_id=? AND tipo='confirmacao' AND status='enviada' AND agendada_para LIKE ?""",
            (t, f"{competencia}%")))
        clientes_ativos = row(db.execute(
            "SELECT COUNT(DISTINCT cliente_id) c FROM agendamentos WHERE tenant_id=? AND inicio LIKE ?",
            (t, f"{competencia}%")))["c"]
        recorrentes = row(db.execute(
            "SELECT COUNT(*) c FROM recorrencias WHERE tenant_id=? AND ativo=1", (t,)))["c"]
    total = ags["total"] or 0
    return {
        "competencia": competencia,
        "agendamentos": total,
        "clientes_ativos": clientes_ativos,
        "recorrencias_ativas": recorrentes,
        "faturamento": round(ags["faturado"], 2),
        "ticket_medio": round(ags["faturado"] / ags["pagos"], 2) if ags["pagos"] else 0,
        "taxa_no_show_pct": round((ags["no_shows"] or 0) / total * 100, 1) if total else 0,
        "taxa_cancelamento_pct": round((ags["cancelados"] or 0) / total * 100, 1) if total else 0,
        "taxa_confirmacao_whatsapp_pct": round((msgs["confirmadas"] or 0) / msgs["enviadas"] * 100, 1) if msgs["enviadas"] else 0,
    }
