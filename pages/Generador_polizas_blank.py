"""Placeholder page for Generador de pólizas cards."""

from __future__ import annotations

from urllib.parse import urlencode

import streamlit as st

from core.theme import apply_theme
from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import handle_logout_request, render_brand_logout_nav


st.set_page_config(
    page_title="Generador de pólizas | Próximamente",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
handle_logout_request()
ensure_session_from_token()


def _get_params() -> dict[str, str]:
    try:
        raw = st.query_params
    except Exception:
        raw = st.experimental_get_query_params()

    flattened: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(value, list):
            value = value[-1] if value else None
        if value is None:
            continue
        flattened[key] = str(value)
    return flattened


def _back_href() -> str:
    params = {"goto": "pages/generador_polizas.py"}
    params.update(auth_query_params())
    query = urlencode(params, doseq=False)
    return f"?{query}"


def _handle_pending_navigation() -> None:
    params = _get_params()
    goto = params.pop("goto", None)
    if not goto:
        return
    try:
        st.query_params.clear()
        if params:
            st.query_params.update(params)
    except Exception:
        st.experimental_set_query_params(**params)
    try:
        st.switch_page(goto)
    except Exception:
        st.stop()
    st.stop()


PAGE_CSS = """
<style>
#MainMenu, header[data-testid="stHeader"], footer, div[data-testid="stToolbar"], [data-testid="stSidebar"] {
  display:none !important;
}
.block-container {
  padding-top: 120px !important;
  max-width: 900px !important;
}
body, [data-testid="stAppViewContainer"] {
  background:#f5f6fb !important;
}
.placeholder-wrap {
  min-height: 50vh;
  display:flex;
  align-items:center;
  justify-content:center;
  color:#0f172a;
  font-size:1rem;
}
</style>
"""
st.markdown(PAGE_CSS, unsafe_allow_html=True)

_handle_pending_navigation()
params = _get_params()
origin = params.get("origin")

render_brand_logout_nav(
    "pages/generador_polizas.py",
    brand="Generador de pólizas",
    action_label="Atrás",
    action_href=_back_href(),
)

with st.container():
    st.markdown(
        f'<div class="placeholder-wrap">{origin or "Continuará..."}</div>',
        unsafe_allow_html=True,
    )
