"""Seed de demonstração: superadmin da plataforma + Barbearia Prime com dados.

Uso: python -m app.seed
Logins criados:
  admin@plataforma.com / admin123        (superadmin — painel de tenants)
  gerente@prime.com   / gerente123       (gerente da Barbearia Prime)
  recepcao@prime.com  / recepcao123      (recepção da Barbearia Prime)
"""
from datetime import datetime, timedelta

from .auth import hash_senha
from .db import get_db, init_db, row


def seed():
    init_db()
    with get_db() as db:
        if row(db.execute("SELECT id FROM usuarios WHERE email='admin@plataforma.com'")):
            print("Seed já aplicado.")
            return

        db.execute("INSERT INTO usuarios (tenant_id, nome, email, senha_hash, papel) VALUES (NULL,?,?,?,'superadmin')",
                   ("Admin Plataforma", "admin@plataforma.com", hash_senha("admin123")))

        cur = db.execute(
            "INSERT INTO tenants (nome, slug, cor_primaria, telefone_whatsapp, plano, mensalidade) VALUES (?,?,?,?,?,?)",
            ("Barbearia Prime", "prime", "#C9A227", "5534999990000", "mensal", 199.90))
        t = cur.lastrowid

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
            c = db.execute("INSERT INTO servicos (tenant_id, nome, preco, duracao_min) VALUES (?,?,?,?)",
                           (t, nome, preco, dur))
            ids[nome] = c.lastrowid
        combo = db.execute(
            "INSERT INTO servicos (tenant_id, nome, preco, duracao_min, eh_combo) VALUES (?, 'Combo Corte + Barba', 70, 60, 1)",
            (t,)).lastrowid
        for s in ("Corte masculino", "Barba completa"):
            db.execute("INSERT INTO combo_itens (combo_id, servico_id) VALUES (?,?)", (combo, ids[s]))

        hoje = datetime.now()
        clientes = [("João da Silva", "39053344705", "34999110001", f"{hoje.month:02d}-15"),
                    ("Pedro Souza", "", "34999110002", "03-22"),
                    ("Lucas Almeida", "", "34999110003", f"{hoje.month:02d}-28")]
        for nome, cpf, tel, aniv in clientes:
            db.execute("INSERT INTO clientes (tenant_id, nome, cpf, telefone, aniversario) VALUES (?,?,?,?,?)",
                       (t, nome, cpf, tel, aniv))

        for nome, valor in (("Pomada Premium", 55), ("Óleo para barba", 42), ("Shampoo antiqueda", 38)):
            db.execute(
                "INSERT INTO produtos (tenant_id, nome, custo, preco_venda, quantidade, estoque_minimo) VALUES (?,?,?,?,10,3)",
                (t, nome, round(valor * 0.5, 2), valor))

        mes = hoje.strftime("%Y-%m")
        db.execute("""INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor) VALUES
                      (?, ?, 'saida', 'despesa_fixa', 'Aluguel do ponto', 3500)""", (t, f"{mes}-05"))
        db.execute("""INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor) VALUES
                      (?, ?, 'saida', 'despesa_fixa', 'Energia + internet', 480)""", (t, f"{mes}-05"))
        db.execute("""INSERT INTO lancamentos_caixa (tenant_id, data, tipo, categoria, descricao, valor) VALUES
                      (?, ?, 'entrada', 'aluguel_cadeira', 'Aluguel de cadeira — Rafael Navalha', 1200)""", (t, f"{mes}-01"))

    print("Seed aplicado com sucesso.")
    print("Logins: admin@plataforma.com/admin123 · gerente@prime.com/gerente123 · recepcao@prime.com/recepcao123")


if __name__ == "__main__":
    seed()
