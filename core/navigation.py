"""Reusable sticky navigation bar with dropdown actions for admin sections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlencode

import streamlit as st


NAV_CSS = """
<style>
  :root {
    --nav-height: 58px;
    --nav-max-width: 1100px;
    --nav-text: #111827;
    --nav-text-hover: #4b5563;
    --brand-red: #dc2626;
    --brand-red-dark: #b91c1c;
  }

  [data-testid="stSidebar"],
  [data-testid="collapsedControl"],
  header[data-testid="stHeader"],
  div[data-testid="stToolbar"],
  #MainMenu {
    display: none !important;
  }

  [data-testid="stAppViewContainer"] > .main {
    padding-top: 0 !important;
  }

  .block-container {
    max-width: var(--nav-max-width) !important;
    margin: 0 auto !important;
    padding: calc(var(--nav-height) + 16px) clamp(16px, 4vw, 32px) clamp(48px, 8vw, 72px) !important;
  }

  .nav-anchor {
    display: block;
    height: var(--nav-height);
  }

  .nav-bar {
    position: fixed;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: min(100%, var(--nav-max-width));
    z-index: 1000;
    background: #fff;
    border-bottom: 1px solid #e5e7eb;
    padding: 0 clamp(16px, 4vw, 24px);
    height: var(--nav-height);
    display: flex;
    align-items: center;
  }

  .nav-inner {
    display: flex;
    align-items: center;
    width: 100%;
    gap: clamp(12px, 2.5vw, 32px);
  }

  .nav-main {
    display: flex;
    align-items: center;
    gap: clamp(14px, 2.6vw, 34px);
    flex: 1 1 auto;
  }

  .nav-scope {
    display: flex;
    align-items: center;
    position: relative;
  }

  .nav-scope.root-link .nav-link {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--nav-text);
    font-weight: 500;
    font-size: clamp(15px, 1.7vw, 18px);
    padding: 8px 14px;
    white-space: nowrap;
    line-height: 20px;
    text-decoration: none;
    border-bottom: 2px solid transparent;
    transition: color .15s ease;
  }

  .nav-scope.root-link.active .nav-link,
  .nav-scope.root-link .nav-link:hover {
    color: var(--nav-text-hover);
  }

  .nav-scope.has-dropdown {
    align-items: stretch;
  }

  .nav-label {
    color: var(--nav-text);
    font-weight: 500;
    font-size: clamp(15px, 1.7vw, 18px);
    padding: 8px 14px;
    white-space: nowrap;
    cursor: default;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border-bottom: 2px solid transparent;
    transition: color .15s ease;
  }

  .nav-scope.has-dropdown::after {
    content: "";
    position: absolute;
    top: calc(100% - 2px);
    left: 0;
    width: 100%;
    height: 12px;
    pointer-events: none;
  }

  .nav-scope.has-dropdown:hover .nav-label,
  .nav-scope.has-dropdown.active .nav-label {
    color: var(--nav-text-hover);
  }

  .nav-dropdown {
    display: none;
    position: absolute;
    top: calc(100% - 2px);
    left: 0;
    flex-direction: column;
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 6px 0;
    box-shadow: none;
    min-width: 210px;
    z-index: 1001;
  }

  .nav-scope.has-dropdown:hover .nav-dropdown {
    display: flex;
  }

  .nav-option {
    display: block;
    width: 100%;
    text-decoration: none;
    padding: 10px 18px;
    font-size: 15px;
    font-weight: 500;
    color: var(--nav-text);
    transition: color .15s ease;
  }

  .nav-option:hover,
  .nav-option.active {
    color: var(--nav-text-hover);
  }

  .nav-scope.logout {
    margin-left: auto;
  }

  .nav-logout {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--brand-red);
    color: #fff;
    border: 1px solid var(--brand-red);
    padding: 10px 20px;
    border-radius: 999px;
    font-weight: 800;
    font-size: clamp(14px, 1.6vw, 17px);
    text-decoration: none;
    transition: background .15s ease, border-color .15s ease;
  }

  .nav-logout:hover {
    background: var(--brand-red-dark);
    border-color: var(--brand-red-dark);
  }

  @media (max-width: 900px) {
    .nav-main {
      gap: 12px;
    }

    .nav-label {
      font-size: 15px;
      padding: 6px 10px;
    }

    .nav-dropdown {
      min-width: 180px;
    }

    .block-container {
      padding: calc(var(--nav-height) + 20px) clamp(14px, 5vw, 24px) clamp(40px, 12vw, 60px) !important;
    }
  }
