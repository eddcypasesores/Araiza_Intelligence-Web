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
:root {
  color-scheme: light dark;
  --nav-bg:var(--ai-surface-bg, #ffffff);
  --nav-text:var(--ai-page-text, #0f172a);
  --nav-muted:rgba(15,23,42,0.65);
  --nav-border:rgba(15,23,42,0.08);
  --nav-shadow:0 20px 45px rgba(15,23,42,0.16);
  --nav-btn-bg:#2563eb;
  --nav-btn-text:#f8fafc;
}
@media (prefers-color-scheme: dark) {
  :root {
    --nav-bg:var(--ai-surface-bg, #0f172a);
    --nav-text:var(--ai-page-text, #f8fafc);
    --nav-muted:rgba(248,250,252,0.75);
    --nav-border:rgba(15,23,42,0.45);
    --nav-shadow:0 25px 55px rgba(0,0,0,0.55);
    --nav-btn-bg:#3b82f6;
    --nav-btn-text:#f8fafc;
  }
}
.custom-nav{
  position:fixed;
  top:12px;
  left:50%;
  transform:translateX(-50%);
  width:min(1100px,100%);
  z-index:1000;
  background:var(--nav-bg);
  color:var(--nav-text);
  padding:12px 28px;
  border-radius:999px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:16px;
  box-shadow:var(--nav-shadow);
  border:1px solid var(--nav-border);
  backdrop-filter:blur(18px);
}
.nav-brand{
  display:flex;
  align-items:center;
  gap:14px;
}
.nav-brand img{
  height:30px;
  width:auto;
  display:block;
}
.nav-brand-text{
  display:flex;
  flex-direction:column;
  line-height:1.1;
  font-family:"Inter","Segoe UI",system-ui,-apple-system,sans-serif;
}
.nav-brand-text span{
  text-transform:none;
  letter-spacing:0;
}
.nav-brand-text .brand-parent{
  font-size:0.78rem;
  font-weight:600;
  color:var(--nav-muted);
}
.nav-brand-text .brand-product{
  font-size:1rem;
  font-weight:600;
  color:var(--nav-text);
}
.nav-actions a{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding:8px 22px;
  border-radius:999px;
  background:var(--nav-btn-bg);
  color:var(--nav-btn-text) !important;
  font-weight:600;
  letter-spacing:0.01em;
  text-decoration:none;
  box-shadow:0 10px 25px rgba(37,99,235,0.35);
  border:1px solid transparent;
  transition:filter 120ms ease, transform 120ms ease;
}
.nav-actions a:hover{
  filter:brightness(1.05);
  transform:translateY(-1px);
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


def _brand_markup(logo_src: str, product_label: str | None) -> str:
    company = "Araiza Intelligence"
    product = (product_label or "").strip()
    product_line = ""
    if product and product.lower() != company.lower():
        product_line = f'<span class="brand-product">{html.escape(product, quote=False)}</span>'
    return (
        '<div class="nav-brand">'
        f'<img src="{logo_src}" alt="Araiza Intelligence logo">'
        '<div class="nav-brand-text">'
        f'<span class="brand-parent">{company}</span>'
        f"{product_line}"
        "</div>"
        "</div>"
    )


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

    brand_block = _brand_markup(logo_src, brand)

    nav_html = (

        f'<div class="custom-nav">'

        f"{brand_block}"

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
