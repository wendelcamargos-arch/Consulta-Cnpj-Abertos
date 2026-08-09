"""Prova de dados reais: ingere arquivos no FORMATO OFICIAL da Receita Federal
(posicional, sem cabeçalho, ';', latin-1) e verifica que /search retorna
resultados reais de SP.

Os arquivos da Receita não têm cabeçalho e trazem UF/município/situação apenas
em Estabelecimentos — este teste exercita o importador RF-nativo
(ImportService.import_receita_dataset via OfficialService.ingest_state) que junta
Empresas + Estabelecimentos e popula a tabela denormalizada `empresas`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.main import app
from services.database_service import DatabaseService
from services.official_service import OfficialService

client = TestClient(app)


def _gen_rf_files(out_dir: Path, uf: str = "SP", n: int = 500, muni_code: str = "7107"):
    """Gera Empresas + Estabelecimentos no layout REAL da RF (latin-1, sem header)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    emp = out_dir / "K3241.K03200Y0.D40118.EMPRECSV"
    est = out_dir / "K3241.K03200Y0.D40118.ESTABELE"

    cnaes = ["6201501", "4711302", "5611201"]
    situacoes = ["02", "02", "08"]  # maioria Ativa

    with emp.open("w", encoding="latin-1", newline="\n") as fe, \
         est.open("w", encoding="latin-1", newline="\n") as fs:
        for i in range(n):
            basico = f"{i:08d}"
            capital = f"{(i % 100 + 1) * 1000},00"
            fe.write(f'"{basico}";"EMPRESA {uf} {i} LTDA";"2062";"49";"{capital}";"03";""\n')

            dia = 15 + (i % 10)  # janela 2024-01-15..2024-01-24
            cols = [
                basico, "0001", f"{i % 100:02d}", "1", f"FANTASIA {i}",
                situacoes[i % 3], f"202401{dia:02d}", "00", "", "",
                "20180101", cnaes[i % 3], "", "RUA", f"LOG {i}", str(i),
                "", f"BAIRRO {i % 10}", "01001000", uf, muni_code,
                "11", f"3{i:07d}"[:8], "", "", "", "",
                f"c{i}@e{i}.com.br", "", "",
            ]
            fs.write(";".join(f'"{c}"' for c in cols) + "\n")
    return emp, est


def test_search_returns_real_sp_data(tmp_path, monkeypatch):
    # Banco temporário isolado (não polui o banco de amostra versionado).
    db_file = tmp_path / "sp_real.duckdb"
    monkeypatch.setattr(DatabaseService, "DATABASE_PATH", db_file)
    DatabaseService.initialize_database()

    # Tabela de apoio para traduzir o código de município (7107 -> Sao Paulo).
    with DatabaseService.get_connection() as conn:
        conn.execute("INSERT INTO municipios VALUES ('7107', 'Sao Paulo', 'SP')")

    emp, est = _gen_rf_files(tmp_path, uf="SP", n=500)

    report = OfficialService.ingest_state(
        "SP", empresas_path=emp, estabelecimentos_path=est, replace=True
    )
    assert report["empresas"] == 500

    # /search com janela de 10 dias e filtro SP deve retornar dados reais.
    resp = client.post(
        "/search",
        json={
            "start_date": "2024-01-15",
            "end_date": "2024-01-24",
            "uf": "SP",
            "limit": 100,
            "page": 1,
            "pageSize": 10,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["total_count"] == 500
    assert len(data["results"]) >= 1
    assert all(item["uf"] == "SP" for item in data["results"])

    first = data["results"][0]
    # CNPJ de 14 dígitos montado a partir de basico+ordem+dv (prova de layout real).
    assert len(first["cnpj"]) == 14 and first["cnpj"].isdigit()
    # Município traduzido do código e situação mapeada de '02' -> 'Ativa'.
    assert first["municipio"] == "Sao Paulo"
    assert first["situacao"] in {"Ativa", "Baixada"}


def test_real_cnae_filter_on_sp_data(tmp_path, monkeypatch):
    db_file = tmp_path / "sp_real2.duckdb"
    monkeypatch.setattr(DatabaseService, "DATABASE_PATH", db_file)
    DatabaseService.initialize_database()

    emp, est = _gen_rf_files(tmp_path, uf="SP", n=300)
    OfficialService.ingest_state("SP", empresas_path=emp, estabelecimentos_path=est, replace=True)

    resp = client.post(
        "/search",
        json={
            "start_date": "2024-01-15",
            "end_date": "2024-01-24",
            "uf": "SP",
            "cnae": "6201501",
            "limit": 500,
            "page": 1,
            "pageSize": 500,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # 1/3 das linhas usam o CNAE 6201501.
    assert data["total_count"] == 100
    assert all(item["cnpj"].isdigit() for item in data["results"])
