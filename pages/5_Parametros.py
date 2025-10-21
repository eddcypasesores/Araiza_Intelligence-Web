# pages/5_Parametros.py
import json
import sqlite3
import pandas as pd
import streamlit as st
from core.db import get_conn, ensure_schema, get_active_version_id, clone_version, publish_version
from core.params import read_params

st.set_page_config(page_title="Parámetros de Costeo", layout="wide")

# Seguridad
if "usuario" not in st.session_state or "rol" not in st.session_state:
    st.warning("Debes iniciar sesión.")
    st.stop()
if st.session_state["rol"] != "admin":
    st.error("Solo administradores.")
    st.stop()

conn = get_conn(); ensure_schema(conn)

st.title("⚙️ Parámetros de Costeo (versionados)")

# Selector de versión
df_vers = pd.read_sql_query("""
  SELECT id, nombre, COALESCE(vigente_desde,'—') AS vigente_desde,
         COALESCE(vigente_hasta,'') AS vigente_hasta
  FROM param_costeo_version ORDER BY id DESC
""", conn)

col_sel, col_new, col_pub = st.columns([2,1,1])
with col_sel:
    vers_opc = [f"{r['id']} — {r['nombre']}  ({'vigente' if r['vigente_desde']!='—' and not r['vigente_hasta'] else 'no vigente'})"
                for _, r in df_vers.iterrows()]
    if not vers_opc:
        st.error("Sin versiones. Recarga la app para sembrar v1.")
        st.stop()
    sel = st.selectbox("Selecciona versión", vers_opc, index=0)
    current_vid = int(sel.split(" — ")[0])

with col_new:
    new_name = st.text_input("Nombre para clonar", value="v1.1")
    if st.button("Clonar versión"):
        try:
            vid_new = clone_version(conn, current_vid, new_name)
            st.success(f"Clonada como {new_name} (id {vid_new})")
            st.experimental_rerun()
        except sqlite3.IntegrityError as e:
            st.error(f"No se pudo clonar: {e}")

with col_pub:
    if st.button("Publicar como vigente"):
        publish_version(conn, current_vid)
        st.success("Versión publicada como vigente.")
        st.experimental_rerun()

st.divider()

# Edición de parámetros
params = read_params(conn, current_vid)

def num(name, value, step=0.01, minv=0.0, help_txt=None):
    return st.number_input(name, value=float(value), step=step, min_value=minv, help=help_txt)

st.subheader("Diésel")
c1, c2 = st.columns(2)
with c1: r_km_l = num("Rendimiento (km/L)", params["diesel"]["rendimiento_km_l"], 0.1, 0.1)
with c2: p_litro = num("Precio por litro ($/L)", params["diesel"]["precio_litro"], 0.1, 0.0)

st.subheader("DEF")
c1, c2 = st.columns(2)
with c1: pct_def = num("% DEF sobre litros", params["def"]["pct_def"], 0.001, 0.0)
with c2: p_def = num("Precio DEF ($/L)", params["def"]["precio_def_litro"], 0.1, 0.0)

st.subheader("Comisión TAG")
pct_tag = num("% comisión TAG sobre peajes", params["tag"]["pct_comision_tag"], 0.001, 0.0)

st.subheader("Costos por km")
c1, c2 = st.columns(2)
with c1: costo_ll = num("Llantas ($/km)", params["costos_km"]["costo_llantas_km"], 0.01, 0.0)
with c2: costo_mt = num("Mantenimiento ($/km)", params["costos_km"]["costo_mantto_km"], 0.01, 0.0)

st.subheader("Depreciación")
c1, c2, c3, c4 = st.columns(4)
with c1: costo_adq = num("Costo adquisición ($)", params["depreciacion"]["costo_adq"], 1000, 0)
with c2: val_res = num("Valor residual ($)", params["depreciacion"]["valor_residual"], 1000, 0)
with c3: vida = st.number_input("Vida (años)", value=int(params["depreciacion"]["vida_anios"]), min_value=1, step=1)
with c4: km_an = st.number_input("Km anuales", value=int(params["depreciacion"]["km_anuales"]), min_value=1, step=1000)

