"""Pantalla de bienvenida del módulo Descarga masiva de XML."""

from __future__ import annotations

import streamlit as st

from core.auth import ensure_session_from_token
from core.custom_nav import handle_logout_request, render_brand_logout_nav


st.set_page_config(
    page_title="Descarga masiva de XML | Inicio",
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
.welcome-page {
  min-height: calc(100vh - 40px);
  padding: 0;
  margin: 0;
}
.welcome-hero {
  background: linear-gradient(135deg, #0f172a, #1d4ed8);
  border-radius: 32px;
  padding: 48px;
  color: #fff;
  box-shadow: 0 25px 45px rgba(15,23,42,0.35);
  margin: 80px auto 32px;
}
.welcome-hero h1 {
  margin: 0 0 12px;
  font-size: clamp(2rem, 3vw, 2.6rem);
}
.welcome-hero p {
  margin: 0;
  font-size: 1.05rem;
  opacity: .9;
}
.welcome-actions .stButton button {
  width: 100%;
  height: 72px;
  border-radius: 18px;
  font-size: 1.1rem;
  font-weight: 700;
  border: none;
  box-shadow: 0 10px 25px rgba(15,23,42,0.18);
}
.welcome-actions .cfdi button {
  background: #0f172a;
  color: #fff;
}
.welcome-actions .nomina button {
  background: #f97316;
  color: #fff;
}
.welcome-actions .stButton button:hover {
  filter: brightness(.95);
}
.welcome-actions h3 {
  margin-top: 0;
}
</style>
<style>
[data-testid="stAppViewContainer"] > .main {
  padding-top: 0 !important;
}
section.main > div.block-container {
  padding: 0 !important;
}
</style>
""",
    unsafe_allow_html=True,
)


def _get_params() -> dict[str, str]:
    try:
        return dict(st.query_params)
    except Exception:
        params = st.experimental_get_query_params()
        return {k: (v[-1] if isinstance(v, list) and v else v) for k, v in params.items()}


def _set_next_param(target: str) -> None:
    params = _get_params()
    params["next"] = target
    try:
        st.query_params.update(params)
    except Exception:
        st.experimental_set_query_params(**params)


def _redirect_to_login() -> None:
    _set_next_param("pages/Descarga_masiva_inicio.py")
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

render_brand_logout_nav("pages/Descarga_masiva_inicio.py", brand="Descarga masiva")


with st.container():
    st.markdown('<div class="welcome-page">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="welcome-hero">
          <h1>Exporta tus CFDI de forma inteligente</h1>
          <p>Selecciona el flujo que deseas trabajar y te guiaremos paso a paso.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Accesos rápidos")
    col_cfdi, col_nomina = st.columns(2)

    with col_cfdi:
        st.write("Genera reportes en Excel a partir de tus archivos CFDI.")
        if st.button("Exportar CFDI", type="primary", use_container_width=True, key="btn_cfdi"):
            st.switch_page("pages/Descarga_masiva_xml.py")

    with col_nomina:
        st.write("Prepárate para exportar XML de nómina (muy pronto).")
        if st.button(
            "Exportar XML Nómina",
            use_container_width=True,
            key="btn_nomina",
        ):
            st.switch_page("pages/Descarga_masiva_nomina.py")

    st.markdown("</div>", unsafe_allow_html=True)
