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
    cand = resolve_plaza_candidates(conn, plaza_nombre)
    if not cand:
        return 0.0
    placeholders = ",".join(["?"] * len(cand))
    sql = f"""
        SELECT MAX(CAST(t.tarifa_mxn AS REAL)) AS tarifa
        FROM plazas p
        JOIN plaza_tarifas t ON t.plaza_id = p.id AND t.clase = ?
        WHERE p.nombre IN ({placeholders})
    """
    df = pd.read_sql_query(sql, conn, params=[clase, *cand])
    val = df.iloc[0]["tarifa"]
    return float(val) if val is not None else 0.0
