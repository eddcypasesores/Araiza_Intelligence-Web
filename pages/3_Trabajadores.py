# pages/3_Trabajadores.py
import io
import pandas as pd
import streamlit as st
from core.db import get_conn, ensure_schema

st.set_page_config(page_title="Trabajadores (solo lectura)", layout="wide")

# ---------- Seguridad (solo admin) ----------
if "usuario" not in st.session_state or "rol" not in st.session_state:
    st.warning("⚠️ Debes iniciar sesión primero.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()
    st.stop()

if st.session_state["rol"] != "admin":
    st.error("🚫 Solo administradores pueden ver esta página.")
    st.stop()

# ---------- Conexión / esquema ----------
conn = get_conn()
ensure_schema(conn)
try:
    conn.execute("PRAGMA foreign_keys = ON")
except Exception:
    pass

st.title("👷 Trabajadores — Solo lectura")

# ---------- Consulta base ----------
BASE_SQL = """
SELECT
  t.id,
  t.nombre,
  t.numero_economico,
  t.salario_mensual,
  t.imss_pct,
  t.carga_social_pct,
  t.aguinaldo_dias,
  t.prima_vacacional_pct,
  t.horas_por_dia,
  t.dias_laborales_mes,
  u.username AS usuario_vinculado,
  u.rol      AS rol_usuario
FROM trabajadores t
LEFT JOIN usuario_trabajador ut ON ut.trabajador_id = t.id
LEFT JOIN usuarios u ON u.id = ut.usuario_id
ORDER BY t.nombre
"""
df = pd.read_sql_query(BASE_SQL, conn)
df.fillna({"usuario_vinculado": "", "rol_usuario": ""}, inplace=True)

# ---------- Filtros ----------
with st.expander("🔎 Filtros y búsqueda", expanded=True):
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])

    with c1:
        q = st.text_input("Buscar (nombre / No. económico / usuario)", placeholder="Ej. Juan, TR-001, jlopez").strip()

    with c2:
        vinc_ops = ["(Todos)", "Con usuario vinculado", "Sin usuario vinculado"]
        vinc_sel = st.selectbox("Vínculo", vinc_ops)

    with c3:
        rol_ops = ["(Todos)", "admin", "operador"]
        rol_sel = st.selectbox("Rol de usuario", rol_ops)

    with c4:
        # Suponiendo que df es el DataFrame que lees de 'trabajadores'
        # Si la tabla está vacía, creamos defaults seguros
        if df.empty:
            min_sal = 0.0
            max_sal = 50000.0
        else:
            min_sal = float(df["salario_mensual"].min() or 0.0)
            max_sal = float(df["salario_mensual"].max() or 0.0)
            # Garantiza min < max
            if max_sal <= min_sal:
                # si todos son 0 o iguales, abre un rango "usable"
                min_sal = 0.0
                max_sal = max(50000.0, (df["salario_mensual"].mean() or 0.0) + 10000.0)

        rango = st.slider(
            "Rango de salario mensual (MXN)",
            min_value=min_sal,
            max_value=max_sal,
            value=(min_sal, max_sal),
            step=100.0,
        )

# ---------- Aplicar filtros ----------
f = df.copy()

# Texto libre
if q:
    q_up = q.upper()
    f = f[
        f["nombre"].str.upper().str.contains(q_up, na=False)
        | f["numero_economico"].str.upper().str.contains(q_up, na=False)
        | f["usuario_vinculado"].str.upper().str.contains(q_up, na=False)
    ]

# Vínculo
if vinc_sel == "Con usuario vinculado":
    f = f[f["usuario_vinculado"].str.len() > 0]
elif vinc_sel == "Sin usuario vinculado":
    f = f[f["usuario_vinculado"].str.len() == 0]

# Rol
if rol_sel in ("admin", "operador"):
    f = f[f["rol_usuario"] == rol_sel]

# Rango salario
lo, hi = rango
f = f[(f["salario_mensual"] >= lo) & (f["salario_mensual"] <= hi)]

# ---------- Tabla ----------
st.subheader(f"Resultados: {len(f)} registro(s)")
st.dataframe(f, use_container_width=True, hide_index=True)

# ---------- Helper: exportar a Excel con openpyxl ----------
def df_to_excel_bytes(dataframe: pd.DataFrame) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Trabajadores")
    return out.getvalue()

# ---------- Exportación ----------
st.divider()
st.subheader("⬇️ Exportar")

modo = st.radio(
    "¿Qué deseas exportar?",
    ["Todos", "Solo lo filtrado (vista)", "Seleccionar por usuario"],
    horizontal=True,
)

df_todos = df.copy()
df_filtrado = f.copy()

seleccion_usuarios = []
if modo == "Seleccionar por usuario":
    usuarios_disponibles = sorted([u for u in df_todos["usuario_vinculado"].dropna().unique().tolist() if u])
    seleccion_usuarios = st.multiselect(
        "Elige usuarios vinculados para exportar",
        options=usuarios_disponibles,
        help="Solo se exportarán los trabajadores vinculados a estos usuarios.",
    )

# DataFrame final a exportar
if modo == "Todos":
    df_export = df_todos
elif modo == "Solo lo filtrado (vista)":
    df_export = df_filtrado
else:
    if seleccion_usuarios:
        df_export = df_todos[df_todos["usuario_vinculado"].isin(seleccion_usuarios)].copy()
    else:
        df_export = df_todos.iloc[0:0].copy()  # vacío si no se eligió nadie

col_l, col_r = st.columns([1, 3])
with col_l:
    if st.button("🔄 Recargar", use_container_width=True):
        st.experimental_rerun()

with col_r:
    excel_bytes = df_to_excel_bytes(df_export)
    nombre = (
        "trabajadores_todos.xlsx"
        if modo == "Todos"
        else "trabajadores_filtrados.xlsx"
        if modo == "Solo lo filtrado (vista)"
        else ("trabajadores_seleccion.xlsx" if not df_export.empty else "trabajadores_seleccion_vacio.xlsx")
    )
    st.download_button(
        "💾 Descargar Excel",
        data=excel_bytes,
        file_name=nombre,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        disabled=df_export.empty,
    )

st.caption("Tip: usa “Solo lo filtrado” para exportar exactamente lo que ves. Con “Seleccionar por usuario”, eliges usuarios específicos.")
