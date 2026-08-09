import os
from pathlib import Path

# Diretório base do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# Paths
DOWNLOAD_PATH = os.getenv("CNPJ_DOWNLOAD_PATH", str(BASE_DIR / "data" / "raw"))

# Caminho do banco DuckDB — FONTE ÚNICA DE VERDADE.
# Respeita a variável de ambiente CNPJ_DATABASE_FILE (aceita caminho absoluto
# ou relativo ao diretório do projeto). Default mantém o banco existente para
# não quebrar dados de amostra nem os testes.
DATABASE_FILE = os.getenv(
    "CNPJ_DATABASE_FILE",
    str(BASE_DIR / "database" / "cnpj_hunter.duckdb"),
)

_database_path = Path(DATABASE_FILE)
if not _database_path.is_absolute():
    _database_path = BASE_DIR / _database_path
DATABASE_PATH = _database_path.resolve()

# Caminho do schema SQL aplicado na inicialização do banco.
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

# Limites de busca
MAX_DAYS_SEARCH = int(os.getenv("CNPJ_MAX_DAYS_SEARCH", "10"))
MAX_RESULTS = int(os.getenv("CNPJ_MAX_RESULTS", "10000"))

# Comportamento
AUTO_UPDATE = os.getenv("CNPJ_AUTO_UPDATE", "true").lower() in ("1", "true", "yes", "on")

# URLs oficiais (configuráveis)
# URL preferencial usada pelo OfficialService para detectar arquivos oficiais
OFFICIAL_BASE_URL = os.getenv(
    "CNPJ_OFFICIAL_BASE_URL",
    "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/",
)
# URL alternativa oficial de fallback
OFFICIAL_FALLBACK_URL = os.getenv(
    "CNPJ_OFFICIAL_FALLBACK_URL",
    "https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/",
)
# Versão manual (YYYY-MM) usada quando não for possível detectar automaticamente
CNPJ_VERSION = os.getenv("CNPJ_VERSION", "").strip()


def ensure_paths() -> None:
    """Garante que os diretórios configurados existam."""
    Path(DOWNLOAD_PATH).mkdir(parents=True, exist_ok=True)
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
