"""Reusable sticky navigation bar with dropdown actions for admin sections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import streamlit as st


NAV_CSS = """
<style>
  :root {
    --nav-height: 58px;
    --nav-max-width: 1100px;
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

  .nav-anchor + div[data-testid="stHorizontalBlock"] {
    position: fixed;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: min(100%, var(--nav-max-width));
    z-index: 1000;
    background: #fff;
    border-bottom: 1px solid #e5e7eb;
    display: flex !important;
    align-items: center;
    gap: clamp(12px, 2.5vw, 32px);
    padding: 0 clamp(16px, 4vw, 24px) !important;
    height: var(--nav-height);
  }

  .nav-anchor + div[data-testid="stHorizontalBlock"] > div {
    padding: 0 !important;
    margin: 0 !important;
    flex: 0 0 auto !important;
    width: auto !important;
  }

  .nav-anchor + div[data-testid="stHorizontalBlock"] > div:last-child {
    margin-left: auto !important;
  }

  .nav-scope {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    position: relative;
  }

  .nav-scope.root-link [data-testid="stPageLink"] {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    color: var(--brand-red) !important;
    font-weight: 700;
    font-size: clamp(15px, 1.7vw, 18px);
    padding: 8px 14px !important;
    white-space: nowrap !important;
    line-height: 20px !important;
    text-decoration: none !important;
  }

  .nav-scope.root-link [data-testid="stPageLink"]:hover {
    color: var(--brand-red-dark) !important;
    text-decoration: underline !important;
  }

  .nav-scope.has-dropdown {
    align-items: center;
  }

  .nav-label {
    color: var(--brand-red);
    font-weight: 700;
    font-size: clamp(15px, 1.7vw, 18px);
    padding: 8px 14px;
    cursor: default;
    white-space: nowrap;
  }

  .nav-scope.has-dropdown:hover .nav-dropdown {
    display: flex;
  }

  .nav-dropdown {
    display: none;
    position: absolute;
    top: calc(100% - 2px);
    left: 0;
    flex-direction: column;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 6px 0;
    box-shadow: 0 16px 30px rgba(15, 23, 42, 0.12);
    min-width: 210px;
  }

  .nav-option {
    width: 100%;
  }

  .nav-option button {
    background: transparent !important;
    border: none !important;
    width: 100%;
    text-align: left;
    padding: 10px 18px;
    font-size: 15px;
    font-weight: 500;
    color: #1f2937;
    border-radius: 0 !important;
    box-shadow: none !important;
  }

  .nav-option button:hover {
    background: #f3f4f6 !important;
    color: var(--brand-red) !important;
  }

  .nav-option.active button {
    color: var(--brand-red) !important;
    font-weight: 700 !important;
  }

  .nav-scope.logout button {
    background: var(--brand-red) !important;
    color: #fff !important;
    border: 1px solid var(--brand-red) !important;
    padding: 10px 20px !important;
    border-radius: 999px !important;
    font-weight: 800 !important;
    font-size: clamp(14px, 1.6vw, 17px) !important;
  }

  .nav-scope.logout button:hover {
    background: var(--brand-red-dark) !important;
    border-color: var(--brand-red-dark) !important;
  }

  @media (max-width: 900px) {
    .nav-anchor + div[data-testid="stHorizontalBlock"] {
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


def _nav_dropdown(
    *,
    label: str,
    actions: Iterable[DropdownAction],
    active_top: str | None,
    active_child: str | None,
    top_key: str,
    key_prefix: str,
) -> None:
    """Render a dropdown menu inside the navbar."""

    active_class = " active" if active_top == top_key else ""
    st.markdown(
        f'<div class="nav-scope has-dropdown{active_class}">',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="nav-label">{label}</div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-dropdown">', unsafe_allow_html=True)

    for action in actions:
        option_active = " active" if active_child == action.view_value else ""
        st.markdown(
            f'<div class="nav-option{option_active}">',
            unsafe_allow_html=True,
        )
        if st.button(
            action.label,
            key=f"nav_{key_prefix}_{action.view_value}",
            use_container_width=True,
        ):
            st.session_state[action.view_key] = action.view_value
            try:
                st.switch_page(action.target_page)
            except Exception:
                st.experimental_rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)


def render_nav(active_top: str | None = None, active_child: str | None = None) -> None:
    """Inject shared CSS and render the sticky navigation bar."""

    st.markdown(NAV_CSS, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="nav-anchor"></div>', unsafe_allow_html=True)

        col_inicio, col_tarifas, col_usuarios, col_parametros, col_logout = st.columns(
            [1.0, 1.2, 1.2, 1.3, 1.0],
            gap="small",
        )

        with col_inicio:
            st.markdown('<div class="nav-scope root-link">', unsafe_allow_html=True)
            st.page_link("pages/0_Inicio.py", label="Inicio")
            st.markdown('</div>', unsafe_allow_html=True)

        with col_tarifas:
            _nav_dropdown(
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
                key_prefix="tarifas",
            )

        with col_usuarios:
            _nav_dropdown(
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
                key_prefix="usuarios",
            )

        with col_parametros:
            _nav_dropdown(
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
                key_prefix="parametros",
            )

        with col_logout:
            st.markdown('<div class="nav-scope logout">', unsafe_allow_html=True)
            if st.button("Salir", key="logout_btn_nav"):
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
                    if key in st.session_state:
                        del st.session_state[key]
                try:
                    st.switch_page("app.py")
                except Exception:
                    st.experimental_rerun()
            st.markdown('</div>', unsafe_allow_html=True)
