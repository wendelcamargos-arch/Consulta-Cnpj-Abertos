-- Executado uma única vez na criação do volume do PostgreSQL (docker-compose).
-- btree_gist habilita a constraint de exclusão anti-dupla-reserva (app/schema.py).
CREATE EXTENSION IF NOT EXISTS btree_gist;
