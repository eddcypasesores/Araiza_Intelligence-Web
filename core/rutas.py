from pathlib import Path
import pandas as pd
from .config import ROUTES_CSV
from .utils import normalize_name

def load_routes() -> dict[str, list[str]]:
    routes = {}
    p = Path(ROUTES_CSV)
    if p.exists():
        df = pd.read_csv(p, encoding="utf-8").fillna("")
        for ruta, chunk in df.groupby("RUTA", sort=False):
            routes[ruta] = [str(x).strip() for x in chunk["CASETA"].tolist() if str(x).strip()]
    if not routes:
        routes = {
            "TOLUCA-NUEVO LAREDO": [
                "EL DORADO","ATLACOMULCO SUR","CHICHIMEQUILLAS",
                "LIB. OTE. S.L.P.","LIB. MATEHUALA","LOS CHORROS","LINCOLN","SABINAS","NVO LAREDO KM26",
            ],
            "NVO LAREDO-PANINDICUARO": [
                "NVO LAREDO PINFRA","SABINAS","LINCOLN","LOS CHORROS","LIB. MATEHUALA",
                "VENTURA - EL PEYOTE","LIB. OTE. S.L.P.","SAN FELIPE","MENDOZA","LA CINTA","PANINDICUARO",
            ]
        }
    return routes


def plazas_catalog(routes: dict[str, list[str]], conn=None) -> list[str]:
    """Devuelve el catálogo de plazas usando los nombres más recientes.

    Se parte de los nombres que vienen en la ruta CSV (para conservar el
    orden lógico y compatibilidad con `find_subsequence_between`), pero si la
    base de datos tiene un nombre distinto que normaliza al mismo valor,
    preferimos el nombre de la BD.  Esto evita diferencias como
    "NVO LAREDO" vs "NUEVO LAREDO" que provocaban que la calculadora no
    encontrara la tarifa.
    """

    plazas_ruta = {p for lista in routes.values() for p in lista}

    if conn is None:
        return sorted(plazas_ruta)

    try:
        import pandas as pd  # local para evitar dependencia global

        df = pd.read_sql_query("SELECT DISTINCT nombre FROM plazas", conn)
    except Exception:
        return sorted(plazas_ruta)

    canonicos = {normalize_name(nombre): nombre for nombre in df["nombre"].tolist()}

    resultado = set()

    for plaza in plazas_ruta:
        norm = normalize_name(plaza)
        resultado.add(canonicos.get(norm, plaza))

    for canonico in df["nombre"].tolist():
        resultado.add(canonico)

    return sorted(resultado)

def find_subsequence_between(routes: dict[str, list[str]], a: str, b: str):
    a_norm, b_norm = normalize_name(a), normalize_name(b)
    best = None
    for name, seq in routes.items():
        norm = [normalize_name(x) for x in seq]
        if a_norm in norm and b_norm in norm:
            ia, ib = norm.index(a_norm), norm.index(b_norm)
            sub = seq[ia:ib+1] if ia <= ib else list(reversed(seq[ib:ia+1]))
            if (best is None) or (len(sub) < len(best[1])):
                best = (name, sub)
    return best
