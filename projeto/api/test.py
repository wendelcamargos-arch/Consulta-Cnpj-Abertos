from fastapi import APIRouter, HTTPException
from fastapi.logger import logger
from pathlib import Path
import json

from services.download_service import DownloadService
from services.database_service import DatabaseService

router = APIRouter()


@router.get("/test/status")
def test_status():
    try:
        # Read last download metadata
        meta = {}
        if DownloadService.METADATA_PATH.exists():
            try:
                meta = json.loads(DownloadService.METADATA_PATH.read_text(encoding='utf-8'))
            except Exception:
                meta = {"error": "invalid metadata"}

        # DB counts
        stats = {}
        with DatabaseService.get_connection() as conn:
            try:
                stats['total_companies'] = conn.execute("SELECT COUNT(*) FROM company_data").fetchone()[0]
            except Exception:
                stats['total_companies'] = 0
            try:
                stats['active_companies'] = conn.execute("SELECT COUNT(*) FROM company_data WHERE situacao_cadastral LIKE 'Ativa' OR situacao_cadastral LIKE 'ATIVA'").fetchone()[0]
            except Exception:
                stats['active_companies'] = 0

        return {"success": True, "metadata": meta, "db_stats": stats}
    except Exception as exc:
        logger.exception("Falha ao obter status de teste: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
