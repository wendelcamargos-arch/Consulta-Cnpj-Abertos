import math
import re
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from services.download_service import DownloadService
from services.import_service import ImportService
from services.database_service import DatabaseService
from config import settings
from config.settings import DOWNLOAD_PATH

logger = logging.getLogger(__name__)


DATASET_KEYWORDS = {
    'empresas': ['empresa', 'empresas', 'RAZAO'],
    'estabelecimentos': ['estabele', 'estabelecimentos', 'ESTABELECIMENTO'],
    'simples': ['simples', 'sn', 'simplesnacional'],
    'cnaes': ['cnae', 'cnaes'],
    'naturezas': ['natureza', 'naturezas'],
    'municipios': ['municipio', 'municipios'],
}

OFFICIAL_FILE_NAMES = {
    'empresas': 'Empresas0.zip',
    'estabelecimentos': 'Estabelecimentos0.zip',
    'simples': 'Simples.zip',
    'cnaes': 'Cnaes.zip',
    'naturezas': 'Naturezas.zip',
    'municipios': 'Municipios.zip',
}


class OfficialService:
    RAW_DIR = Path(DOWNLOAD_PATH)

    @classmethod
    def _discover_latest_version_from_index(cls, base_url: str) -> Optional[str]:
        original_base = getattr(DownloadService, 'BASE_URL', None)
        try:
            DownloadService.BASE_URL = base_url
            html = DownloadService.fetch_download_page()
        except Exception as exc:
            logger.warning('Não foi possível acessar índice oficial %s: %s', base_url, exc)
            return None
        finally:
            if original_base is not None:
                DownloadService.BASE_URL = original_base

        matches = re.findall(r'href=["\'](?P<dir>\d{4}-\d{2})/(["\']|[^"\']*?["\'])', html)
        versions = sorted({match[0] for match in matches})
        if not versions:
            logger.warning('Nenhuma versão YYYY-MM encontrada no índice oficial %s', base_url)
            return None
        latest = versions[-1]
        logger.info('Versão oficial mais recente detectada: %s', latest)
        return latest

    @classmethod
    def _get_official_version(cls) -> Optional[str]:
        latest = cls._discover_latest_version_from_index(settings.OFFICIAL_BASE_URL)
        if latest:
            return latest

        manual_version = getattr(settings, 'CNPJ_VERSION', '').strip()
        if manual_version:
            logger.info('Índice principal inacessível; usando versão manual CNPJ_VERSION=%s', manual_version)
            return manual_version

        logger.warning('Não foi possível descobrir automaticamente a versão oficial e CNPJ_VERSION não está definido.')
        return None

    @classmethod
    def _build_official_candidate_urls(cls, version: str) -> Dict[str, Dict[str, str]]:
        base_url = settings.OFFICIAL_BASE_URL.rstrip('/') + '/'
        if not version.endswith('/'):
            version = version + '/'
        candidate_base = f"{base_url}{version}"
        return {
            key: {'name': filename, 'url': f"{candidate_base}{filename}"}
            for key, filename in OFFICIAL_FILE_NAMES.items()
        }

    @classmethod
    def discover_official_candidates(cls) -> Dict[str, Dict[str, str]]:
        """Constrói URLs oficiais com base no diretório de versão mais recente ou na versão manual."""
        version = cls._get_official_version()
        if not version:
            return {}
        return cls._build_official_candidate_urls(version)

    @classmethod
    def estimate_sizes(cls, candidates: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, Optional[int]]]:
        """Retorna estimativas de tamanho (bytes) para cada candidato usando HEAD requests."""
        estimates: Dict[str, Dict[str, Optional[int]]] = {}
        for key, info in candidates.items():
            url = info['url']
            headers = DownloadService._get_remote_headers(url)
            size = None
            try:
                size = int(headers.get('Content-Length') or headers.get('content-length') or 0) or None
            except Exception:
                size = None
            estimates[key] = {'name': info['name'], 'url': url, 'size': size}
        return estimates

    @classmethod
    def estimate_total(cls, estimates: Dict[str, Dict[str, Optional[int]]], bandwidth_bytes_per_s: int = 10 * 1024 * 1024) -> Dict[str, float]:
        """Estima tempo total de download (s) e tamanho total (bytes).

        `bandwidth_bytes_per_s` padrão 10 MB/s. Retorna dict com keys: total_bytes, total_seconds, per_file_seconds.
        """
        total = 0
        per_file = {}
        for k, info in estimates.items():
            s = info.get('size') or 0
            total += s
            per_file[k] = (s / bandwidth_bytes_per_s) if bandwidth_bytes_per_s > 0 else float('inf')

        total_seconds = total / bandwidth_bytes_per_s if bandwidth_bytes_per_s > 0 else float('inf')
        return {'total_bytes': total, 'total_seconds': total_seconds, 'per_file_seconds': per_file}

    @classmethod
    def estimate_import_time(cls, estimates: Dict[str, Dict[str, Optional[int]]], import_speed_bytes_per_s: int = 5 * 1024 * 1024) -> float:
        """Estimativa grosseira do tempo de importação baseado no tamanho total e velocidade média de import (5 MB/s por padrão)."""
        total = sum((info.get('size') or 0) for info in estimates.values())
        return total / import_speed_bytes_per_s if import_speed_bytes_per_s > 0 else float('inf')

    @classmethod
    def plan_for_official(cls) -> Dict[str, object]:
        """Cria um plano de download/importação sem executar nada. Retorna metadados planejados."""
        candidates = cls.discover_official_candidates()
        estimates = cls.estimate_sizes(candidates)
        totals = cls.estimate_total(estimates)
        import_time_s = cls.estimate_import_time(estimates)

        plan = {
            'candidates': candidates,
            'estimates': estimates,
            'download_estimate': totals,
            'import_estimate_seconds': import_time_s,
            'duckdb_path': str(DatabaseService.DATABASE_PATH),
        }
        return plan

    @classmethod
    def create_download_metadata(cls, estimates: Dict[str, Dict[str, Optional[int]]]) -> Dict:
        """Gera um entry inicial para metadata.json descrevendo os arquivos a baixar (status pending)."""
        meta = {'files': {}, 'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        for k, info in estimates.items():
            meta['files'][info['name']] = {
                'dataset': k,
                'url': info['url'],
                'size': info.get('size'),
                'status': 'pending',
            }
        return meta

    @classmethod
    def execute_downloads(cls, selected: List[str], progress_callback: Optional[callable] = None) -> Dict[str, Path]:
        """Realiza os downloads dos arquivos selecionados. EXECUTE apenas quando autorizado pelo usuário."""
        candidates = cls.discover_official_candidates()
        to_download = {candidates[k]['name']: candidates[k]['url'] for k in selected if k in candidates}
        return DownloadService.download_files(to_download, progress_callback)

    @classmethod
    def execute_imports(cls, paths: List[Path], batch_size: int = None) -> Dict[str, dict]:
        """Importa os arquivos localmente baixados para o DuckDB (usa ImportService.import_file_streaming).

        EXECUTE apenas quando autorizado pelo usuário.
        Retorna um dicionário com relatórios por arquivo.
        """
        reports = {}
        for p in paths:
            try:
                r = ImportService.import_file_streaming(p, batch_size=batch_size)
                reports[p.name] = r
            except Exception as exc:
                logger.exception('Falha ao importar %s', p)
                reports[p.name] = {'error': str(exc)}
        # Optionally update indexes or run ANALYZE
        try:
            with DatabaseService.get_connection() as conn:
                # DuckDB manages stats automatically; user can run ANALYZE if desired
                conn.execute('ANALYZE')
        except Exception:
            logger.exception('Falha ao atualizar estatísticas do DuckDB')
        return reports

    @classmethod
    def ingest_state(
        cls,
        uf: str,
        empresas_path: Optional[Path] = None,
        estabelecimentos_path: Optional[Path] = None,
        replace: bool = True,
    ) -> Dict:
        """Ingere a base oficial de UM estado, populando a tabela `empresas`.

        Se `empresas_path`/`estabelecimentos_path` forem fornecidos (arquivos já
        baixados/extraídos da Receita), usa-os diretamente — útil quando o
        download ao vivo não está disponível. Caso contrário, tenta baixar via
        DownloadService a partir das URLs oficiais descobertas.

        A ingestão em si é delegada ao ImportService (layout real da RF).
        """
        if empresas_path is None or estabelecimentos_path is None:
            candidates = cls.discover_official_candidates()
            if not candidates:
                raise RuntimeError(
                    "Não foi possível descobrir a base oficial (índice inacessível "
                    "e CNPJ_VERSION não definido). Baixe os arquivos e informe os "
                    "caminhos em empresas_path/estabelecimentos_path."
                )
            downloaded = cls.execute_downloads(["empresas", "estabelecimentos"])
            for name, path in downloaded.items():
                extracted = ImportService.extract_zip(path)
                for ex in extracted:
                    kind = ImportService.detect_file_type(ex)
                    if kind == "empresas" and empresas_path is None:
                        empresas_path = ex
                    elif kind == "estabelecimentos" and estabelecimentos_path is None:
                        estabelecimentos_path = ex

        if empresas_path is None or estabelecimentos_path is None:
            raise RuntimeError(
                "Arquivos de Empresas e/ou Estabelecimentos não encontrados para ingestão."
            )

        report = ImportService.import_receita_dataset(
            empresas_path=Path(empresas_path),
            estabelecimentos_path=Path(estabelecimentos_path),
            uf=uf,
            replace=replace,
        )
        return report

    @classmethod
    def prepare_and_save_plan(cls) -> Dict:
        """Helper que gera o plano e salva como metadata de planejamento em data/raw/download_plan.json."""
        plan = cls.plan_for_official()
        path = cls.RAW_DIR / 'download_plan.json'
        cls.RAW_DIR.mkdir(parents=True, exist_ok=True)
        import json
        path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding='utf-8')
        return plan
