"""Reusable custom navigation bar with brand logo and logout button."""

from __future__ import annotations

import base64
import html
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st

from .auth import forget_session
from .session import process_logout_flag

NAV_LOGO_CANDIDATES: tuple[Path, ...] = (
    Path("assets/logo_nav.png"),
    Path("assets/Araiza Intelligence logo-04.png"),
    Path("assets/Araiza Intelligence logo-04.jpg"),
    Path("assets/logo.png"),
    Path("assets/logo.jpg"),
)

DEFAULT_NAV_LOGO = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAE/wJ/lAqvVwAAAABJRU5ErkJggg=="

_NAV_CSS = """
<style>
.custom-nav{
  position:fixed;
  top:0;
  left:50%;
  transform:translateX(-50%);
  width:min(1100px,100%);
  z-index:1000;
  background:#ffffff;
  color:#0f172a;
  padding:10px 22px;
  border-radius:999px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:16px;
  box-shadow:0 18px 32px rgba(15,23,42,0.18);
  border:1px solid rgba(148,163,184,0.25);
}
.nav-brand{
  display:inline-flex;
  align-items:center;
  gap:10px;
  font-weight:700;
  font-size:1rem;
  text-transform:uppercase;
  letter-spacing:0.05em;
}
.nav-brand img{
  height:28px;
  width:auto;
  display:block;
}
.nav-actions a{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding:6px 20px;
  border-radius:999px;
  background:#0d3c74;
  color:#fff !important;
  font-weight:600;
  text-decoration:none;
  box-shadow:0 6px 16px rgba(13,60,116,0.25);
}
</style>
"""


def _navbar_logo_data() -> str:
    for candidate in NAV_LOGO_CANDIDATES:
        if candidate.exists():
            try:
                encoded = base64.b64encode(candidate.read_bytes()).decode()
                return f"data:image/png;base64,{encoded}"
            except Exception:
                continue
    return DEFAULT_NAV_LOGO


def _logout_href(page_param: str) -> str:
    params: dict[str, str] = {}
    for key, value in st.query_params.items():
        if key in {"goto", "logout"}:
            continue
        if isinstance(value, list):
            value = value[-1] if value else None
        if isinstance(value, str) and value:
            params[key] = value
    if page_param:
        params.setdefault("page", page_param)
    params["logout"] = "1"
    query = urlencode(params, doseq=False)
    return f"?{query}"


def render_brand_logout_nav(
    page_param: str,
    *,
    brand: str = "Araiza Intelligence",
    action_label: str | None = None,
    action_href: str | None = None,
) -> None:
    """Render the fixed navigation pill with brand logo and a configurable action button."""

    # Reinyecta el CSS en cada renderizado para evitar que se pierda tras un rerun.
    st.markdown(_NAV_CSS, unsafe_allow_html=True)

    logo_src = _navbar_logo_data()
    if action_href:
        action_url = html.escape(action_href, quote=True)
    else:
        action_url = html.escape(_logout_href(page_param), quote=True)
    button_label = html.escape(action_label or "Cerrar sesión", quote=False)
    nav_html = (
        f'<div class="custom-nav">'
        f'<div class="nav-brand"><img src="{logo_src}" alt="Araiza logo"><span>{brand}</span></div>'
        f'<div class="nav-actions"><a href="{action_url}" target="_self">{button_label}</a></div>'
        f'</div>'
    )
    st.markdown(nav_html, unsafe_allow_html=True)


def handle_logout_request(redirect_page: str = "pages/0_Inicio.py") -> None:
    """Process the logout query flag and redirect to the provided page."""

    if process_logout_flag():
        forget_session()
        try:
            st.switch_page(redirect_page)
        except Exception:
            st.stop()
        st.stop()
