import pandas as pd
from .utils import normalize_name

def resolve_plaza_candidates(conn, input_name: str) -> list[str]:
    all_plazas = pd.read_sql_query("SELECT DISTINCT nombre FROM plazas", conn)["nombre"].tolist()
    norm_target = normalize_name(input_name)
    exact = [p for p in all_plazas if normalize_name(p) == norm_target]
    if exact:
        return exact
    tokens = [t for t in norm_target.split(" ") if len(t) >= 2]
    relaxed = []
    for p in all_plazas:
        np = normalize_name(p)
        if all(t in np for t in tokens):
            relaxed.append(p)
    relaxed.sort(key=lambda p: abs(len(normalize_name(p)) - len(norm_target)))
    return relaxed[:5]

def tarifa_por_plaza(conn, plaza_nombre: str, clase: str) -> float:
    """Devuelve la tarifa para una plaza y clase, tolerando variaciones de nombre."""

    c = clase.strip().upper()
    cur = conn.cursor()

    def _buscar(nombre: str):
        row = cur.execute(
            """
            SELECT pt.tarifa_mxn
            FROM plaza_tarifas pt
            JOIN plazas p ON p.id = pt.plaza_id
            WHERE p.nombre = ? AND pt.clase = ?
            """,
            (nombre, c),
        ).fetchone()
        if row:
            return float(row[0] or 0.0)

        # fallback a AUTOMOVIL si no existe la clase pedida
        row = cur.execute(
            """
            SELECT pt.tarifa_mxn
            FROM plaza_tarifas pt
            JOIN plazas p ON p.id = pt.plaza_id
            WHERE p.nombre = ? AND pt.clase = 'AUTOMOVIL'
            """,
            (nombre,),
        ).fetchone()
        if row:
            return float(row[0] or 0.0)
        return None

    candidatos = [plaza_nombre]
    for cand in resolve_plaza_candidates(conn, plaza_nombre):
        if cand not in candidatos:
            candidatos.append(cand)

    for candidato in candidatos:
        resultado = _buscar(candidato)
        if resultado is not None:
            return resultado

    return 0.0

