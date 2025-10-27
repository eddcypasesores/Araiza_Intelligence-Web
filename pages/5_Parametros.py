import json
import sqlite3
import pandas as pd
import streamlit as st

from core.auth import ensure_session_from_token
from core.db import (
    get_conn,
    ensure_schema,
    get_active_version_id,
    clone_version,
    publish_version,
)
from core.params import read_params
from core.navigation import render_nav


st.set_page_config(page_title="Parámetros de Costeo", layout="wide")
ensure_session_from_token()

# Seguridad
if "usuario" not in st.session_state or "rol" not in st.session_state:
    st.warning("Debes iniciar sesión.")
    params = {k: v for k, v in st.query_params.items() if k not in {"logout", "next"}}
    params["next"] = "pages/5_Parametros.py"
    try:
        st.experimental_set_query_params(**params)
    except Exception:
        pass
    try:
        st.switch_page("pages/1_Calculadora.py")
    except Exception:
        st.stop()
    st.stop()
if st.session_state["rol"] != "admin":
    st.error("Solo administradores.")
    st.stop()

conn = get_conn()
ensure_schema(conn)

VIEW_KEY = "parametros_view"
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

render_nav(active_top="parametros", active_child=view)

VIEW_TITLES = {
    "consultar": "📊 Consultar versiones de parámetros",
    "agregar": "➕ Crear nueva versión",
    "modificar": "✏️ Editar parámetros",
    "eliminar": "🗑️ Eliminar versión",
}

st.title(VIEW_TITLES[view])


def load_versions() -> pd.DataFrame:
    return pd.read_sql_query(
        """
          SELECT id, nombre,
                 COALESCE(vigente_desde,'—') AS vigente_desde,
                 COALESCE(vigente_hasta,'')  AS vigente_hasta
          FROM param_costeo_version
          ORDER BY id DESC
        """,
        conn,
    )


def render_consultar():
    df_vers = load_versions()
    if df_vers.empty:
        st.error("Sin versiones. Recarga la app para sembrar v1.")
        return

    labels = [
        f"{row.id} — {row.nombre} ({'vigente' if row.vigente_desde != '—' and not row.vigente_hasta else 'no vigente'})"
        for row in df_vers.itertuples()
    ]
    sel = st.selectbox("Selecciona versión", labels, index=0)
    current_vid = int(sel.split(" — ")[0])

    params = read_params(conn, current_vid)
    rows: list[dict[str, object]] = []
    for categoria, valores in params.items():
        if categoria == "version_id":
            continue
        if isinstance(valores, dict):
            for clave, valor in valores.items():
                if clave == "version_id":
                    continue
                if isinstance(valor, list):
                    valor = ", ".join(map(str, valor))
                rows.append({"Categoría": categoria, "Parámetro": clave, "Valor": valor})
        else:
            rows.append({"Categoría": categoria, "Parámetro": "valor", "Valor": valores})

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_agregar():
    df_vers = load_versions()
    if df_vers.empty:
        st.error("Sin versiones base para clonar. Edita la BD para crear v1.")
        return

    labels = [f"{row.id} — {row.nombre}" for row in df_vers.itertuples()]
    sel = st.selectbox("Versión base", labels, index=0)
    base_vid = int(sel.split(" — ")[0])

    new_name = st.text_input("Nombre para la nueva versión", value="v1.1")

    if st.button("Clonar versión", type="primary"):
        try:
            vid_new = clone_version(conn, base_vid, new_name)
            st.success(f"Versión clonada como {new_name} (id {vid_new}).")
            st.rerun()
        except sqlite3.IntegrityError as e:
            st.error(f"No se pudo clonar: {e}")
        except Exception as e:
            st.error(f"Error inesperado: {e}")


