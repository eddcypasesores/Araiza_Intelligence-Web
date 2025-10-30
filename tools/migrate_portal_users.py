import sqlite3
from datetime import datetime, timezone

import psycopg

from core.config import DB_PATH, PORTAL_DATABASE_URL
from core.db import ensure_portal_schema


def _normalize_ts(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def main():
    if not PORTAL_DATABASE_URL:
        raise SystemExit(
            "Define PORTAL_DATABASE_URL o DATABASE_URL antes de ejecutar la migración."
        )

    ensure_portal_schema(None)

    sqlite_conn = sqlite3.connect(str(DB_PATH))
    try:
        sqlite_conn.row_factory = sqlite3.Row
        rows = sqlite_conn.execute(
            """
            SELECT rfc, password_hash, regimen_fiscal, calle, colonia, cp,
                   municipio, email, telefono, permisos, must_change_password,
                   created_at, updated_at
            FROM portal_users
            """
        ).fetchall()
    finally:
        sqlite_conn.close()

    if not rows:
        print("No se encontraron usuarios en la base SQLite local.")
        return

    with psycopg.connect(PORTAL_DATABASE_URL, autocommit=False) as pg_conn:
        with pg_conn.cursor() as cur:
            for row in rows:
                created_at = _normalize_ts(row["created_at"]) or datetime.now(timezone.utc)
                updated_at = _normalize_ts(row["updated_at"]) or datetime.now(timezone.utc)
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
                        row["regimen_fiscal"],
                        row["calle"],
                        row["colonia"],
                        row["cp"],
                        row["municipio"],
                        row["email"],
                        row["telefono"],
                        row["permisos"] or "[]",
                        bool(row["must_change_password"]),
                        created_at,
                        updated_at,
                    ),
                )
        pg_conn.commit()

    print(f"Usuarios migrados: {len(rows)}")


if __name__ == "__main__":
    main()
