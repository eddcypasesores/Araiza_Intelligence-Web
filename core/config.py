# core/config.py
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[1]

# Permite sobreescribir por env var (ideal para Render)
DB_ENV = os.getenv("DB_PATH", "").strip()

if DB_ENV:
    DB_PATH = Path(DB_ENV)
else:
    DB_PATH = BASE_DIR / "db" / "tolls.db"    # por defecto en local

# CSV de rutas (solo lectura, dentro del repo)
ROUTES_CSV = BASE_DIR / "data" / "plantilla_rutas_peaje.csv"
