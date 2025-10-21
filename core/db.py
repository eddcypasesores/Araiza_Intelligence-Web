# core/db.py
import sqlite3
import pandas as pd
from .config import DB_PATH

# =========================
# Conexión
# =========================
def get_conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)  # + tiempo de espera
    conn.execute("PRAGMA journal_mode = WAL;")        # lecturas concurrentes
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 8000;")       # espera hasta 8s si está bloqueada
    conn.execute("PRAGMA foreign_keys = ON;")
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
    # ---- EXISTENTE: dominio de peajes/usuarios/trabajadores ----
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
    _ensure_column(conn, "trabajadores", "numero_economico",   "numero_economico TEXT UNIQUE")
    _ensure_column(conn, "trabajadores", "fecha_registro",     "fecha_registro TEXT")
    _ensure_column(conn, "trabajadores", "salario_diario",     "salario_diario REAL DEFAULT 0")
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

    # ---- NUEVO: PARAMETROS VERSIONADOS DE COSTEO ----
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
        incluye_en_base TEXT NOT NULL, -- JSON con lista de conceptos
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

    # Seed parámetros v1 si no hay versiones
    cur.execute("SELECT COUNT(*) FROM param_costeo_version")
    if (cur.fetchone() or [0])[0] == 0:
        _seed_parametros_v1(conn)

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

# ---------- NUEVO: helpers de parámetros ----------
def _seed_parametros_v1(conn):
    cur = conn.cursor()

    # 1) Crear/obtener versión v1
    cur.execute("""
        INSERT OR IGNORE INTO param_costeo_version(nombre, vigente_desde, notas)
        VALUES(?,?,?)
    """, ("v1", None, "Versión inicial sembrada automáticamente"))
    vid = cur.execute("SELECT id FROM param_costeo_version WHERE nombre=?", ("v1",)).fetchone()[0]

    # 2) Insertar cada bloque SOLO si no existe (clave = version_id)
    cur.execute("""
        INSERT OR IGNORE INTO param_diesel(version_id, rendimiento_km_l, precio_litro)
        VALUES (?,?,?)
    """, (vid, 2.8, 26.5))

    cur.execute("""
        INSERT OR IGNORE INTO param_def(version_id, pct_def, precio_def_litro)
        VALUES (?,?,?)
    """, (vid, 0.04, 20.0))

    cur.execute("""
        INSERT OR IGNORE INTO param_tag(version_id, pct_comision_tag)
        VALUES (?,?)
    """, (vid, 0.02))

    cur.execute("""
        INSERT OR IGNORE INTO param_costos_km(version_id, costo_llantas_km, costo_mantto_km)
        VALUES (?,?,?)
    """, (vid, 1.80, 1.50))

    cur.execute("""
        INSERT OR IGNORE INTO param_depreciacion(version_id, costo_adq, valor_residual, vida_anios, km_anuales)
        VALUES (?,?,?,?,?)
    """, (vid, 2500000.0, 250000.0, 5, 100000))

    cur.execute("""
        INSERT OR IGNORE INTO param_seguros(version_id, prima_anual, km_anuales)
        VALUES (?,?,?)
    """, (vid, 120000.0, 100000))

    cur.execute("""
        INSERT OR IGNORE INTO param_financiamiento(version_id, tasa_anual, dias_cobro)
        VALUES (?,?,?)
    """, (vid, 0.25, 30))

    cur.execute("""
        INSERT OR IGNORE INTO param_overhead(version_id, pct_overhead)
        VALUES (?,?)
    """, (vid, 0.10))

    cur.execute("""
        INSERT OR IGNORE INTO param_utilidad(version_id, pct_utilidad)
        VALUES (?,?)
    """, (vid, 0.00))

    cur.execute("""
        INSERT OR IGNORE INTO param_otros(version_id, viatico_dia, permiso_viaje, custodia_km)
        VALUES (?,?,?,?)
    """, (vid, 900.0, 500.0, 0.0))

    cur.execute("""
        INSERT OR IGNORE INTO param_politicas(version_id, incluye_en_base)
        VALUES (?,?)
    """, (vid, '["peajes","diesel","llantas","mantto","depreciacion","seguros","viaticos","permisos","def","custodia","tag"]'))

    conn.commit()


def get_active_version_id(conn) -> int:
    """
    Devuelve la versión vigente (la primera con vigente_desde no nulo y vigente_hasta nulo),
    o si ninguna está marcada, devuelve la más reciente creada.
    """
    cur = conn.cursor()
    row = cur.execute("""
      SELECT id FROM param_costeo_version
      WHERE vigente_desde IS NOT NULL AND (vigente_hasta IS NULL OR vigente_hasta='')
      ORDER BY id DESC LIMIT 1
    """).fetchone()
    if row: return row[0]
    row = cur.execute("SELECT id FROM param_costeo_version ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None

def clone_version(conn, base_version_id: int, new_name: str) -> int:
    """
    Clona todos los parámetros de base_version_id a una nueva versión con nombre 'new_name'.
    """
    cur = conn.cursor()
    cur.execute("INSERT INTO param_costeo_version(nombre) VALUES(?)", (new_name,))
    new_vid = cur.lastrowid

    def _copy(table, cols):
        cols_csv = ",".join(cols)
        cur.execute(f"""
          INSERT INTO {table} ({cols_csv})
          SELECT {",".join(["? AS version_id" if c=="version_id" else c for c in cols])}
          FROM {table} WHERE version_id=?""", (new_vid, base_version_id))

    _copy("param_diesel", ["version_id","rendimiento_km_l","precio_litro"])
    _copy("param_def", ["version_id","pct_def","precio_def_litro"])
    _copy("param_tag", ["version_id","pct_comision_tag"])
    _copy("param_costos_km", ["version_id","costo_llantas_km","costo_mantto_km"])
    _copy("param_depreciacion", ["version_id","costo_adq","valor_residual","vida_anios","km_anuales"])
    _copy("param_seguros", ["version_id","prima_anual","km_anuales"])
    _copy("param_financiamiento", ["version_id","tasa_anual","dias_cobro"])
    _copy("param_overhead", ["version_id","pct_overhead"])
    _copy("param_utilidad", ["version_id","pct_utilidad"])
    _copy("param_otros", ["version_id","viatico_dia","permiso_viaje","custodia_km"])
    _copy("param_politicas", ["version_id","incluye_en_base"])

    conn.commit()
    return new_vid

def publish_version(conn, version_id: int):
    """
    Marca una versión como vigente desde hoy y cierra la anterior, si existe.
    """
    cur = conn.cursor()
    # cerrar vigente previa
    cur.execute("""
      UPDATE param_costeo_version
      SET vigente_hasta = DATE('now')
      WHERE vigente_desde IS NOT NULL AND (vigente_hasta IS NULL OR vigente_hasta='')
    """)
    # publicar nueva
    cur.execute("""
      UPDATE param_costeo_version
      SET vigente_desde = DATE('now'), vigente_hasta = NULL
      WHERE id=?
    """, (version_id,))
    conn.commit()
