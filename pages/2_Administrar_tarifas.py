import pandas as pd
import streamlit as st

from core.db import ensure_schema, get_conn


if "usuario" not in st.session_state or "rol" not in st.session_state:
    st.warning("⚠️ Debes iniciar sesión primero.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()
    st.stop()

if st.session_state["rol"] != "admin":
    st.error("🚫 No tienes permiso para acceder a esta página.")
    st.stop()


st.set_page_config(page_title="Admin tarifas", layout="wide")
st.header("🛠️ Modificación de precios de casetas")

conn = get_conn()
ensure_schema(conn)

vias = pd.read_sql_query("SELECT id, nombre FROM vias ORDER BY nombre", conn)
if vias.empty:
    st.info("Carga primero las vías y plazas mediante el ETL de peajes.")
    st.stop()

via_nombre = st.selectbox("Vía", vias["nombre"].tolist())
via_id = int(vias.loc[vias["nombre"] == via_nombre, "id"].iloc[0])

plazas = pd.read_sql_query(
    "SELECT id AS plaza_id, nombre AS plaza FROM plazas WHERE via_id=? ORDER BY orden",
    conn,
    params=(via_id,),
)
if plazas.empty:
    st.info("Esta vía no tiene plazas asociadas.")
    st.stop()

plaza_nombre = st.selectbox("Plaza", plazas["plaza"].tolist())
plaza_id = int(plazas.loc[plazas["plaza"] == plaza_nombre, "plaza_id"].iloc[0])

tarifas = pd.read_sql_query(
    "SELECT clase, tarifa_mxn FROM plaza_tarifas WHERE plaza_id=? ORDER BY clase",
    conn,
    params=(plaza_id,),
)

clases = ["MOTO", "AUTOMOVIL", "B2", "B3", "B4", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"]
faltantes = [c for c in clases if c not in tarifas["clase"].tolist()]
if faltantes:
    tarifas = pd.concat(
        [tarifas, pd.DataFrame({"clase": faltantes, "tarifa_mxn": [0.0] * len(faltantes)})],
        ignore_index=True,
    )

tarifas = tarifas.sort_values("clase").reset_index(drop=True)

edited = st.data_editor(
    tarifas,
    use_container_width=True,
    hide_index=True,
    column_config={
        "clase": st.column_config.TextColumn("Clase", disabled=True),
        "tarifa_mxn": st.column_config.NumberColumn("Tarifa (MXN)", format="%.2f"),
    },
    key="editor_admin_tarifas",
)


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if st.button("💾 Guardar cambios", type="primary"):
    cur = conn.cursor()
    for _, row in edited.iterrows():
        clase = str(row["clase"]).strip().upper()
        tarifa = _to_float(row.get("tarifa_mxn"))
        if not clase:
            continue
        cur.execute(
            """
            INSERT INTO plaza_tarifas(plaza_id, clase, tarifa_mxn)
            VALUES(?,?,?)
            ON CONFLICT(plaza_id, clase) DO UPDATE SET tarifa_mxn=excluded.tarifa_mxn
            """,
            (plaza_id, clase, tarifa),
        )

    conn.commit()
    st.success("Tarifas actualizadas ✅")
    st.experimental_rerun()