def render_modificar():
    df_vers = load_versions()
    if df_vers.empty:
        st.error("Sin versiones para editar.")
        return

    labels = [
        f"{row.id} — {row.nombre} ({'vigente' if row.vigente_desde != '—' and not row.vigente_hasta else 'no vigente'})"
        for row in df_vers.itertuples()
    ]
    sel = st.selectbox("Selecciona versión", labels, index=0)
    current_vid = int(sel.split(" — ")[0])

    if st.button("Publicar como vigente", type="secondary"):
        publish_version(conn, current_vid)
        st.success("Versión publicada como vigente.")
        st.rerun()

    params = read_params(conn, current_vid)

    def num(name, value, step=0.01, minv=0.0, help_txt=None, key=None):
        v = 0.0 if value is None else float(value)
        stp = float(step)
        mn = float(minv)
        return st.number_input(
            name,
            value=v,
            step=stp,
            min_value=mn,
            format="%.2f",
            help=help_txt,
            key=key,
        )

    st.subheader("Diésel")
    c1, c2 = st.columns(2)
    with c1:
        r_km_l = num(
            "Rendimiento (km/L)",
            params["diesel"]["rendimiento_km_l"],
            0.1,
            0.1,
            key="diesel_rend",
        )
    with c2:
        p_litro = num(
            "Precio por litro ($/L)",
            params["diesel"]["precio_litro"],
            0.1,
            0.0,
            key="diesel_precio",
        )

    st.subheader("DEF")
    c1, c2 = st.columns(2)
    with c1:
        pct_def = num(
            "% DEF sobre litros",
            params["def"]["pct_def"],
            0.001,
            0.0,
            key="def_pct",
        )
    with c2:
        p_def = num(
            "Precio DEF ($/L)",
            params["def"]["precio_def_litro"],
            0.1,
            0.0,
            key="def_precio",
        )

    st.subheader("Comisión TAG")
    pct_tag = num(
        "% comisión TAG sobre peajes",
        params["tag"]["pct_comision_tag"],
        0.001,
        0.0,
        key="tag_pct",
    )

    st.subheader("Costos por km")
    c1, c2 = st.columns(2)
    with c1:
        costo_ll = num(
            "Llantas ($/km)",
            params["costos_km"]["costo_llantas_km"],
            0.01,
            0.0,
            key="ck_llantas",
        )
    with c2:
        costo_mt = num(
            "Mantenimiento ($/km)",
            params["costos_km"]["costo_mantto_km"],
            0.01,
            0.0,
            key="ck_mantto",
        )

    st.subheader("Depreciación")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        costo_adq = num(
            "Costo adquisición ($)",
            params["depreciacion"]["costo_adq"],
            1000.0,
            0.0,
            key="dep_costo_adq",
        )
    with c2:
        val_res = num(
            "Valor residual ($)",
            params["depreciacion"]["valor_residual"],
            1000.0,
            0.0,
            key="dep_val_res",
        )
    with c3:
        vida = st.number_input(
            "Vida (años)",
            value=int(params["depreciacion"]["vida_anios"]),
            min_value=1,
            step=1,
            key="dep_vida",
        )
    with c4:
        km_an = st.number_input(
            "Km anuales",
            value=int(params["depreciacion"]["km_anuales"]),
            min_value=1,
            step=1000,
            key="dep_km_anuales",
        )

    st.subheader("Seguros")
    c1, c2 = st.columns(2)
    with c1:
        prima = num(
            "Prima anual ($)",
            params["seguros"]["prima_anual"],
            100.0,
            0.0,
            key="seg_prima",
        )
    with c2:
        km_seguros = st.number_input(
            "Km anuales",
            value=int(params["seguros"]["km_anuales"]),
            min_value=1,
            step=1000,
            key="seg_km_anuales",
        )

    st.subheader("Financiamiento")
    c1, c2 = st.columns(2)
    with c1:
        tasa = num(
            "Tasa anual",
            params["financiamiento"]["tasa_anual"],
            0.001,
            0.0,
            key="fin_tasa",
        )
    with c2:
        dias_cobro = st.number_input(
            "Días de cobro",
            value=int(params["financiamiento"]["dias_cobro"]),
            min_value=1,
            step=1,
            key="fin_dias",
        )

    st.subheader("Overhead y Utilidad")
    c1, c2 = st.columns(2)
    with c1:
        pct_ov = num(
            "% Overhead",
            params["overhead"]["pct_overhead"],
            0.001,
            0.0,
            key="ov_pct",
        )
    with c2:
        pct_ut = num(
            "% Utilidad",
            params["utilidad"]["pct_utilidad"],
            0.001,
            0.0,
            key="ut_pct",
        )

    st.subheader("Otros")
    c1, c2, c3 = st.columns(3)
    with c1:
        viatico_dia = num(
            "Viático por día ($)",
            params["otros"]["viatico_dia"],
            10.0,
            0.0,
            key="ot_viatico",
        )
    with c2:
        permiso_viaje = num(
            "Permiso por viaje ($)",
            params["otros"]["permiso_viaje"],
            10.0,
            0.0,
            key="ot_permiso",
        )
    with c3:
        custodia_km = num(
            "Custodia ($/km)",
            params["otros"]["custodia_km"],
            0.01,
            0.0,
            key="ot_custodia",
        )

    st.subheader("Políticas (Base para financiamiento/overhead/utilidad)")
    base_opts = [
        "peajes",
        "diesel",
        "llantas",
        "mantto",
        "depreciacion",
        "seguros",
        "viaticos",
        "permisos",
        "def",
        "custodia",
        "tag",
    ]
    sel_base = st.multiselect(
        "Conceptos que integran la 'Base'",
        base_opts,
        default=params["politicas"]["incluye_en_base"],
    )

    if st.button("💾 Guardar cambios en esta versión", type="primary"):
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE param_diesel SET rendimiento_km_l=?, precio_litro=? WHERE version_id=?",
                (r_km_l, p_litro, params["version_id"]),
            )
            cur.execute(
                "UPDATE param_def SET pct_def=?, precio_def_litro=? WHERE version_id=?",
                (pct_def, p_def, params["version_id"]),
            )
            cur.execute(
                "UPDATE param_tag SET pct_comision_tag=? WHERE version_id=?",
                (pct_tag, params["version_id"]),
            )
            cur.execute(
                "UPDATE param_costos_km SET costo_llantas_km=?, costo_mantto_km=? WHERE version_id=?",
                (costo_ll, costo_mt, params["version_id"]),
            )
            cur.execute(
                "UPDATE param_depreciacion SET costo_adq=?, valor_residual=?, vida_anios=?, km_anuales=? WHERE version_id=?",
                (costo_adq, val_res, int(vida), int(km_an), params["version_id"]),
            )
            cur.execute(
                "UPDATE param_seguros SET prima_anual=?, km_anuales=? WHERE version_id=?",
                (prima, int(km_seguros), params["version_id"]),
            )
            cur.execute(
                "UPDATE param_financiamiento SET tasa_anual=?, dias_cobro=? WHERE version_id=?",
                (tasa, int(dias_cobro), params["version_id"]),
            )
            cur.execute(
                "UPDATE param_overhead SET pct_overhead=? WHERE version_id=?",
                (pct_ov, params["version_id"]),
            )
            cur.execute(
                "UPDATE param_utilidad SET pct_utilidad=? WHERE version_id=?",
                (pct_ut, params["version_id"]),
            )
            cur.execute(
                "UPDATE param_otros SET viatico_dia=?, permiso_viaje=?, custodia_km=? WHERE version_id=?",
                (viatico_dia, permiso_viaje, custodia_km, params["version_id"]),
            )
            cur.execute(
                "UPDATE param_politicas SET incluye_en_base=? WHERE version_id=?",
                (json.dumps(sel_base), params["version_id"]),
            )
            conn.commit()
            st.success("Cambios guardados.")
        except Exception as e:
            conn.rollback()
            st.error(f"No se pudieron guardar los cambios: {e}")


def render_eliminar():
    df_vers = load_versions()
    if df_vers.empty:
        st.info("No hay versiones para eliminar.")
        return

    labels = [f"{row.id} — {row.nombre}" for row in df_vers.itertuples()]
    sel = st.selectbox("Versión a eliminar", labels)
    target_vid = int(sel.split(" — ")[0])

    vigente = get_active_version_id(conn)
    if vigente and target_vid == vigente:
        st.warning("No puedes eliminar la versión actualmente vigente.")
        return

    if st.button("Eliminar versión", type="primary"):
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM param_costeo_version WHERE id=?", (target_vid,))
            conn.commit()
            st.success("Versión eliminada.")
            st.rerun()
        except Exception as e:
            conn.rollback()
            st.error(f"No se pudo eliminar la versión: {e}")


if view == "consultar":
    render_consultar()
elif view == "agregar":
    render_agregar()
elif view == "modificar":
    render_modificar()
elif view == "eliminar":
    render_eliminar()