</style>
"""


@dataclass(frozen=True)
class DropdownAction:
    """Represents an action inside a dropdown menu."""

    label: str
    view_key: str
    view_value: str
    target_page: str


def _handle_logout_query() -> None:
    """Detect the logout flag in the query string and reset the session."""

    params = st.query_params
    logout_value = params.get("logout")
    if isinstance(logout_value, list):
        logout_flag = logout_value[-1] if logout_value else "0"
    else:
        logout_flag = logout_value or "0"

    if logout_flag == "1":
        for key in (
            "usuario",
            "rol",
            "excluded_set",
            "route",
            "show_detail",
            "tarifas_view",
            "usuarios_view",
            "parametros_view",
        ):
            st.session_state.pop(key, None)

        try:
            params.clear()
        except Exception:
            pass

        try:
            st.switch_page("app.py")
        except Exception:
            st.experimental_rerun()
        st.stop()


def _page_href(page: str | None, extra: dict[str, str] | None = None) -> str:
    """Build a Streamlit multipage URL for the given page and query params."""

    query: dict[str, str] = {}
    if page:
        query["p"] = page
    if extra:
        query.update(extra)
    if not query:
        return "/"
    return "/?" + urlencode(query, doseq=False)


def _dropdown_html(
    *,
    label: str,
    actions: Iterable[DropdownAction],
    active_top: str | None,
    active_child: str | None,
    top_key: str,
) -> str:
    """Return the HTML for a dropdown menu inside the navbar."""

    items: list[str] = []
    for action in actions:
        href = _page_href(action.target_page, {action.view_key: action.view_value})
        option_class = "nav-option"
        if active_child == action.view_value and active_top == top_key:
            option_class += " active"
        items.append(
            f'<a class="{option_class}" href="{href}" target="_self">{action.label}</a>'
        )

    dropdown_class = "nav-scope has-dropdown"
    if active_top == top_key:
        dropdown_class += " active"

    return (
        f'<div class="{dropdown_class}">'
        f'<div class="nav-label">{label}</div>'
        f'<div class="nav-dropdown">{"".join(items)}</div>'
        f"</div>"
    )


def render_nav(
    active_top: str | None = None,
    active_child: str | None = None,
    *,
    show_inicio: bool = True,
) -> None:
    """Inject shared CSS and render the sticky navigation bar.

    Parameters
    ----------
    active_top, active_child
        Optional identifiers used to highlight the active dropdown and option.
    show_inicio
        If ``True`` the "Inicio" link is shown; disable it on the landing page to
        avoid duplicating the current location.
    """

    _handle_logout_query()
    st.markdown(NAV_CSS, unsafe_allow_html=True)

    nav_parts: list[str] = []
    if show_inicio:
        root_class = "nav-scope root-link"
        if active_top == "inicio":
            root_class += " active"
        nav_parts.append(
            f'<div class="{root_class}">'
            f'<a class="nav-link" href="{_page_href("pages/0_Inicio.py")}" target="_self">Inicio</a>'
            "</div>"
        )

    nav_parts.append(
        _dropdown_html(
            label="Tarifas",
            actions=[
                DropdownAction("Consultar", "tarifas_view", "consultar", "pages/2_Administrar_tarifas.py"),
                DropdownAction("Agregar", "tarifas_view", "agregar", "pages/2_Administrar_tarifas.py"),
                DropdownAction("Modificar", "tarifas_view", "modificar", "pages/2_Administrar_tarifas.py"),
                DropdownAction("Eliminar", "tarifas_view", "eliminar", "pages/2_Administrar_tarifas.py"),
            ],
            active_top=active_top,
            active_child=active_child,
            top_key="tarifas",
        )
    )

    nav_parts.append(
        _dropdown_html(
            label="Usuarios",
            actions=[
                DropdownAction("Consultar", "usuarios_view", "consultar", "pages/4_Usuarios.py"),
                DropdownAction("Agregar", "usuarios_view", "agregar", "pages/4_Usuarios.py"),
                DropdownAction("Modificar", "usuarios_view", "modificar", "pages/4_Usuarios.py"),
                DropdownAction("Eliminar", "usuarios_view", "eliminar", "pages/4_Usuarios.py"),
            ],
            active_top=active_top,
            active_child=active_child,
            top_key="usuarios",
        )
    )

    nav_parts.append(
        _dropdown_html(
            label="Parámetros",
            actions=[
                DropdownAction("Consultar", "parametros_view", "consultar", "pages/5_Parametros.py"),
                DropdownAction("Agregar", "parametros_view", "agregar", "pages/5_Parametros.py"),
                DropdownAction("Modificar", "parametros_view", "modificar", "pages/5_Parametros.py"),
                DropdownAction("Eliminar", "parametros_view", "eliminar", "pages/5_Parametros.py"),
            ],
            active_top=active_top,
            active_child=active_child,
            top_key="parametros",
        )
    )

    nav_html = "".join(nav_parts)
    logout_html = '<div class="nav-scope logout"><a class="nav-logout" href="/?logout=1" target="_self">Salir</a></div>'

    markup = (
        '<div class="nav-anchor"></div>'
        '<nav class="nav-bar">'
        '<div class="nav-inner">'
        f'<div class="nav-main">{nav_html}</div>'
        f"{logout_html}"
        "</div></nav>"
    )

    st.markdown(markup, unsafe_allow_html=True)
