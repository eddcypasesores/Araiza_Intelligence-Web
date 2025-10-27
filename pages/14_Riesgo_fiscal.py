"""Página de bienvenida al módulo de Riesgo Fiscal."""

from pathlib import Path
import base64
import streamlit as st

from core.auth import ensure_session_from_token
from core.db import get_conn, ensure_schema, validar_usuario
from core.auth import persist_login
from core.navigation import render_nav

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
    persist_login(username.strip(), rol)
    try:
        st.rerun()
    except Exception:
        pass

if not (st.session_state.get("usuario") and st.session_state.get("rol") in ALLOWED_ROLES):
    _render_login()

# Mark landing and render nav without Inicio link (label will be shown)
st.session_state["riesgo_show_landing"] = True
render_nav(active_top="riesgo", active_child=None, show_inicio=False)

ASSET_CANDIDATES = [
    # Prefer PNG assets for this module
    Path("assets/riesgo_cover.png"),
    Path(__file__).resolve().parent / "assets" / "riesgo_cover.png",
    # Fallbacks if a PNG is not present
    Path("assets/riesgo_cover.jpg"),
    Path(__file__).resolve().parent / "assets" / "riesgo_cover.jpg",
]


def _load_cover() -> str | None:
    for candidate in ASSET_CANDIDATES:
        if candidate.exists():
            data = candidate.read_bytes()
            mime = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
            return f"data:{mime};base64," + base64.b64encode(data).decode()
    return None


cover_src = _load_cover()

st.markdown(
    """
    <style>
      .module-hero {
        display: flex;
        flex-wrap: wrap;
        gap: clamp(28px, 5vw, 48px);
        align-items: center;
        margin-top: clamp(12px, 3vw, 24px);
      }
      .module-hero > div {
        flex: 1 1 360px;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: clamp(16px, 2vw, 24px);
      }
      .module-copy h1 {
        font-size: clamp(28px, 3.4vw, 40px);
        font-weight: 800;
        color: #0f172a;
        margin: 0;
      }
      .module-copy p {
        font-size: clamp(15px, 1.6vw, 18px);
        line-height: 1.55;
        color: #334155;
        margin: 0;
      }
      .module-copy ul {
        margin: 0 0 0 clamp(18px, 2vw, 24px);
        color: #0f172a;
        font-size: clamp(14px, 1.5vw, 17px);
      }
      .module-copy ul li {
        margin-bottom: clamp(2px, 1vw, 6px);
        line-height: 1.35;
      }
      .module-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: clamp(18px, 3vw, 28px);
      }
      .module-actions button[kind="primary"] {
        min-width: 220px;
      }
      .module-cover {
        align-items: stretch;
      }
      .module-cover img {
        width: 100%;
        border-radius: 18px;
        box-shadow: 0 20px 36px rgba(15, 23, 42, 0.18);
        object-fit: cover;
        max-height: 420px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="module-hero">', unsafe_allow_html=True)

st.markdown('<div class="module-copy">', unsafe_allow_html=True)
st.markdown('<h1>Verificación fiscal inteligente</h1>', unsafe_allow_html=True)
st.markdown(
    """
    <p>
      Nuestra aplicación analiza archivos XML de CFDI para extraer los RFC de los emisores y compararlos con la lista negra del SAT, garantizando control y cumplimiento fiscal.
    </p>
    <p>
      Con una interfaz clara e intuitiva, podrás revisar tus comprobantes, visualizar los RFC detectados y generar un Excel con las coincidencias en segundos.
    </p>
    <p><strong>Características principales:</strong></p>
    <ul>
      <li>Carga masiva de XML y extracción automática de RFC.</li>
      <li>Comparación directa con la lista negra SAT (Firmes.csv).</li>
      <li>Vista previa compacta y ordenada.</li>
      <li>Generación rápida de reportes en Excel.</li>
      <li>Interfaz moderna y fácil de usar.</li>
    </ul>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="module-actions">', unsafe_allow_html=True)
if st.button("Consultar lista negra", type="primary", key="btn_consultar_riesgo"):
    st.switch_page("pages/15_Lista_negra_SAT.py")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="module-cover">', unsafe_allow_html=True)
if cover_src:
    st.markdown(f"<img src='{cover_src}' alt='Riesgo fiscal' />", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
