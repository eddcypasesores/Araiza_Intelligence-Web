import os
import sqlite3
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from core.config import DB_PATH, PORTAL_DATABASE_URL
from core.db import ensure_portal_schema


PORTAL_SOURCE_DATABASE_URL = os.getenv("PORTAL_SOURCE_DATABASE_URL", "").strip()

_SELECT_PORTAL_USERS = """
    SELECT rfc, password_hash, regimen_fiscal, calle, colonia, cp,
           municipio, email, telefono, permisos, must_change_password,
           created_at, updated_at
    FROM portal_users
"""


def _fetch_from_sqlite() -> list[dict]:
    sqlite_conn = sqlite3.connect(str(DB_PATH))
    try:
        sqlite_conn.row_factory = sqlite3.Row
        rows = sqlite_conn.execute(_SELECT_PORTAL_USERS).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        if "no such table" in message:
            raise SystemExit(
                "No existe la tabla portal_users en SQLite. "
                "Si tus usuarios viven en otro PostgreSQL (Render, etc.), "
                "define PORTAL_SOURCE_DATABASE_URL con esa cadena y vuelve a ejecutar."
            ) from exc
        raise
    finally:
        sqlite_conn.close()


def _fetch_from_postgres() -> list[dict]:
    with psycopg.connect(PORTAL_SOURCE_DATABASE_URL, row_factory=dict_row) as src_conn:
        with src_conn.cursor() as cur:
            cur.execute(_SELECT_PORTAL_USERS)
            return cur.fetchall()


def _load_source_rows() -> list[dict]:
    if PORTAL_SOURCE_DATABASE_URL:
        print("Leyendo usuarios desde PORTAL_SOURCE_DATABASE_URL...")
        return _fetch_from_postgres()

    print(f"Leyendo usuarios desde SQLite ({DB_PATH})...")
    return _fetch_from_sqlite()


def _normalize_ts(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main():
    if not PORTAL_DATABASE_URL:
        raise SystemExit(
            "Define PORTAL_DATABASE_URL o DATABASE_URL antes de ejecutar la migracion."
        )

    ensure_portal_schema(None)

    rows = _load_source_rows()
    if not rows:
        print("No se encontraron usuarios para migrar.")
        return

    with psycopg.connect(PORTAL_DATABASE_URL, autocommit=False) as pg_conn:
        with pg_conn.cursor() as cur:
            for row in rows:
                created_at = _normalize_ts(row.get("created_at")) or datetime.now(timezone.utc)
                updated_at = _normalize_ts(row.get("updated_at")) or datetime.now(timezone.utc)
                cur.execute(
                    """
                    INSERT INTO portal_users(
                        rfc, password_hash, regimen_fiscal, calle, colonia, cp,
                        municipio, email, telefono, permisos, must_change_password,
                        created_at, updated_at
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (rfc) DO UPDATE SET
                        password_hash = EXCLUDED.password_hash,
                        regimen_fiscal = EXCLUDED.regimen_fiscal,
                        calle = EXCLUDED.calle,
                        colonia = EXCLUDED.colonia,
                        cp = EXCLUDED.cp,
                        municipio = EXCLUDED.municipio,
                        email = EXCLUDED.email,
                        telefono = EXCLUDED.telefono,
                        permisos = EXCLUDED.permisos,
                        must_change_password = EXCLUDED.must_change_password,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        row["rfc"],
                        row["password_hash"],
                        row.get("regimen_fiscal"),
                        row.get("calle"),
                        row.get("colonia"),
                        row.get("cp"),
                        row.get("municipio"),
                        row.get("email"),
                        row.get("telefono"),
                        row.get("permisos") or "[]",
                        bool(row.get("must_change_password")),
                        created_at,
                        updated_at,
                    ),
                )
        pg_conn.commit()

    print(f"Usuarios migrados: {len(rows)}")


if __name__ == "__main__":
    main()
