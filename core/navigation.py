"""Reusable sticky navigation bar with dropdown actions for admin sections."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from .session import clear_session_state, process_logout_flag


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

  .nav-scope.root-link [data-testid="stPageLink"] {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    color: var(--nav-text) !important;
    font-weight: 500 !important;
    font-size: clamp(15px, 1.7vw, 18px) !important;
    padding: 8px 14px !important;
    white-space: nowrap !important;
    line-height: 20px !important;
    text-decoration: none !important;
    border-bottom: 2px solid transparent !important;
    transition: color .15s ease !important;
  }

  .nav-scope.root-link [data-testid="stPageLink"]:hover {
    color: var(--nav-text-hover) !important;
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
    background: rgba(255, 255, 255, 0.98);
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 12px;
    padding: 6px 0;
    box-shadow: 0 18px 32px rgba(15, 23, 42, 0.12);
    min-width: 210px;
    z-index: 1001;
    backdrop-filter: blur(10px);
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

  .nav-option.active button {
    color: var(--nav-text-hover) !important;
    font-weight: 600 !important;
  }

  .nav-option button {
    width: 100%;
    background: transparent !important;
    border: none !important;
    text-align: left !important;
    color: inherit !important;
    padding: 6px 0 !important;
  }

  .nav-option button:hover {
    color: var(--nav-text-hover) !important;
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

    if not process_logout_flag():
        return

    try:
        st.switch_page("app.py")
    except Exception:
        st.experimental_rerun()
    st.stop()


def _nav_dropdown(
    *,
    label: str,
    actions: list[DropdownAction],
    active_top: str | None,
    active_child: str | None,
    top_key: str,
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
        option_active = " active" if (active_child == action.view_value and active_top == top_key) else ""
        st.markdown(f'<div class="nav-option{option_active}">', unsafe_allow_html=True)
        if st.button(
            action.label,
            key=f"nav_{top_key}_{action.view_value}",
            use_container_width=True,
        ):
            st.session_state[action.view_key] = action.view_value
            try:
                st.switch_page(action.target_page)
            except Exception:
                st.experimental_rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)


def render_nav(
    active_top: str | None = None,
    active_child: str | None = None,
    *,
    show_inicio: bool = True,
) -> None:
    """Inject shared CSS and render the sticky navigation bar."""

    _handle_logout_query()
    st.markdown(NAV_CSS, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="nav-anchor"></div>', unsafe_allow_html=True)
        nav_cols = st.columns([1.0, 1.2, 1.2, 1.3, 1.0], gap="small")

        col_inicio, col_tarifas, col_usuarios, col_parametros, col_logout = nav_cols

        if show_inicio:
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
            )

        with col_logout:
            st.markdown('<div class="nav-scope logout">', unsafe_allow_html=True)
            if st.button("Salir", key="logout_btn_nav"):
                clear_session_state()
                try:
                    st.switch_page("app.py")
                except Exception:
                    st.experimental_rerun()
            st.markdown('</div>', unsafe_allow_html=True)