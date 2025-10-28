"""Pagina de bienvenida al modulo de Riesgo Fiscal."""

from pathlib import Path
import streamlit as st

from core.auth import ensure_session_from_token
from core.db import get_conn, ensure_schema, validar_usuario
from core.auth import persist_login
from core.streamlit_compat import set_query_params
from core.navigation import render_nav
from pages.components.hero import first_image_base64, inject_hero_css

st.set_page_config(page_title="Riesgo Fiscal | Araiza Intelligence", layout="wide")

ensure_session_from_token()

# Gate: require login for Riesgo Fiscal (admin or operador)
ALLOWED_ROLES = {"admin", "operador"}

def _render_login() -> None:
    st.title("Riesgo Fiscal")
    st.subheader("Inicia sesion para continuar")
    with st.form("riesgo_login", clear_on_submit=False):
        username = st.text_input("Usuario", placeholder="ej. admin")
        password = st.text_input("Contrasena", type="password")
        submitted = st.form_submit_button("Iniciar sesion", use_container_width=True)
    if not submitted:
        st.stop()

    conn = get_conn()
    ensure_schema(conn)
    try:
        rol = validar_usuario(conn, username.strip(), password)
    except Exception:
        st.error("No fue posible validar las credenciales.")
        st.stop()
    if not rol or rol not in ALLOWED_ROLES:
        st.error("Usuario o contrasena incorrectos, o sin permiso para Riesgo Fiscal.")
        st.stop()
    token = persist_login(username.strip(), rol)
    try:
        current_qs = {k: v for k, v in st.query_params.items() if k != "auth"}
        current_qs["auth"] = token
        set_query_params(current_qs)
    except Exception:
        pass
    try:
        st.rerun()
    except Exception:
        pass

if not (st.session_state.get("usuario") and st.session_state.get("rol") in ALLOWED_ROLES):
    _render_login()

# Mark landing and render nav without Inicio link (label will be shown)

st.session_state["riesgo_show_landing"] = True
render_nav(active_top="riesgo", active_child=None, show_inicio=False)

inject_hero_css()

cover_candidates = [
    Path("assets/riesgo_cover.png"),
    Path(__file__).resolve().parent / "assets" / "riesgo_cover.png",
    Path("assets/riesgo_cover.jpg"),
    Path(__file__).resolve().parent / "assets" / "riesgo_cover.jpg",
    Path("assets/logo.jpg"),
    Path(__file__).resolve().parent / "assets" / "logo.jpg",
]
cover_src = first_image_base64(cover_candidates)

col_img, col_content = st.columns([5, 5])

with col_img:
    st.markdown('<div style="padding-top: 20px;">', unsafe_allow_html=True)
    if cover_src:
        st.markdown(
            f'<img class="hero-image" src="{cover_src}" alt="Riesgo fiscal" />',
            unsafe_allow_html=True,
        )
    else:
        st.warning(
            "No se encontro la imagen de portada para Riesgo Fiscal. Verifica la carpeta 'assets'."
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_content:
    st.markdown('<div style="padding-top: 20px;">', unsafe_allow_html=True)
    st.markdown(
        '<h1 class="hero-title">Verificaci&oacute;n fiscal inteligente</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <p class="hero-subtitle">
            Analiza archivos XML de CFDI, extrae los RFC relevantes y comp&aacute;ralos con la lista negra del SAT sin esfuerzo.
        </p>
        <p class="hero-subtitle">
            Identifica alertas de cumplimiento en segundos y genera reportes listos para compartir.
        </p>
        <ul class="hero-list">
            <li>Carga masiva de CFDI y extracci&oacute;n autom&aacute;tica de RFC.</li>
            <li>Cruces directos contra Firmes.csv del SAT.</li>
            <li>Tablas resumidas con coincidencias y detalle descargable.</li>
            <li>Exportaci&oacute;n inmediata a Excel para tu equipo.</li>
        </ul>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="hero-actions">', unsafe_allow_html=True)
    if st.button("Consultar lista negra", key="btn_consultar_riesgo"):
        st.switch_page("pages/15_Lista_negra_Sat.py")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