st.subheader("Seguros")
c1, c2 = st.columns(2)
with c1: prima = num("Prima anual ($)", params["seguros"]["prima_anual"], 100, 0)
with c2: km_seguros = st.number_input("Km anuales", value=int(params["seguros"]["km_anuales"]), min_value=1, step=1000)

st.subheader("Financiamiento")
c1, c2 = st.columns(2)
with c1: tasa = num("Tasa anual", params["financiamiento"]["tasa_anual"], 0.001, 0.0)
with c2: dias_cobro = st.number_input("Días de cobro", value=int(params["financiamiento"]["dias_cobro"]), min_value=1, step=1)

st.subheader("Overhead y Utilidad")
c1, c2 = st.columns(2)
with c1: pct_ov = num("% Overhead", params["overhead"]["pct_overhead"], 0.001, 0.0)
with c2: pct_ut = num("% Utilidad", params["utilidad"]["pct_utilidad"], 0.001, 0.0)

st.subheader("Otros")
c1, c2, c3 = st.columns(3)
with c1: viatico_dia = num("Viático por día ($)", params["otros"]["viatico_dia"], 10, 0)
with c2: permiso_viaje = num("Permiso por viaje ($)", params["otros"]["permiso_viaje"], 10, 0)
with c3: custodia_km = num("Custodia ($/km)", params["otros"]["custodia_km"], 0.01, 0)

st.subheader("Políticas (Base para financiamiento/overhead/utilidad)")
base_opts = ["peajes","diesel","llantas","mantto","depreciacion","seguros","viaticos","permisos","def","custodia","tag"]
sel_base = st.multiselect("Conceptos que integran la 'Base'", base_opts, default=params["politicas"]["incluye_en_base"])

if st.button("💾 Guardar cambios en esta versión", type="primary"):
    try:
        cur = conn.cursor()
        cur.execute("UPDATE param_diesel SET rendimiento_km_l=?, precio_litro=? WHERE version_id=?",
                    (r_km_l, p_litro, params["version_id"]))
        cur.execute("UPDATE param_def SET pct_def=?, precio_def_litro=? WHERE version_id=?",
                    (pct_def, p_def, params["version_id"]))
        cur.execute("UPDATE param_tag SET pct_comision_tag=? WHERE version_id=?",
                    (pct_tag, params["version_id"]))
        cur.execute("UPDATE param_costos_km SET costo_llantas_km=?, costo_mantto_km=? WHERE version_id=?",
                    (costo_ll, costo_mt, params["version_id"]))
        cur.execute("UPDATE param_depreciacion SET costo_adq=?, valor_residual=?, vida_anios=?, km_anuales=? WHERE version_id=?",
                    (costo_adq, val_res, int(vida), int(km_an), params["version_id"]))
        cur.execute("UPDATE param_seguros SET prima_anual=?, km_anuales=? WHERE version_id=?",
                    (prima, int(km_seguros), params["version_id"]))
        cur.execute("UPDATE param_financiamiento SET tasa_anual=?, dias_cobro=? WHERE version_id=?",
                    (tasa, int(dias_cobro), params["version_id"]))
        cur.execute("UPDATE param_overhead SET pct_overhead=? WHERE version_id=?",
                    (pct_ov, params["version_id"]))
        cur.execute("UPDATE param_utilidad SET pct_utilidad=? WHERE version_id=?",
                    (pct_ut, params["version_id"]))
        cur.execute("UPDATE param_otros SET viatico_dia=?, permiso_viaje=?, custodia_km=? WHERE version_id=?",
                    (viatico_dia, permiso_viaje, custodia_km, params["version_id"]))
        cur.execute("UPDATE param_politicas SET incluye_en_base=? WHERE version_id=?",
                    (json.dumps(sel_base), params["version_id"]))
        conn.commit()
        st.success("Cambios guardados.")
    except Exception as e:
        st.error(f"No se pudo guardar: {e}")
