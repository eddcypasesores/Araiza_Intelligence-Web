"""Placeholder para la exportación de XML de nómina."""

from __future__ import annotations

import streamlit as st

from core.auth import ensure_session_from_token
from core.custom_nav import handle_logout_request, render_brand_logout_nav


st.set_page_config(
    page_title="Descarga masiva | XML Nómina",
    layout="wide",
    initial_sidebar_state="collapsed",
)
handle_logout_request()

st.markdown(
    """
<style>
#MainMenu, header[data-testid="stHeader"], footer, div[data-testid="stToolbar"] {
  visibility: hidden !important;
  display: none !important;
}
.nomina-wrapper {
  min-height: 100vh;
  padding-top: 110px;
}
.nomina-card {
  background: #fff;
  border-radius: 28px;
  padding: 48px;
  border: 1px solid rgba(15,23,42,0.07);
  box-shadow: 0 18px 35px rgba(15,23,42,0.15);
}
</style>
""",
    unsafe_allow_html=True,
)


def _redirect_to_login() -> None:
    try:
        st.query_params.update({"next": "pages/Descarga_masiva_nomina.py"})
    except Exception:
        st.experimental_set_query_params(next="pages/Descarga_masiva_nomina.py")
    try:
        st.switch_page("pages/Descarga_masiva_login.py")
    except Exception:
        st.stop()


ensure_session_from_token()
usuario = st.session_state.get("usuario")
permisos = set(st.session_state.get("permisos") or [])

if not usuario:
    _redirect_to_login()
    st.stop()

if "descarga_masiva" not in permisos and "admin" not in permisos:
    st.error("No tienes permiso para acceder a este módulo.")
    _redirect_to_login()
    st.stop()

render_brand_logout_nav("pages/Descarga_masiva_nomina.py", brand="Descarga masiva")

st.markdown('<div class="nomina-wrapper"><div class="nomina-card">', unsafe_allow_html=True)
st.title("Exportar XML Nómina")
st.caption("Estamos preparando esta herramienta para ayudarte a transformar y analizar tus nóminas.")
st.info("Esta pantalla está en construcción. Te avisaremos cuando esté lista.")

if st.button("Volver al inicio de Descarga masiva", use_container_width=True):
    st.switch_page("pages/Descarga_masiva_inicio.py")

st.markdown("</div></div>", unsafe_allow_html=True)
