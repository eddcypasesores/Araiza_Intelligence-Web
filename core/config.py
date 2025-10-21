# core/config.py
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[1]

DB_ENV = os.getenv("DB_PATH", "").strip()
DB_PATH = Path(DB_ENV) if DB_ENV else (BASE_DIR / "db" / "tolls.db")

# CSV de rutas: ENV primero; si no, prueba rutas comunes
ROUTES_CSV_ENV = os.getenv("ROUTES_CSV", "").strip()

if ROUTES_CSV_ENV:
    ROUTES_CSV = Path(ROUTES_CSV_ENV)
else:
    candidates = [
        BASE_DIR / "data" / "plantilla_rutas_peaje.csv",
        BASE_DIR / "plantilla_rutas_peaje.csv",           # por si lo dejaste en la raíz
    ]
    ROUTES_CSV = next((p for p in candidates if p.exists()), candidates[0])

if DB_ENV:
    DB_PATH = Path(DB_ENV)
else:
    DB_PATH = BASE_DIR / "db" / "tolls.db"    # por defecto en local

# CSV de rutas (solo lectura, dentro del repo)
ROUTES_CSV = BASE_DIR / "data" / "plantilla_rutas_peaje.csv"
