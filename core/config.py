# core/config.py
from pathlib import Path
import os
from typing import Iterable


def _first_existing(paths: Iterable[Path], default: Path) -> Path:
    for candidate in paths:
        if candidate.exists():
            return candidate
    return default


BASE_DIR = Path(__file__).resolve().parents[1]

db_env = os.getenv("DB_PATH", "").strip()
DB_PATH = Path(db_env).expanduser() if db_env else BASE_DIR / "db" / "tolls.db"

routes_env = os.getenv("ROUTES_CSV", "").strip()
if routes_env:
    ROUTES_CSV = Path(routes_env).expanduser()
else:
    ROUTES_CSV = BASE_DIR / "data" / "plantilla_rutas_peaje.csv"

tariffs_env = os.getenv("TARIFFS_XLSX", "").strip()
if tariffs_env:
    TARIFFS_XLSX = Path(tariffs_env).expanduser()
else:
    TARIFFS_XLSX = _first_existing(
        [
            BASE_DIR / "data" / "PEAJE_PASE_2025.xlsx",
            BASE_DIR / "PEAJE_PASE_2025.xlsx",
        ],
        BASE_DIR / "data" / "PEAJE_PASE_2025.xlsx",
    )

# Google Maps key (required for autocompletado y rutas)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
