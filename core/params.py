# core/params.py
import json
import pandas as pd

def read_params(conn, version_id: int) -> dict:
    q = lambda sql, *p: pd.read_sql_query(sql, conn, params=p).to_dict(orient="records")

    out = {"version_id": version_id}
    out["diesel"]        = q("SELECT * FROM param_diesel WHERE version_id=?", version_id)[0]
    out["def"]           = q("SELECT * FROM param_def WHERE version_id=?", version_id)[0]
    out["tag"]           = q("SELECT * FROM param_tag WHERE version_id=?", version_id)[0]
    out["costos_km"]     = q("SELECT * FROM param_costos_km WHERE version_id=?", version_id)[0]
    out["depreciacion"]  = q("SELECT * FROM param_depreciacion WHERE version_id=?", version_id)[0]
    out["seguros"]       = q("SELECT * FROM param_seguros WHERE version_id=?", version_id)[0]
    out["financiamiento"]= q("SELECT * FROM param_financiamiento WHERE version_id=?", version_id)[0]
    out["overhead"]      = q("SELECT * FROM param_overhead WHERE version_id=?", version_id)[0]
    out["utilidad"]      = q("SELECT * FROM param_utilidad WHERE version_id=?", version_id)[0]
    out["otros"]         = q("SELECT * FROM param_otros WHERE version_id=?", version_id)[0]
    pol                  = q("SELECT * FROM param_politicas WHERE version_id=?", version_id)[0]
    try:
        pol["incluye_en_base"] = json.loads(pol["incluye_en_base"])
    except Exception:
        pol["incluye_en_base"] = []
    out["politicas"] = pol
    return out
