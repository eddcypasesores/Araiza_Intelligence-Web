# core/db.py
import csv
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd  # puede usarse en otros helpers

from .config import DB_PATH, ROUTES_CSV, TARIFFS_XLSX


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

    # Seed mínimo: usuario admin
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM usuarios")
    if (cur.fetchone() or [0])[0] == 0:
        cur.execute("INSERT INTO usuarios(username,password,rol) VALUES(?,?,?)",
                    ("admin", "1234", "admin"))
        conn.commit()

    # Seed parámetros v1 (idempotente)
    cur.execute("SELECT COUNT(*) FROM param_costeo_version")
    if (cur.fetchone() or [0])[0] == 0:
        _seed_parametros_v1(conn)

    # >>> IMPORTANTE: cargar rutas/plazas/tarifas si está vacío
    _seed_routes_if_empty(conn)


# ---------- Helpers de autenticación / relación ----------
def validar_usuario(conn, username: str, password: str):
    cur = conn.cursor()
    cur.execute("SELECT rol FROM usuarios WHERE username=? AND password=?", (username, password))
    row = cur.fetchone()
    return row[0] if row else None

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
