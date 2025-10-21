from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "db" / "tolls.db"
ROUTES_CSV = BASE_DIR / "data" / "plantilla_rutas_peaje.csv"

# Si después migras a Postgres, cambia a DATABASE_URL y úsalo con SQLAlchemy.
