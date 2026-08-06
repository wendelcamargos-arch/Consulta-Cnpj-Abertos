"""Seed de demonstração — PROIBIDO em produção.

Só executa quando APP_ENV != production E DEMO_MODE=1 (explícito).
Uso: DEMO_MODE=1 python -m app.seed
"""
import os
import sys
from datetime import datetime

from .auth import hash_senha
from .db import get_db, init_db, row


def seed():
    if os.environ.get("APP_ENV", "development") == "production":
        print("ERRO: seed de demonstração é proibido em produção.", file=sys.stderr)
        sys.exit(1)
    if os.environ.get("DEMO_MODE") != "1":
        print("ERRO: defina DEMO_MODE=1 para aplicar o seed de demonstração.", file=sys.stderr)
        sys.exit(1)

    init_db()
    with get_db() as db:
        if row(db.execute("SELECT id FROM usuarios WHERE email='admin@plataforma.com'")):
            print("Seed já aplicado.")
            return

        db.execute("INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (NULL,?,?,?,'superadmin')",
                   ("Admin Plataforma", "admin@plataforma.com", hash_senha("admin123")))

        t = db.insert(
            "INSERT INTO tenants (nome, slug, cor_primaria, telefone_whatsapp, plano, mensalidade) VALUES (?,?,?,?,?,?)",
            ("Barbearia Prime", "prime", "#C9A227", "5534999990000", "mensal", 199.90))
        db.execute("INSERT INTO tenant_settings (tenant_id) VALUES (?)", (t,))
        db.execute("INSERT INTO birthday_campaigns (tenant_id) VALUES (?)", (t,))

        db.execute("INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (?,?,?,?,'gerente')",
                   (t, "João Gerente", "gerente@prime.com", hash_senha("gerente123")))
        db.execute("INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (?,?,?,?,'recepcao')",
                   (t, "Maria Recepção", "recepcao@prime.com", hash_senha("recepcao123")))

        db.execute("""INSERT INTO barbeiros (tenant_id, nome, telefone, modelo, percentual_comissao) VALUES
                      (?, 'Carlos Tesoura', '34988880001', 'comissao', 50)""", (t,))
        db.execute("""INSERT INTO barbeiros (tenant_id, nome, telefone, modelo, valor_aluguel, percentual_comissao) VALUES
                      (?, 'Rafael Navalha', '34988880002', 'aluguel_cadeira', 1200, 0)""", (t,))

        servicos = [("Corte masculino", 45, 30), ("Barba completa", 35, 30),
                    ("Sobrancelha", 15, 15), ("Pigmentação", 60, 45), ("Hidratação", 40, 30)]
        ids = {}
        for nome, preco, dur in servicos:
            ids[nome] = db.insert("INSERT INTO servicos (tenant_id, nome, preco, duracao_min) VALUES (?,?,?,?)",
                                  (t, nome, preco, dur))
        combo = db.insert(
            "INSERT INTO servicos (tenant_id, nome, preco, duracao_min, eh_combo) VALUES (?, 'Combo Corte + Barba', 70, 60, 1)",
            (t,))
        for s in ("Corte masculino", "Barba completa"):
            db.execute("INSERT INTO combo_itens (combo_id, servico_id) VALUES (?,?)", (combo, ids[s]))

        hoje = datetime.now()
        clientes = [("João da Silva", "39053344705", "34999110001", f"{hoje.month:02d}-15"),
                    ("Pedro Souza", "", "34999110002", "03-22"),
                    ("Lucas Almeida", "", "34999110003", f"{hoje.month:02d}-28")]
        for nome, cpf, tel, aniv in clientes:
            cid = db.insert("INSERT INTO clientes (tenant_id, nome, cpf, telefone, aniversario) VALUES (?,?,?,?,?)",
                            (t, nome, cpf, tel, aniv))
            db.execute("INSERT INTO customer_consents (tenant_id, cliente_id, tipo, concedido) VALUES (?,?, 'marketing', 1)",
                       (t, cid))

        for nome, valor in (("Pomada Premium", 55), ("Óleo para barba", 42), ("Shampoo antiqueda", 38)):
            db.execute(
                "INSERT INTO produtos (tenant_id, nome, custo, custo_medio, preco_venda, quantidade, estoque_minimo) VALUES (?,?,?,?,?,10,3)",
                (t, nome, round(valor * 0.5, 2), round(valor * 0.5, 2), valor))

        mes = hoje.strftime("%Y-%m")
        for data, cat, desc, valor in ((f"{mes}-05", "despesa_fixa", "Aluguel do ponto", 3500),
                                       (f"{mes}-05", "despesa_fixa", "Energia + internet", 480)):
            db.execute("INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor) VALUES (?,?,'saida',?,?,?)",
                       (t, data, cat, desc, valor))
        db.execute("""INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor) VALUES
                      (?, ?, 'entrada', 'aluguel_cadeira', 'Aluguel de cadeira — Rafael Navalha', 1200)""", (t, f"{mes}-01"))

    print("Seed de demonstração aplicado (DEMO_MODE).")
    print("Logins: admin@plataforma.com/admin123 · gerente@prime.com/gerente123 · recepcao@prime.com/recepcao123")


if __name__ == "__main__":
    seed()
