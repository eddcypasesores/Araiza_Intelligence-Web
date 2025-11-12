"""Pantalla de bienvenida del módulo Descarga masiva de XML."""

from __future__ import annotations

import streamlit as st

from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import handle_logout_request, render_brand_logout_nav


st.set_page_config(
    page_title="Descarga masiva de XML | Inicio",
    # Mantenemos el layout "wide" para que el contenido use todo el ancho
    layout="wide",
    initial_sidebar_state="collapsed",
)
handle_logout_request("pages/0_Inicio.py")


PAGE_CSS = """
<style>
  html, body, .stApp {
    background:#f5f6fb !important;
    color:#0f172a !important;
  }
  #MainMenu, header, footer, div[data-testid="stToolbar"], section[data-testid="stSidebar"] {
    display:none !important;
  }
  .stAppViewContainer, .block-container {
    padding-top:5.5rem !important;
  }
  .block-container {
    max-width:1100px !important;
  }
  *:not(i) {
    color:#0f172a;
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


# --- INICIO DEL CONTENIDO SIMPLIFICADO ---
# Usamos contenedores y markdown para estructurar el contenido simple

# Eliminamos st.container() y las divs HTML
st.title("Exporta tus CFDI de forma inteligente") # Título principal
st.write("Selecciona el flujo que deseas trabajar y te guiaremos paso a paso.") # Párrafo introductorio

# Separador visual
st.divider()

st.subheader("Accesos rápidos")
col_cfdi, col_nomina = st.columns(2)

with col_cfdi:
    st.write("Genera reportes en Excel a partir de tus archivos CFDI.")
    # El botón ahora usa el estilo 'primary' por defecto de Streamlit (azul)
    if st.button("Exportar CFDI", type="primary", use_container_width=True, key="btn_cfdi"):
        st.switch_page("pages/Descarga_masiva_xml.py")

with col_nomina:
    st.write("Genera reportes en Excel a partir de tus archivos XML de nómina.")
    # El botón ahora usa el estilo por defecto de Streamlit (secundario/gris)
    if st.button(
        "Exportar XML Nómina",
        use_container_width=True,
        key="btn_nomina",
    ):
        st.switch_page("pages/Descarga_masiva_nomina.py")

# Fin del contenido simplificado
