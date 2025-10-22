# pages/0_Inicio.py — Inicio limpio sin sidebar
import streamlit as st
from core.db import get_conn, ensure_schema

st.set_page_config(page_title="Inicio | Costos de Rutas", layout="wide")

# ===== Seguridad =====
if "usuario" not in st.session_state or "rol" not in st.session_state:
    st.warning("⚠️ Debes iniciar sesión primero.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()
    st.stop()

# ===== Ocultar SOLO en esta página la barra lateral y el botón de colapsar =====
st.markdown(
    """
    <style>
      [data-testid="stSidebar"] { display: none !important; }
      [data-testid="collapsedControl"] { display: none !important; }
      .block-container { padding-top: 3.5rem !important; }
      .inicio-hero { font-size: 2rem; font-weight: 800; letter-spacing: .3px; margin-bottom: .75rem; }
      .inicio-grid { display: grid; grid-template-columns: repeat(4, minmax(180px, 1fr)); gap: 16px; }
      @media (max-width: 900px) { .inicio-grid { grid-template-columns: repeat(2, 1fr); } }
      @media (max-width: 520px) { .inicio-grid { grid-template-columns: 1fr; } }
      .sep { margin-top: 18px; margin-bottom: 6px; }
    </style>
    """,
    unsafe_allow_html=True
)

# ===== Conexión / nombre + apellido paterno del usuario logueado =====
conn = get_conn()
ensure_schema(conn)

usuario = st.session_state["usuario"]

# Intentar resolver Nombre + Apellido Paterno a partir del vínculo usuario_trabajador
try:
    row = conn.execute(
        """
        SELECT t.nombres, t.apellido_paterno
        FROM usuarios u
        JOIN usuario_trabajador ut ON ut.usuario_id = u.id
        JOIN trabajadores t        ON t.id = ut.trabajador_id
        WHERE u.username = ?
        """,
        (usuario,)
    ).fetchone()
except Exception:
    row = None

if row and (row[0] or row[1]):
    nombre_vista = f"{(row[0] or '').strip()} {(row[1] or '').strip()}".strip()
else:
    # Fallback: usar el username si no hay trabajador vinculado
    nombre_vista = usuario

# ===== Encabezado =====
st.markdown(f"<div class='inicio-hero'>Hola, {nombre_vista}</div>", unsafe_allow_html=True)

# ===== Botones principales =====
# Nota: mostramos siempre los 4. Las páginas de destino ya controlan permisos.
st.markdown("<div class='sep'></div>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    if st.button("🧮 Calculadora", use_container_width=True):
        st.switch_page("pages/1_Calculadora.py")

with c2:
    if st.button("🏷️ Tarifas caseta", use_container_width=True):
        st.switch_page("pages/2_Administrar_tarifas.py")

with c3:
    if st.button("👥 Usuarios", use_container_width=True):
        st.switch_page("pages/4_Usuarios.py")

with c4:
    if st.button("⚙️ Parámetros", use_container_width=True):
        # Si tu módulo de parámetros está en otra ruta, ajusta este string.
        st.switch_page("pages/5_Parametros.py")

# ===== Botón “Cerrar sesión” separado =====
st.markdown("<div class='sep'></div>", unsafe_allow_html=True)
if st.button("🔓 Cerrar sesión", type="secondary"):
    for k in ("usuario", "rol", "excluded_set", "route", "show_detail"):
        if k in st.session_state:
            del st.session_state[k]
    try:
        st.switch_page("app.py")
    except Exception:
        st.experimental_rerun()
