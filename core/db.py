# core/db.py
import csv
import hashlib
import json
import re
import secrets
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd  # puede usarse en otros helpers

from .config import (
    DB_PATH,
    PORTAL_DATABASE_URL,
    ROUTES_CSV,
    TARIFFS_XLSX,
)

try:
    import psycopg
except ImportError:  # pragma: no cover - solo ocurre si no se instala psycopg
    psycopg = None


CLASES: list[str] = [
    "MOTO",
    "AUTOMOVIL",
    "B2",
    "B3",
    "B4",
    "T2",
    "T3",
    "T4",
    "T5",
    "T6",
    "T7",
    "T8",
    "T9",
]

HEADER_ALIASES = {
    "via_principal": "via",
    "via": "via",
    "ruta": "via",
    "tramo": "via",
    "plaza": "plaza",
    "caseta": "plaza",
    "caseta_de_cobro": "plaza",
    "n": "orden",
    "no": "orden",
    "numero": "orden",
    "orden": "orden",
    "lat": "lat",
    "latitud": "lat",
    "lon": "lon",
    "long": "lon",
    "longitud": "lon",
    "tarifa_mxn": "tarifa_mxn",
    "tarifa": "tarifa",
    "precio": "precio",
    "costo": "costo",
    "clase": "clase",
}


USE_PORTAL_POSTGRES = bool(PORTAL_DATABASE_URL)
if USE_PORTAL_POSTGRES and psycopg is None:  # pragma: no cover - protección de entorno
    raise RuntimeError(
        "psycopg es requerido cuando PORTAL_DATABASE_URL o DATABASE_URL están definidos."
    )


def _clean_header(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = text.replace("º", "n").replace("°", "n")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _normalize_headers(headers: Iterable[str]) -> list[str]:
    normalized = []
    for header in headers:
        cleaned = _clean_header(header)
        normalized.append(HEADER_ALIASES.get(cleaned, cleaned))
    return normalized


def _strip_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _parse_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value):
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _records_from_excel(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    except ImportError as exc:
        print(f"[ETL] Falta dependencia para leer Excel: {exc}")
        return []
    except Exception as exc:
        print(f"[ETL] Error leyendo Excel {path}: {exc}")
        return []

    if df.empty:
        return []

    df = df.fillna("")
    headers = _normalize_headers(df.columns)
    records: list[dict] = []
    for raw in df.to_dict(orient="records"):
        normalized = {}
        for alias, original_key in zip(headers, df.columns):
            normalized[alias] = raw.get(original_key)
        records.append(normalized)
    return records


def _records_from_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            records = []
            for row in reader:
                normalized = {}
                for key, value in row.items():
                    alias = HEADER_ALIASES.get(_clean_header(key), _clean_header(key))
                    normalized[alias] = value
                records.append(normalized)
            return records
    except Exception as exc:
        print(f"[ETL] Error leyendo CSV {path}: {exc}")
        return []


def _ingest_records(conn, records: Iterable[dict], source: str) -> bool:
    cur = conn.cursor()
    vias_cache: dict[str, int] = {}
    orden_cache: dict[int, int] = {}
    inserted_any = False

    for row in records:
        via_nom = _strip_str(row.get("via"))
        plaza_nom = _strip_str(row.get("plaza"))
        if not via_nom or not plaza_nom:
            continue

        inserted_any = True

        via_id = vias_cache.get(via_nom)
        if via_id is None:
            cur.execute("INSERT OR IGNORE INTO vias(nombre) VALUES(?)", (via_nom,))
            via_id = cur.execute("SELECT id FROM vias WHERE nombre=?", (via_nom,)).fetchone()[0]
            vias_cache[via_nom] = via_id

        orden = _parse_int(row.get("orden"))
        if orden is None:
            orden = orden_cache.get(via_id, 0) + 1
        orden_cache[via_id] = max(orden_cache.get(via_id, 0), orden)

        lat = _parse_float(row.get("lat"))
        lon = _parse_float(row.get("lon"))

        cur.execute(
            """
            INSERT OR IGNORE INTO plazas(via_id, nombre, orden, lat, lon)
            VALUES(?,?,?,?,?)
            """,
            (via_id, plaza_nom, orden, lat, lon),
        )
        plaza_id = cur.execute(
            "SELECT id FROM plazas WHERE via_id=? AND nombre=?",
            (via_id, plaza_nom),
        ).fetchone()[0]

        clase_unica = _strip_str(row.get("clase")).upper()
        tarifa_unica = row.get("tarifa_mxn")
        if clase_unica and tarifa_unica not in (None, ""):
            tarifa_float = _parse_float(tarifa_unica)
            if tarifa_float is not None:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO plaza_tarifas(plaza_id, clase, tarifa_mxn)
                    VALUES(?,?,?)
                    """,
                    (plaza_id, clase_unica, tarifa_float),
                )

        inserted_clase = False
        for clase in CLASES:
            valor = row.get(clase.lower())
            if valor in (None, ""):
                continue
            tarifa_float = _parse_float(valor)
            if tarifa_float is None:
                continue
            cur.execute(
                """
                INSERT OR REPLACE INTO plaza_tarifas(plaza_id, clase, tarifa_mxn)
                VALUES(?,?,?)
                """,
                (plaza_id, clase, tarifa_float),
            )
            inserted_clase = True

        if not inserted_clase and not (clase_unica and tarifa_unica not in (None, "")):
            precio_simple = _parse_float(row.get("precio") or row.get("tarifa") or row.get("costo"))
            if precio_simple is not None:
                for clase in CLASES:
                    cur.execute(
                        """
                        INSERT OR REPLACE INTO plaza_tarifas(plaza_id, clase, tarifa_mxn)
                        VALUES(?,?,?)
                        """,
                        (plaza_id, clase, precio_simple),
                    )
            else:
                for clase in ("AUTOMOVIL", "T5"):
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO plaza_tarifas(plaza_id, clase, tarifa_mxn)
                        VALUES(?,?,?)
                        """,
                        (plaza_id, clase, 0.0),
                    )

    if inserted_any:
        conn.commit()
        print(f"[ETL] Rutas/plazas/tarifas cargadas desde {source}.")
    return inserted_any


