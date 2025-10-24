import pandas as pd
import streamlit as st

from core.db import ensure_schema, get_conn, CLASES
from core.navigation import render_nav


st.set_page_config(page_title="Tarifas", layout="wide")

# ---- Seguridad ----
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


conn = get_conn()
ensure_schema(conn)

VIEW_KEY = "tarifas_view"
VALID_VIEWS = {"consultar", "agregar", "modificar", "eliminar"}

params = st.query_params
query_view = params.get(VIEW_KEY)
if isinstance(query_view, list):
    candidate = query_view[-1] if query_view else None
elif query_view is None:
    candidate = None
else:
    candidate = query_view

if candidate in VALID_VIEWS:
    st.session_state[VIEW_KEY] = candidate

view = st.session_state.get(VIEW_KEY, "consultar")
if view not in VALID_VIEWS:
    view = "consultar"
    st.session_state[VIEW_KEY] = view

render_nav(active_top="tarifas", active_child=view)

VIEW_TITLES = {
    "consultar": "📊 Consultar tarifas",
    "agregar": "➕ Agregar tarifa",
    "modificar": "✏️ Modificar tarifas",
    "eliminar": "🗑️ Eliminar tarifas",
}

st.title(VIEW_TITLES[view])


def select_via_plaza():
    vias = pd.read_sql_query("SELECT id, nombre FROM vias ORDER BY nombre", conn)
    if vias.empty:
        st.info("Carga primero las vías y plazas mediante el ETL de peajes.")
        return None

    via_nombre = st.selectbox("Vía", vias["nombre"].tolist())
    via_id = int(vias.loc[vias["nombre"] == via_nombre, "id"].iloc[0])

    plazas = pd.read_sql_query(
        "SELECT id AS plaza_id, nombre AS plaza FROM plazas WHERE via_id=? ORDER BY orden",
        conn,
        params=(via_id,),
    )
    if plazas.empty:
        st.info("Esta vía no tiene plazas asociadas.")
        return None

    plaza_nombre = st.selectbox("Plaza", plazas["plaza"].tolist())
    plaza_id = int(plazas.loc[plazas["plaza"] == plaza_nombre, "plaza_id"].iloc[0])
    return via_id, via_nombre, plaza_id, plaza_nombre


def tarifas_por_plaza(plaza_id: int) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT clase, tarifa_mxn FROM plaza_tarifas WHERE plaza_id=? ORDER BY clase",
        conn,
        params=(plaza_id,),
    )


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


selection = select_via_plaza()
if selection is None:
    st.stop()

_, via_nombre, plaza_id, plaza_nombre = selection
st.caption(f"Vía seleccionada: **{via_nombre}** · Plaza: **{plaza_nombre}**")

tarifas = tarifas_por_plaza(plaza_id)


if view == "consultar":
    if tarifas.empty:
        st.info("No hay tarifas registradas para esta plaza.")
    else:
        st.dataframe(
            tarifas.sort_values("clase"),
            use_container_width=True,
            hide_index=True,
        )

elif view == "agregar":
    existentes = tarifas["clase"].tolist()
    faltantes = [c for c in CLASES if c not in existentes]
    sugerida = faltantes[0] if faltantes else (existentes[0] if existentes else "")

    with st.form("form_tarifa_add"):
        clase = st.text_input(
            "Clase",
            value=sugerida,
            help="Sugerimos utilizar las clases estándar en mayúsculas.",
        ).strip().upper()
        tarifa = st.number_input("Tarifa (MXN)", min_value=0.0, step=1.0, format="%.2f")
        submitted = st.form_submit_button("Guardar tarifa", type="primary")

    if submitted:
        if not clase:
            st.error("La clase es obligatoria.")
        else:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO plaza_tarifas(plaza_id, clase, tarifa_mxn)
                VALUES(?,?,?)
                ON CONFLICT(plaza_id, clase) DO UPDATE SET tarifa_mxn=excluded.tarifa_mxn
                """,
                (plaza_id, clase, float(tarifa)),
            )
            conn.commit()
            st.success(f"Tarifa para {clase} guardada correctamente.")
            st.experimental_rerun()

elif view == "modificar":
    df_edit = tarifas.copy()
    faltantes = [c for c in CLASES if c not in df_edit["clase"].tolist()]
    if faltantes:
        df_edit = pd.concat(
            [
                df_edit,
                pd.DataFrame({"clase": faltantes, "tarifa_mxn": [0.0] * len(faltantes)}),
            ],
            ignore_index=True,
        )
    df_edit = df_edit.sort_values("clase").reset_index(drop=True)

    edited = st.data_editor(
        df_edit,
        use_container_width=True,
        hide_index=True,
        column_config={
            "clase": st.column_config.TextColumn("Clase", disabled=True),
            "tarifa_mxn": st.column_config.NumberColumn("Tarifa (MXN)", format="%.2f"),
        },
        key="editor_admin_tarifas",
    )

    if st.button("💾 Guardar cambios", type="primary"):
        cur = conn.cursor()
        for _, row in edited.iterrows():
            clase = str(row["clase"]).strip().upper()
            tarifa_val = _to_float(row.get("tarifa_mxn"))
            if not clase:
                continue
            cur.execute(
                """
                INSERT INTO plaza_tarifas(plaza_id, clase, tarifa_mxn)
                VALUES(?,?,?)
                ON CONFLICT(plaza_id, clase) DO UPDATE SET tarifa_mxn=excluded.tarifa_mxn
                """,
                (plaza_id, clase, tarifa_val),
            )
        conn.commit()
        st.success("Tarifas actualizadas ✅")
        st.experimental_rerun()

elif view == "eliminar":
    if tarifas.empty:
        st.info("No hay tarifas registradas para eliminar.")
    else:
        clases = tarifas.sort_values("clase")["clase"].tolist()
        seleccion = st.multiselect(
            "Selecciona las clases a eliminar",
            clases,
            help="Las clases seleccionadas se eliminarán de la plaza actual.",
        )
        if st.button(
            "Eliminar seleccionadas",
            type="primary",
            disabled=not seleccion,
        ):
            cur = conn.cursor()
            cur.executemany(
                "DELETE FROM plaza_tarifas WHERE plaza_id=? AND clase=?",
                [(plaza_id, clase) for clase in seleccion],
            )
            conn.commit()
            st.success("Tarifas eliminadas.")
            st.experimental_rerun()
