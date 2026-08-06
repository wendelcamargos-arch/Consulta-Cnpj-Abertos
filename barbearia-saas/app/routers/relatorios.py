"""Relatórios gerenciais: DRE com plano de categorias, desempenho e KPIs.

DRE gerencial em regime de caixa (docs/DATABASE.md):
  Receita bruta (serviços + produtos + aluguel de cadeiras + outras)
  (−) Descontos e estornos             = Receita líquida de deduções
  (−) Impostos                          = Receita líquida
  (−) Comissões (−) CMV (−) Custos variáveis = Margem de contribuição
  (−) Despesas fixas (−) Outras saídas  = Resultado gerencial
Movimentos de sessão (abertura/reforço/sangria) NÃO entram no DRE — são
movimentação de caixa, não resultado.
"""
from fastapi import APIRouter, Depends

from ..auth import contexto_tenant
from ..db import get_db, row, rows
from ..util import agora_tenant

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
    t = usuario["tenant_id"]
    with get_db() as db:
        competencia = competencia or agora_tenant(db, t).strftime("%Y-%m")
        receita_servicos = _soma(db, t, competencia, "entrada", ("servico",))
        receita_produtos = _soma(db, t, competencia, "entrada", ("produto",))
        receita_alugueis = _soma(db, t, competencia, "entrada", ("aluguel_cadeira",))
        outras_receitas = _soma(db, t, competencia, "entrada", ("outro",))
        receita_bruta = round(receita_servicos + receita_produtos + receita_alugueis + outras_receitas, 2)

        descontos = _soma(db, t, competencia, "saida", ("desconto",))
        estornos = _soma(db, t, competencia, "saida", ("estorno",))
        receita_apos_deducoes = round(receita_bruta - descontos - estornos, 2)

        impostos = _soma(db, t, competencia, "saida", ("imposto",))
        receita_liquida = round(receita_apos_deducoes - impostos, 2)

        comissoes = _soma(db, t, competencia, "saida", ("comissao",))
        cmv = _soma(db, t, competencia, "saida", ("cmv",))
        custos_variaveis = _soma(db, t, competencia, "saida", ("despesa_variavel",))
        margem_contribuicao = round(receita_liquida - comissoes - cmv - custos_variaveis, 2)

        despesas_fixas = _soma(db, t, competencia, "saida", ("despesa_fixa",))
        outras_saidas = _soma(db, t, competencia, "saida", ("outro",))
        resultado = round(margem_contribuicao - despesas_fixas - outras_saidas, 2)

    return {
        "competencia": competencia,
        "receita_bruta": receita_bruta,
        "detalhe_receita": {"servicos": receita_servicos, "produtos": receita_produtos,
                            "aluguel_cadeiras": receita_alugueis, "outras": outras_receitas},
        "descontos": descontos,
        "estornos": estornos,
        "impostos": impostos,
        "receita_liquida": receita_liquida,
        "comissoes": comissoes,
        "cmv": cmv,
        "custos_variaveis": custos_variaveis,
        "margem_contribuicao": margem_contribuicao,
        "despesas_fixas": despesas_fixas,
        "outras_saidas": outras_saidas,
        "lucro_liquido": resultado,
        "margem_liquida_pct": round(resultado / receita_bruta * 100, 1) if receita_bruta else 0,
    }


@router.get("/barbeiros")
def desempenho_barbeiros(competencia: str = "", usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        competencia = competencia or agora_tenant(db, usuario["tenant_id"]).strftime("%Y-%m")
        lista = rows(db.execute(
            """SELECT b.id, b.nome, b.modelo,
                      COUNT(a.id) atendimentos,
                      COALESCE(SUM(CASE WHEN a.status IN ('pago','pago_parcial') THEN a.valor_total END),0) faturamento,
                      SUM(CASE WHEN a.status='no_show' THEN 1 ELSE 0 END) no_shows
               FROM barbeiros b
               LEFT JOIN agendamentos a ON a.barbeiro_id=b.id AND a.inicio LIKE ?
               WHERE b.tenant_id=? AND b.ativo=1
               GROUP BY b.id, b.nome, b.modelo ORDER BY faturamento DESC""",
            (f"{competencia}%", usuario["tenant_id"])))
        for b in lista:
            com = row(db.execute(
                """SELECT COALESCE(SUM(valor),0) v FROM commissions
                   WHERE barbeiro_id=? AND criado_em LIKE ?""", (b["id"], f"{competencia}%")))
            b["comissoes"] = round(com["v"], 2)
    return lista


@router.get("/indicadores")
def indicadores(competencia: str = "", usuario: dict = Depends(contexto_tenant)):
    t = usuario["tenant_id"]
    with get_db() as db:
        competencia = competencia or agora_tenant(db, t).strftime("%Y-%m")
        ags = row(db.execute(
            """SELECT COUNT(*) total,
                      SUM(CASE WHEN status='no_show' THEN 1 ELSE 0 END) no_shows,
                      SUM(CASE WHEN status='cancelado' THEN 1 ELSE 0 END) cancelados,
                      SUM(CASE WHEN status IN ('pago','pago_parcial') THEN 1 ELSE 0 END) pagos,
                      COALESCE(SUM(CASE WHEN status IN ('pago','pago_parcial') THEN valor_total END),0) faturado
               FROM agendamentos WHERE tenant_id=? AND inicio LIKE ?""", (t, f"{competencia}%")))
        msgs = row(db.execute(
            """SELECT COUNT(*) enviadas,
                      SUM(CASE WHEN resposta='confirmar' THEN 1 ELSE 0 END) confirmadas
               FROM mensagens_whatsapp
               WHERE tenant_id=? AND tipo='confirmacao' AND status IN ('enviada','entregue','lida')
                 AND agendada_para LIKE ?""", (t, f"{competencia}%")))
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


@router.get("/auditoria")
def auditoria(limite: int = 100, usuario: dict = Depends(contexto_tenant)):
    with get_db() as db:
        return rows(db.execute(
            """SELECT a.*, u.nome usuario FROM audit_logs a LEFT JOIN usuarios u ON u.id=a.usuario_id
               WHERE a.tenant_id=? ORDER BY a.id DESC LIMIT ?""",
            (usuario["tenant_id"], min(limite, 500))))
