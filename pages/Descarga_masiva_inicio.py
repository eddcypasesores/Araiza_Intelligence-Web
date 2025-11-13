"""Pantalla de bienvenida del módulo Descarga masiva de XML."""

from __future__ import annotations

import streamlit as st

from core.theme import apply_theme
from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import handle_logout_request, render_brand_logout_nav


st.set_page_config(
    page_title="Descarga masiva de XML | Inicio",
    # Mantenemos el layout "wide" para que el contenido use todo el ancho
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
handle_logout_request("pages/0_Inicio.py")


PAGE_CSS = """
<style>
.block-container {
  padding-top:5.5rem !important;
  max-width:1100px !important;
  color:var(--ai-page-text) !important;
}
.stApp *:not(svg):not(path) {
  color:inherit;
}
#MainMenu, header, footer, div[data-testid="stToolbar"], section[data-testid="stSidebar"] {
  display:none !important;
}
.landing-surface {
  background:var(--ai-surface-bg);
  color:var(--ai-surface-text);
  border-radius:32px;
  padding:40px 48px;
  box-shadow:var(--ai-card-shadow);
  border:1px solid var(--ai-border-color);
  backdrop-filter: blur(6px);
}
.landing-divider {
  border:none;
  border-top:1px solid var(--ai-border-color);
  margin:20px 0 30px;
}
.landing-actions {
  margin-top:20px;
}
.landing-actions .stButton {
  width:100%;
}
.landing-actions .stButton button {
  width:100%;
  border-radius:18px;
  font-weight:600;
  padding:16px 18px;
  border:1px solid transparent;
  background:var(--ai-accent);
  color:var(--ai-accent-contrast) !important;
  box-shadow:0 12px 25px rgba(0,0,0,0.12);
}
.landing-actions .stButton button:hover {
  filter:brightness(1.05);
}
.landing-description {
  color:var(--ai-muted-text);
}
</style>
"""
st.markdown(PAGE_CSS, unsafe_allow_html=True)

# --- Eliminamos el bloque st.markdown con todos los estilos CSS ---

def _get_params() -> dict[str, str]:
    try:
        raw_params = st.query_params
    except Exception:
        raw_params = st.experimental_get_query_params()

    normalized: dict[str, str] = {}
    for key, value in raw_params.items():
        if isinstance(value, list):
            value = value[-1] if value else None
        if value is None:
            continue
        normalized[key] = str(value)
    return normalized


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


def _ensure_auth_param() -> None:
    token_params = auth_query_params()
    if not token_params:
        return
    params = _get_params()
    if params.get("auth") == token_params.get("auth"):
        return
    params.update(token_params)
    try:
        st.query_params.update(params)
    except Exception:
        st.experimental_set_query_params(**params)


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

_ensure_auth_param()

# La barra de navegación se mantiene, ya que es funcional
render_brand_logout_nav("pages/Descarga_masiva_inicio.py", brand="Descarga masiva")


with st.container():
    st.markdown('<div class="landing-surface">', unsafe_allow_html=True)
    st.title("Exporta tus CFDI de forma inteligente")
    st.markdown(
        '<p class="landing-description">Selecciona el flujo que deseas trabajar y te guiaremos paso a paso.</p>',
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="landing-divider">', unsafe_allow_html=True)
    st.subheader("Accesos rápidos")
    st.markdown('<div class="landing-actions">', unsafe_allow_html=True)
    col_cfdi, col_nomina = st.columns(2, gap="large")

    with col_cfdi:
        st.write("Genera reportes en Excel a partir de tus archivos CFDI.")
        if st.button("Exportar CFDI", use_container_width=True, key="btn_cfdi"):
            st.switch_page("pages/Descarga_masiva_xml.py")

    with col_nomina:
        st.write("Genera reportes en Excel a partir de tus archivos XML de nómina.")
        if st.button(
            "Exportar XML Nómina",
            use_container_width=True,
            key="btn_nomina",
        ):
            st.switch_page("pages/Descarga_masiva_nomina.py")
    st.markdown("</div></div>", unsafe_allow_html=True)