def _remove_generic_seed(conn):
    cur = conn.cursor()
    via_generica = cur.execute(
        "SELECT id FROM vias WHERE nombre=?",
        ("VIA GENÉRICA",),
    ).fetchone()
    if not via_generica:
        return
    gen_id = via_generica[0]
    cur.execute(
        "DELETE FROM plaza_tarifas WHERE plaza_id IN (SELECT id FROM plazas WHERE via_id=?)",
        (gen_id,),
    )
    cur.execute("DELETE FROM plazas WHERE via_id=?", (gen_id,))
    cur.execute("DELETE FROM vias WHERE id=?", (gen_id,))
    conn.commit()


# -------------------------
# ETL inicial de rutas
# -------------------------
def _seed_routes_if_empty(conn):
    cur = conn.cursor()
    pcount = cur.execute("SELECT COUNT(*) FROM plazas").fetchone()[0]
    tcount = cur.execute("SELECT COUNT(*) FROM plaza_tarifas").fetchone()[0]
    real_vias = cur.execute(
        "SELECT COUNT(*) FROM vias WHERE nombre <> ?",
        ("VIA GENÉRICA",),
    ).fetchone()[0]
    if pcount > 0 and tcount > 0 and real_vias > 0:
        return

    seeded = False
    if TARIFFS_XLSX and TARIFFS_XLSX.exists():
        seeded = _ingest_records(conn, _records_from_excel(TARIFFS_XLSX), "Excel")

    if not seeded and ROUTES_CSV and ROUTES_CSV.exists():
        seeded = _ingest_records(conn, _records_from_csv(ROUTES_CSV), "CSV")

    if seeded:
        _remove_generic_seed(conn)
        return

    # Fallback mínimo (si no hay CSV)
    try:
        cur.execute("INSERT OR IGNORE INTO vias(nombre) VALUES(?)", ("VIA GENÉRICA",))
        via_row = cur.execute(
            "SELECT id FROM vias WHERE nombre=?",
            ("VIA GENÉRICA",),
        ).fetchone()
        if not via_row:
            raise RuntimeError("No se pudo recuperar VIA GENÉRICA")

        via_id = via_row[0]
        cur.execute(
            """
            INSERT OR IGNORE INTO plazas(via_id, nombre, orden, lat, lon)
            VALUES(?,?,?,?,?)
            """,
            (via_id, "PLAZA DEMO", 1, None, None),
        )

        plazas = cur.execute("SELECT id FROM plazas").fetchall()
        if not plazas:
            raise RuntimeError("No se encontraron plazas para aplicar fallback")

        for (plaza_id,) in plazas:
            for c in CLASES:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO plaza_tarifas(plaza_id, clase, tarifa_mxn)
                    VALUES(?,?,?)
                    """,
                    (plaza_id, c, 100.0 if c in ("AUTOMOVIL", "T5") else 0.0),
                )
        conn.commit()
        print("[ETL] Seed de rutas mínimo creado (sin CSV).")
    except Exception as e:
        print(f"[ETL] Fallback de rutas falló: {e}")
# =========================
# Conexión
# =========================
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 8000;")
        conn.execute("PRAGMA foreign_keys = ON;")
    except Exception:
        pass
    return conn


def _column_exists(conn, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())


def _ensure_column(conn, table: str, col: str, decl_sql: str):
    if not _column_exists(conn, table, col):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {decl_sql}")

# =========================
# Esquema / Migración
# =========================
def ensure_schema(conn):
    # ---- dominio peajes/usuarios/trabajadores ----
    conn.execute("""
      CREATE TABLE IF NOT EXISTS vias(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS plazas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        via_id INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        orden INTEGER NOT NULL,
        lat REAL, lon REAL,
        UNIQUE(via_id, nombre),
        UNIQUE(via_id, orden)
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS plaza_tarifas(
        plaza_id INTEGER NOT NULL,
        clase TEXT NOT NULL,
        tarifa_mxn REAL NOT NULL DEFAULT 0,
        PRIMARY KEY (plaza_id, clase)
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS usuarios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        rol TEXT NOT NULL CHECK(rol IN ('admin','operador'))
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS trabajadores(
        id INTEGER PRIMARY KEY AUTOINCREMENT
      );
    """)
    _ensure_column(conn, "trabajadores", "nombres",            "nombres TEXT")
    _ensure_column(conn, "trabajadores", "apellido_paterno",   "apellido_paterno TEXT")
    _ensure_column(conn, "trabajadores", "apellido_materno",   "apellido_materno TEXT")
    _ensure_column(conn, "trabajadores", "edad",               "edad INTEGER DEFAULT 0")
    _ensure_column(conn, "trabajadores", "rol_trabajador",     "rol_trabajador TEXT")
    _ensure_column(conn, "trabajadores", "numero_economico",   "numero_economico TEXT")
    _ensure_column(conn, "trabajadores", "fecha_registro",     "fecha_registro TEXT")
    _ensure_column(conn, "trabajadores", "salario_diario",     "salario_diario REAL DEFAULT 0")
    # Campos requeridos por 3_Trabajadores.py
    _ensure_column(conn, "trabajadores", "nombre",                "nombre TEXT")
    _ensure_column(conn, "trabajadores", "salario_mensual",       "salario_mensual REAL DEFAULT 0")
    _ensure_column(conn, "trabajadores", "imss_pct",              "imss_pct REAL DEFAULT 0")
    _ensure_column(conn, "trabajadores", "carga_social_pct",      "carga_social_pct REAL DEFAULT 0")
    _ensure_column(conn, "trabajadores", "aguinaldo_dias",        "aguinaldo_dias REAL DEFAULT 0")
    _ensure_column(conn, "trabajadores", "prima_vacacional_pct",  "prima_vacacional_pct REAL DEFAULT 0")
    _ensure_column(conn, "trabajadores", "horas_por_dia",         "horas_por_dia REAL DEFAULT 8")
    _ensure_column(conn, "trabajadores", "dias_laborales_mes",    "dias_laborales_mes REAL DEFAULT 30")

    conn.execute("""
      CREATE TABLE IF NOT EXISTS usuario_trabajador(
        usuario_id INTEGER NOT NULL UNIQUE,
        trabajador_id INTEGER NOT NULL UNIQUE,
        PRIMARY KEY (usuario_id, trabajador_id),
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        FOREIGN KEY(trabajador_id) REFERENCES trabajadores(id) ON DELETE CASCADE
      );
    """)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_plaza_clase ON plaza_tarifas(plaza_id, clase)")
    conn.execute("""
      CREATE UNIQUE INDEX IF NOT EXISTS ux_trab_numeco
      ON trabajadores(numero_economico)
      WHERE numero_economico IS NOT NULL AND numero_economico <> '';
    """)

    # ---- parámetros versionados ----
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_costeo_version(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        vigente_desde TEXT,
        vigente_hasta TEXT,
        notas TEXT
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_diesel(
        version_id INTEGER PRIMARY KEY,
        rendimiento_km_l REAL NOT NULL,
        precio_litro REAL NOT NULL,
        FOREIGN KEY(version_id) REFERENCES param_costeo_version(id) ON DELETE CASCADE
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_def(
        version_id INTEGER PRIMARY KEY,
        pct_def REAL NOT NULL,
        precio_def_litro REAL NOT NULL,
        FOREIGN KEY(version_id) REFERENCES param_costeo_version(id) ON DELETE CASCADE
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_tag(
        version_id INTEGER PRIMARY KEY,
        pct_comision_tag REAL NOT NULL,
        FOREIGN KEY(version_id) REFERENCES param_costeo_version(id) ON DELETE CASCADE
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_costos_km(
        version_id INTEGER PRIMARY KEY,
        costo_llantas_km REAL NOT NULL,
        costo_mantto_km REAL NOT NULL,
        FOREIGN KEY(version_id) REFERENCES param_costeo_version(id) ON DELETE CASCADE
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_depreciacion(
        version_id INTEGER PRIMARY KEY,
        costo_adq REAL NOT NULL,
        valor_residual REAL NOT NULL,
        vida_anios INTEGER NOT NULL,
        km_anuales INTEGER NOT NULL,
        FOREIGN KEY(version_id) REFERENCES param_costeo_version(id) ON DELETE CASCADE
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_seguros(
        version_id INTEGER PRIMARY KEY,
        prima_anual REAL NOT NULL,
        km_anuales INTEGER NOT NULL,
        FOREIGN KEY(version_id) REFERENCES param_costeo_version(id) ON DELETE CASCADE
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_financiamiento(
        version_id INTEGER PRIMARY KEY,
        tasa_anual REAL NOT NULL,
        dias_cobro INTEGER NOT NULL,
        FOREIGN KEY(version_id) REFERENCES param_costeo_version(id) ON DELETE CASCADE
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_overhead(
        version_id INTEGER PRIMARY KEY,
        pct_overhead REAL NOT NULL,
        FOREIGN KEY(version_id) REFERENCES param_costeo_version(id) ON DELETE CASCADE
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_utilidad(
        version_id INTEGER PRIMARY KEY,
        pct_utilidad REAL NOT NULL,
        FOREIGN KEY(version_id) REFERENCES param_costeo_version(id) ON DELETE CASCADE
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_otros(
        version_id INTEGER PRIMARY KEY,
        viatico_dia REAL NOT NULL,
        permiso_viaje REAL NOT NULL,
        custodia_km REAL NOT NULL,
        FOREIGN KEY(version_id) REFERENCES param_costeo_version(id) ON DELETE CASCADE
      );
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS param_politicas(
        version_id INTEGER PRIMARY KEY,
        incluye_en_base TEXT NOT NULL,
        FOREIGN KEY(version_id) REFERENCES param_costeo_version(id) ON DELETE CASCADE
      );
    """)

    conn.commit()

    ensure_portal_schema(conn)

    # Seed mínimo: usuario admin
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM usuarios")
    if (cur.fetchone() or [0])[0] == 0:
        cur.execute(
            "INSERT INTO usuarios(username,password,rol) VALUES(?,?,?)",
            ("admin", "1234", "admin"),
        )
        conn.commit()

    ensure_portal_admin(conn)

    # Seed parámetros v1 (idempotente)
    cur.execute("SELECT COUNT(*) FROM param_costeo_version")
    if (cur.fetchone() or [0])[0] == 0:
        _seed_parametros_v1(conn)

    # >>> IMPORTANTE: cargar rutas/plazas/tarifas si está vacío
    _seed_routes_if_empty(conn)


# ---------- Helpers de autenticación / relación ----------
def validar_usuario(conn, username: str, password: str):
    """Compatibilidad retro: devuelve rol admin/operador usando portal_users."""
    record = authenticate_portal_user(conn, username, password)
    if not record:
        return None
    permisos = set(record.get("permisos") or [])
    return "admin" if "admin" in permisos else "operador"

def get_usuario(conn, username: str):
    cur = conn.cursor()
    cur.execute("SELECT id, username, rol FROM usuarios WHERE username=?", (username,))
    return cur.fetchone()

def set_usuario_trabajador(conn, username: str, trabajador_id: int):
    u = get_usuario(conn, username)
    if not u:
        raise ValueError("Usuario no existe")
    uid = u[0]
    conn.execute("""
      INSERT INTO usuario_trabajador(usuario_id, trabajador_id)
      VALUES(?, ?)
      ON CONFLICT(usuario_id) DO UPDATE SET trabajador_id=excluded.trabajador_id
    """, (uid, trabajador_id))
    conn.commit()

def clear_usuario_trabajador(conn, username: str):
    u = get_usuario(conn, username)
    if not u:
        return
    conn.execute("DELETE FROM usuario_trabajador WHERE usuario_id=?", (u[0],))
    conn.commit()


# ---------- Portal storage helpers ----------
@contextmanager
def _portal_cursor(conn, *, write: bool = False):
    """Yield (db_conn, cursor) apuntando a la base de datos del portal."""

    if USE_PORTAL_POSTGRES:
        db = psycopg.connect(PORTAL_DATABASE_URL, autocommit=False)
        cur = db.cursor()
        try:
            yield db, cur
            if write:
                db.commit()
        except Exception:
            if write:
                db.rollback()
            raise
        finally:
            cur.close()
            db.close()
    else:
        cur = conn.cursor()
        try:
            yield conn, cur
            if write:
                conn.commit()
        except Exception:
            if write:
                conn.rollback()
            raise
        finally:
            cur.close()


def _portal_sql(sql: str) -> str:
    return sql.replace("?", "%s") if USE_PORTAL_POSTGRES else sql


def _portal_dataframe(cur) -> pd.DataFrame:
    rows = cur.fetchall()
    columns = [col[0] for col in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=columns)


def ensure_portal_schema(conn):
    """Crea las tablas del portal según el backend configurado."""

    if USE_PORTAL_POSTGRES:
        with _portal_cursor(conn, write=True) as (_, cur):
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS portal_users(
                    id BIGSERIAL PRIMARY KEY,
                    rfc TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    regimen_fiscal TEXT,
                    calle TEXT,
                    colonia TEXT,
                    cp TEXT,
                    municipio TEXT,
                    email TEXT,
                    telefono TEXT,
                    permisos TEXT NOT NULL DEFAULT '[]',
                    must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS portal_user_resets(
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
                    token TEXT NOT NULL UNIQUE,
                    expires_at timestamptz NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portal_users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfc TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                regimen_fiscal TEXT,
                calle TEXT,
                colonia TEXT,
                cp TEXT,
                municipio TEXT,
                email TEXT,
                telefono TEXT,
                permisos TEXT NOT NULL DEFAULT '[]',
                must_change_password INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portal_user_resets(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES portal_users(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


# ---------- Portal Users (nueva autenticacion global) ----------
PORTAL_ALLOWED_MODULES: tuple[str, ...] = ("traslados", "riesgos", "diot", "cedula", "admin")
DEFAULT_RESET_TOKEN_TTL_MINUTES = 60

SUPERADMIN_SEED: dict[str, str | bool | list[str]] = {
    "rfc": "ZELE990823E20",
    "password_raw": "ZELE990823E20",
    "regimen_fiscal": "PERSONA FISICA CON ACTIVIDADES EMPRESARIALES",
    "calle": "DAVID HERNANDEZ 09",
    "colonia": "EJERCITO DEL TRABAJO",
    "cp": "56390",
    "municipio": "CHICOLOAPAN",
    "email": "werzl330@gmail.com",
    "telefono": "5549386304",
    "permisos": ["admin", "traslados", "riesgos", "diot", "cedula"],
    "must_change_password": True,
}


def _normalize_rfc(value: str) -> str:
    return (value or "").strip().upper()


def _hash_password(raw_password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 120_000
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        raw_password.encode("utf-8"),
        salt,
        iterations,
    )
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def _verify_password(raw_password: str, stored_hash: str) -> tuple[bool, bool]:
    """Return (is_valid, needs_rehash)."""

    if stored_hash and stored_hash.startswith("pbkdf2_sha256$"):
        try:
            algorithm, iterations_str, salt_hex, digest_hex = stored_hash.split("$")
            iterations = int(iterations_str)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
        except Exception:
            return False, False
        if algorithm != "pbkdf2_sha256":
            return False, False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            raw_password.encode("utf-8"),
            salt,
            iterations,
        )
        return secrets.compare_digest(candidate, expected), False

    # Legacy fallbacks (plain text or SHA-256 hex without salt)
    normalized = raw_password.strip()
    legacy_candidates = {
        normalized,
        normalized.upper(),
        hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    }
    if stored_hash in legacy_candidates:
        return True, True

    return False, False


def _permisos_to_text(permisos: Sequence[str] | None) -> str:
    if not permisos:
        return "[]"
    clean = sorted({p.strip().lower() for p in permisos if p})
    return json.dumps(clean)


def _permisos_from_text(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(p).strip().lower() for p in data if isinstance(p, str)]


def ensure_portal_admin(conn: sqlite3.Connection) -> None:
    """Crea el super administrador configurado si no existe."""

    seed_rfc = _normalize_rfc(str(SUPERADMIN_SEED.get("rfc") or ""))
    if not seed_rfc:
        return

    with _portal_cursor(conn, write=True) as (_, cur):
        cur.execute(
            _portal_sql("SELECT 1 FROM portal_users WHERE rfc=?"),
            (seed_rfc,),
        )
        if cur.fetchone():
            return

        permisos = SUPERADMIN_SEED.get("permisos") or ["admin", "traslados", "riesgos", "diot", "cedula"]
        permisos_text = _permisos_to_text(permisos)
        must_change_password = bool(SUPERADMIN_SEED.get("must_change_password", True))
        password_hash = _hash_password(str(SUPERADMIN_SEED.get("password_raw") or seed_rfc))

        cur.execute(
            _portal_sql(
                """
                INSERT INTO portal_users(
                    rfc, password_hash, regimen_fiscal, calle, colonia, cp, municipio,
                    email, telefono, permisos, must_change_password
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """
            ),
            (
                seed_rfc,
                password_hash,
                SUPERADMIN_SEED.get("regimen_fiscal"),
                SUPERADMIN_SEED.get("calle"),
                SUPERADMIN_SEED.get("colonia"),
                SUPERADMIN_SEED.get("cp"),
                SUPERADMIN_SEED.get("municipio"),
                SUPERADMIN_SEED.get("email"),
                SUPERADMIN_SEED.get("telefono"),
                permisos_text,
                must_change_password,
            ),
        )


def portal_create_user(
    conn: sqlite3.Connection,
    *,
    rfc: str,
    regimen_fiscal: str | None = None,
    calle: str | None = None,
    colonia: str | None = None,
    cp: str | None = None,
    municipio: str | None = None,
    email: str | None = None,
    telefono: str | None = None,
    permisos: Sequence[str] | None = None,
    password: str | None = None,
    must_change_password: bool = True,
) -> None:
    norm_rfc = _normalize_rfc(rfc)
    if not norm_rfc:
        raise ValueError("RFC obligatorio")
    permisos_list = list(permisos or [])
    if not permisos_list:
        permisos_list = ["traslados"]
    permisos_text = _permisos_to_text(permisos_list)
    password_hash = _hash_password(password or norm_rfc)
    with _portal_cursor(conn, write=True) as (_, cur):
        cur.execute(
            _portal_sql(
                """
                INSERT INTO portal_users(
                    rfc, password_hash, regimen_fiscal, calle, colonia, cp, municipio,
                    email, telefono, permisos, must_change_password
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """
            ),
            (
                norm_rfc,
                password_hash,
                regimen_fiscal,
                calle,
                colonia,
                cp,
                municipio,
                email,
                telefono,
                permisos_text,
                bool(must_change_password),
            ),
        )


def portal_update_user(
    conn: sqlite3.Connection,
    rfc: str,
    *,
    regimen_fiscal: str | None = None,
    calle: str | None = None,
    colonia: str | None = None,
    cp: str | None = None,
    municipio: str | None = None,
    email: str | None = None,
    telefono: str | None = None,
    permisos: Sequence[str] | None = None,
    must_change_password: bool | None = None,
) -> None:
    norm_rfc = _normalize_rfc(rfc)
    with _portal_cursor(conn, write=True) as (_, cur):
        cur.execute(_portal_sql('SELECT id FROM portal_users WHERE rfc=?'), (norm_rfc,))
        if not cur.fetchone():
            raise ValueError('Usuario no encontrado')

        updates: list[str] = []
        params: list = []

        def _set(field: str, value):
            updates.append(f"{field}=?")
            params.append(value)

        if regimen_fiscal is not None:
            _set('regimen_fiscal', regimen_fiscal)
        if calle is not None:
            _set('calle', calle)
        if colonia is not None:
            _set('colonia', colonia)
        if cp is not None:
            _set('cp', cp)
        if municipio is not None:
            _set('municipio', municipio)
        if email is not None:
            _set('email', email)
        if telefono is not None:
            _set('telefono', telefono)
        if permisos is not None:
            permisos_list = list(permisos)
            if not permisos_list:
                permisos_list = ['traslados']
            _set('permisos', _permisos_to_text(permisos_list))
        if must_change_password is not None:
            _set('must_change_password', bool(must_change_password))

        if updates:
            params.extend([datetime.now(timezone.utc).isoformat(), norm_rfc])
            cur.execute(
                _portal_sql(
                    f"""
                    UPDATE portal_users
                    SET {', '.join(updates)}, updated_at=?
                    WHERE rfc=?
                    """
                ),
                params,
            )


def portal_delete_users(conn: sqlite3.Connection, rfcs: Sequence[str]) -> None:
    if not rfcs:
        return
    cleaned = [_normalize_rfc(r) for r in rfcs if r]
    if not cleaned:
        return
    with _portal_cursor(conn, write=True) as (_, cur):
        cur.executemany(
            _portal_sql("DELETE FROM portal_users WHERE rfc=?"),
            [(r,) for r in cleaned],
        )


def portal_list_users(conn: sqlite3.Connection) -> pd.DataFrame:
    query = """
    SELECT
        rfc,
        regimen_fiscal,
        calle,
        colonia,
        cp,
        municipio,
        email,
        telefono,
        permisos,
        must_change_password,
        created_at,
        updated_at
    FROM portal_users
    ORDER BY rfc
    """
    with _portal_cursor(conn) as (_, cur):
        cur.execute(_portal_sql(query))
        return _portal_dataframe(cur)


def portal_get_user(conn: sqlite3.Connection, rfc: str):
    norm_rfc = _normalize_rfc(rfc)
    with _portal_cursor(conn) as (_, cur):
        cur.execute(
            _portal_sql(
                """
                SELECT id, rfc, password_hash, permisos, must_change_password,
                       regimen_fiscal, calle, colonia, cp, municipio, email, telefono
                FROM portal_users
                WHERE rfc=?
                """
            ),
            (norm_rfc,),
        )
        row = cur.fetchone()
    if not row:
        return None
    permisos = _permisos_from_text(row[3])
    return {
        "id": row[0],
        "rfc": row[1],
        "password_hash": row[2],
        "permisos": permisos,
        "must_change_password": bool(row[4]),
        "regimen_fiscal": row[5],
        "calle": row[6],
        "colonia": row[7],
        "cp": row[8],
        "municipio": row[9],
        "email": row[10],
        "telefono": row[11],
    }


def portal_set_password(
    conn: sqlite3.Connection,
    rfc: str,
    new_password: str,
    require_change: bool = False,
) -> None:
    norm_rfc = _normalize_rfc(rfc)
    password_hash = _hash_password(new_password)
    with _portal_cursor(conn, write=True) as (_, cur):
        cur.execute(
            _portal_sql(
                """
                UPDATE portal_users
                SET password_hash=?, must_change_password=?, updated_at=?
                WHERE rfc=?
                """
            ),
            (
                password_hash,
                bool(require_change),
                datetime.now(timezone.utc).isoformat(),
                norm_rfc,
            ),
        )
        cur.execute(
            _portal_sql(
                """
                DELETE FROM portal_user_resets
                WHERE user_id = (
                    SELECT id FROM portal_users WHERE rfc=?
                )
                """
            ),
            (norm_rfc,),
        )


def portal_reset_password_to_default(conn: sqlite3.Connection, rfc: str) -> bool:
    user = portal_get_user(conn, rfc)
    if not user:
        return False
    portal_set_password(conn, rfc, _normalize_rfc(rfc), require_change=True)
    return True


def _ensure_positive_ttl(minutes: int | None) -> int:
    try:
        value = int(minutes or 0)
    except (TypeError, ValueError):
        value = 0
    return max(value, 1)


def _generate_reset_token(conn: sqlite3.Connection) -> str:
    with _portal_cursor(conn) as (_, cur):
        while True:
            token = secrets.token_urlsafe(24)
            cur.execute(
                _portal_sql("SELECT 1 FROM portal_user_resets WHERE token=?"),
                (token,),
            )
            if not cur.fetchone():
                return token


def portal_create_reset_token(
    conn: sqlite3.Connection,
    rfc: str,
    *,
    ttl_minutes: int | None = None,
) -> str:
    user = portal_get_user(conn, rfc)
    if not user:
        raise ValueError("Usuario no encontrado")
    token = _generate_reset_token(conn)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=_ensure_positive_ttl(ttl_minutes or DEFAULT_RESET_TOKEN_TTL_MINUTES)
    )
    with _portal_cursor(conn, write=True) as (_, cur):
        cur.execute(
            _portal_sql(
                """
                INSERT INTO portal_user_resets(user_id, token, expires_at)
                VALUES(?,?,?)
                """
            ),
            (user["id"], token, expires_at.isoformat()),
        )
    return token


def _row_to_reset_record(row) -> dict | None:
    if not row:
        return None
    expires_raw = row[3]
    if isinstance(expires_raw, datetime):
        expires = expires_raw
    else:
        try:
            expires = datetime.fromisoformat(expires_raw)
        except Exception:
            expires = None
    return {
        "id": row[0],
        "user_id": row[1],
        "token": row[2],
        "expires_at": expires,
        "rfc": row[4] if len(row) > 4 else None,
    }


def portal_get_reset_token(conn: sqlite3.Connection, token: str) -> dict | None:
    with _portal_cursor(conn, write=True) as (_, cur):
        cur.execute(
            _portal_sql(
                """
                SELECT r.id, r.user_id, r.token, r.expires_at, u.rfc
                FROM portal_user_resets r
                JOIN portal_users u ON u.id = r.user_id
                WHERE r.token=?
                """
            ),
            (token,),
        )
        row = cur.fetchone()
        record = _row_to_reset_record(row)
        if not record:
            return None
        expires = record["expires_at"]
        if expires and expires < datetime.now(timezone.utc):
            cur.execute(
                _portal_sql("DELETE FROM portal_user_resets WHERE id=?"),
                (record["id"],),
            )
            return None
    return record


def portal_consume_reset_token(
    conn: sqlite3.Connection,
    token: str,
    new_password: str,
) -> bool:
    record = portal_get_reset_token(conn, token)
    if not record:
        return False
    rfc = record.get("rfc")
    if not rfc:
        with _portal_cursor(conn, write=True) as (_, cur):
            cur.execute(
                _portal_sql("DELETE FROM portal_user_resets WHERE id=?"),
                (record["id"],),
            )
        return False
    portal_set_password(conn, rfc, new_password, require_change=False)
    with _portal_cursor(conn, write=True) as (_, cur):
        cur.execute(
            _portal_sql("DELETE FROM portal_user_resets WHERE id=?"),
            (record["id"],),
        )
    return True


def portal_list_pending_resets(
    conn: sqlite3.Connection,
    rfc: str | None = None,
) -> list[dict]:
    query = """
        SELECT r.id, r.token, r.expires_at, u.rfc
          FROM portal_user_resets r
          JOIN portal_users u ON u.id = r.user_id
          WHERE (? IS NULL OR u.rfc = ?)
          ORDER BY r.expires_at DESC
      """
    records: list[dict] = []
    now = datetime.now(timezone.utc)
    with _portal_cursor(conn, write=True) as (_, cur):
        cur.execute(_portal_sql(query), (rfc, rfc))
        rows = cur.fetchall()
        for row in rows:
            expires_raw = row[2]
            if isinstance(expires_raw, datetime):
                expires = expires_raw
            else:
                try:
                    expires = datetime.fromisoformat(expires_raw)
                except Exception:
                    expires = None
            if expires and expires < now:
                cur.execute(
                    _portal_sql("DELETE FROM portal_user_resets WHERE id=?"),
                    (row[0],),
                )
                continue
            records.append(
                {
                    "id": row[0],
                    "token": row[1],
                    "expires_at": expires,
                    "rfc": row[3],
                }
            )
    return records


def portal_revoke_reset_tokens(
    conn: sqlite3.Connection,
    *,
    rfc: str | None = None,
    tokens: Sequence[str] | None = None,
) -> None:
    with _portal_cursor(conn, write=True) as (_, cur):
        if tokens:
            prepared = [t for t in tokens if t]
            if prepared:
                cur.executemany(
                    _portal_sql("DELETE FROM portal_user_resets WHERE token=?"),
                    [(token,) for token in prepared],
                )
        elif rfc:
            norm_rfc = _normalize_rfc(rfc)
            cur.execute(
                _portal_sql(
                    """
                    DELETE FROM portal_user_resets
                    WHERE user_id = (SELECT id FROM portal_users WHERE rfc=?)
                    """
                ),
                (norm_rfc,),
            )


def authenticate_portal_user(conn: sqlite3.Connection, rfc: str, password: str):
    norm_rfc = _normalize_rfc(rfc)
    with _portal_cursor(conn) as (_, cur):
        cur.execute(
            _portal_sql(
                """
                SELECT id, rfc, password_hash, permisos, must_change_password
                FROM portal_users
                WHERE rfc=?
                """
            ),
            (norm_rfc,),
        )
        row = cur.fetchone()
    if not row:
        return None
    is_valid, needs_rehash = _verify_password(password, row[2])
    if not is_valid:
        return None
    if needs_rehash:
        new_hash = _hash_password(password)
        try:
            with _portal_cursor(conn, write=True) as (_, cur):
                cur.execute(
                    _portal_sql(
                        "UPDATE portal_users SET password_hash=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
                    ),
                    (new_hash, row[0]),
                )
        except Exception:
            pass
    permisos = _permisos_from_text(row[3])
    return {
        "id": row[0],
        "rfc": row[1],
        "permisos": permisos,
        "must_change_password": bool(row[4]),
    }
# ---------- Seeds y versión ----------
def _seed_parametros_v1(conn):
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO param_costeo_version(nombre, vigente_desde, notas)
        VALUES(?,?,?)
    """, ("v1", None, "Versión inicial sembrada automáticamente"))
    vid = cur.execute("SELECT id FROM param_costeo_version WHERE nombre=?", ("v1",)).fetchone()[0]

    cur.execute("""INSERT OR IGNORE INTO param_diesel(version_id, rendimiento_km_l, precio_litro) VALUES (?,?,?)""", (vid, 2.8, 26.5))
    cur.execute("""INSERT OR IGNORE INTO param_def(version_id, pct_def, precio_def_litro) VALUES (?,?,?)""", (vid, 0.04, 20.0))
    cur.execute("""INSERT OR IGNORE INTO param_tag(version_id, pct_comision_tag) VALUES (?,?)""", (vid, 0.02))
    cur.execute("""INSERT OR IGNORE INTO param_costos_km(version_id, costo_llantas_km, costo_mantto_km) VALUES (?,?,?)""", (vid, 1.80, 1.50))
    cur.execute("""INSERT OR IGNORE INTO param_depreciacion(version_id, costo_adq, valor_residual, vida_anios, km_anuales) VALUES (?,?,?,?,?)""", (vid, 2500000.0, 250000.0, 5, 100000))
    cur.execute("""INSERT OR IGNORE INTO param_seguros(version_id, prima_anual, km_anuales) VALUES (?,?,?)""", (vid, 120000.0, 100000))
    cur.execute("""INSERT OR IGNORE INTO param_financiamiento(version_id, tasa_anual, dias_cobro) VALUES (?,?,?)""", (vid, 0.25, 30))
    cur.execute("""INSERT OR IGNORE INTO param_overhead(version_id, pct_overhead) VALUES (?,?)""", (vid, 0.10))
    cur.execute("""INSERT OR IGNORE INTO param_utilidad(version_id, pct_utilidad) VALUES (?,?)""", (vid, 0.00))
    cur.execute("""INSERT OR IGNORE INTO param_otros(version_id, viatico_dia, permiso_viaje, custodia_km) VALUES (?,?,?,?)""", (vid, 900.0, 500.0, 0.0))
    cur.execute("""INSERT OR IGNORE INTO param_politicas(version_id, incluye_en_base) VALUES (?,?)""",
                (vid, '["peajes","diesel","llantas","mantto","depreciacion","seguros","viaticos","permisos","def","custodia","tag"]'))
    conn.commit()


def get_active_version_id(conn) -> int:
    cur = conn.cursor()
    row = cur.execute("""
      SELECT id FROM param_costeo_version
      WHERE vigente_desde IS NOT NULL AND (vigente_hasta IS NULL OR vigente_hasta='')
      ORDER BY id DESC LIMIT 1
    """).fetchone()
    if row:
        return row[0]
    row = cur.execute("SELECT id FROM param_costeo_version ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None


def clone_version(conn, base_version_id: int, new_name: str) -> int:
    cur = conn.cursor()
    cur.execute("INSERT INTO param_costeo_version(nombre) VALUES(?)", (new_name,))
    new_vid = cur.lastrowid

    def _copy(table, cols):
        cols_csv = ",".join(cols)
        select_cols = ",".join(["? AS version_id" if c == "version_id" else c for c in cols])
        cur.execute(f"""
          INSERT INTO {table} ({cols_csv})
          SELECT {select_cols}
          FROM {table} WHERE version_id=?""", (new_vid, base_version_id))

    _copy("param_diesel",        ["version_id","rendimiento_km_l","precio_litro"])
    _copy("param_def",           ["version_id","pct_def","precio_def_litro"])
    _copy("param_tag",           ["version_id","pct_comision_tag"])
    _copy("param_costos_km",     ["version_id","costo_llantas_km","costo_mantto_km"])
    _copy("param_depreciacion",  ["version_id","costo_adq","valor_residual","vida_anios","km_anuales"])
    _copy("param_seguros",       ["version_id","prima_anual","km_anuales"])
    _copy("param_financiamiento",["version_id","tasa_anual","dias_cobro"])
    _copy("param_overhead",      ["version_id","pct_overhead"])
    _copy("param_utilidad",      ["version_id","pct_utilidad"])
    _copy("param_otros",         ["version_id","viatico_dia","permiso_viaje","custodia_km"])
    _copy("param_politicas",     ["version_id","incluye_en_base"])

    conn.commit()
    return new_vid


def publish_version(conn, version_id: int):
    cur = conn.cursor()
    cur.execute("""
      UPDATE param_costeo_version
      SET vigente_hasta = DATE('now')
      WHERE vigente_desde IS NOT NULL AND (vigente_hasta IS NULL OR vigente_hasta='')
    """)
    cur.execute("""
      UPDATE param_costeo_version
      SET vigente_desde = DATE('now'), vigente_hasta = NULL
      WHERE id=?
    """, (version_id,))
    conn.commit()
