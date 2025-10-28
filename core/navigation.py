"""Reusable sticky navigation bar with dropdown actions for admin sections."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode

import streamlit as st

from .auth import auth_query_params
from .session import process_logout_flag
from .streamlit_compat import set_query_params


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
    background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
    border: 1px solid rgba(148, 163, 184, 0.28);
    padding: 0 clamp(16px, 4vw, 24px);
    height: var(--nav-height);
    display: flex;
    align-items: center;
    border-radius: 16px;
    box-shadow: 0 18px 32px rgba(15, 23, 42, 0.12);
  }

  .nav-inner {
    display: flex;
    align-items: center;
    width: 100%;
    gap: clamp(12px, 2.5vw, 32px);
  }

  .nav-brand {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    text-decoration: none;
    font-weight: 800;
    font-size: clamp(16px, 1.8vw, 20px);
    color: var(--nav-text);
    white-space: nowrap;
  }

  .nav-brand:hover {
    color: var(--nav-text-hover);
  }

  .nav-brand img {
    height: 34px;
    width: auto;
    display: block;
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
    font-weight: 600;
    font-size: clamp(15px, 1.7vw, 18px);
    padding: 10px 18px;
    white-space: nowrap;
    line-height: 20px;
    text-decoration: none;
    border-bottom: 2px solid transparent;
    transition: color .15s ease, border-color .15s ease;
  }

  .nav-scope.root-link.active .nav-link,
  .nav-scope.root-link .nav-link:hover {
    color: var(--nav-text-hover);
    border-color: rgba(37, 99, 235, 0.35);
  }

  .nav-scope.has-dropdown {
    align-items: stretch;
  }

  .nav-label {
    color: var(--nav-text);
    font-weight: 600;
    font-size: clamp(15px, 1.7vw, 18px);
    padding: 10px 18px;
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
    border-color: rgba(37, 99, 235, 0.35);
  }

  .nav-dropdown {
    display: none;
    position: absolute;
    top: calc(100% - 2px);
    left: 50%;
    transform: translateX(-50%);
    flex-direction: column;
    background: rgba(255, 255, 255, 0.98);
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 16px;
    padding: 12px 10px;
    box-shadow: 0 18px 32px rgba(15, 23, 42, 0.18);
    min-width: 230px;
    z-index: 1001;
    backdrop-filter: blur(10px);
    gap: 6px;
  }

  .nav-scope.has-dropdown:hover .nav-dropdown,
  .nav-scope.has-dropdown:focus-within .nav-dropdown {
    display: flex;
  }

  .nav-option {
    display: block;
    width: 100%;
    text-decoration: none;
    padding: 10px 16px;
    font-size: 15px;
    font-weight: 600;
    color: var(--nav-text);
    border-radius: 12px;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: linear-gradient(145deg, #f8fafc 0%, #eef2ff 100%);
    text-align: center;
    transition: all .18s ease;
  }

  .nav-option:hover {
    color: #1d4ed8;
    border-color: rgba(59, 130, 246, 0.55);
    box-shadow: 0 10px 18px rgba(59, 130, 246, 0.16);
  }

  .nav-option.active {
    color: #1d4ed8;
    border-color: rgba(59, 130, 246, 0.65);
    background: linear-gradient(145deg, #dbeafe 0%, #bfdbfe 100%);
    box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.45);
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
    padding: 10px 22px;
    border-radius: 999px;
    font-weight: 800;
    font-size: clamp(14px, 1.6vw, 17px);
    text-decoration: none;
    transition: background .15s ease, border-color .15s ease, transform .15s ease;
  }

  .nav-logout:hover {
    background: var(--brand-red-dark);
    border-color: var(--brand-red-dark);
    transform: translateY(-1px);
  }

  @media (max-width: 900px) {
    .nav-bar {
      border-radius: 12px;
      padding: 0 clamp(12px, 4vw, 16px);
    }

    .nav-main {
      gap: 12px;
    }

    .nav-label,
    .nav-scope.root-link .nav-link {
      font-size: 15px;
      padding: 8px 12px;
    }

    .nav-dropdown {
      min-width: 190px;
    }

    .block-container {
      padding: calc(var(--nav-height) + 20px) clamp(14px, 5vw, 24px) clamp(40px, 12vw, 60px) !important;
    }
  }
</style>
"""

_LOGO_CANDIDATES: tuple[Path, ...] = (
    Path("assets/logo_nav.png"),
    Path("assets/logo.png"),
    Path("assets/logo.jpg"),
    Path(__file__).resolve().parent.parent / "assets" / "logo_nav.png",
    Path(__file__).resolve().parent.parent / "assets" / "logo.png",
    Path(__file__).resolve().parent.parent / "assets" / "logo.jpg",
)


PAGE_PARAM_NAMES: dict[str, str] = {
    "pages/0_Inicio.py": "Inicio",
    "pages/1_Calculadora.py": "Calculadora",
    "pages/2_Tarifas_consultar.py": "Tarifas - Consultar",
    "pages/3_Tarifas_agregar.py": "Tarifas - Agregar",
    "pages/4_Tarifas_modificar.py": "Tarifas - Modificar",
    "pages/5_Tarifas_eliminar.py": "Tarifas - Eliminar",
    "pages/3_Trabajadores.py": "Trabajadores",
    "pages/6_Usuarios_consultar.py": "Usuarios - Consultar",
    "pages/7_Usuarios_agregar.py": "Usuarios - Agregar",
    "pages/8_Usuarios_modificar.py": "Usuarios - Modificar",
    "pages/9_Usuarios_eliminar.py": "Usuarios - Eliminar",
    "pages/10_Parametros_consultar.py": "Parametros - Consultar",
    "pages/11_Parametros_agregar.py": "Parametros - Agregar",
    "pages/12_Parametros_modificar.py": "Parametros - Modificar",
    "pages/13_Parametros_eliminar.py": "Parametros - Eliminar",
    "pages/14_Riesgo_fiscal.py": "Riesgo fiscal",
    "pages/15_Lista_negra_Sat.py": "Lista negra SAT - Cruce de RFC",
    "pages/16_Acerca_de_nosotros.py": "Acerca de Nosotros",
    "pages/17_Archivo_firmes.py": "Archivo Firmes",
}


@dataclass(frozen=True)
class DropdownAction:
    """Represents an action inside a dropdown menu."""

    label: str
    child_id: str
    target_page: str
    query: dict[str, str] | None = None


def _handle_logout_query() -> None:
    """Detect the logout flag in the query string and reset the session."""

    if not process_logout_flag():
        return

    try:
        st.switch_page("pages/0_Inicio.py")
    except Exception:
        st.rerun()
    st.stop()


def _page_href(page: str | None, extra: dict[str, str] | None = None) -> str:
    """Build a Streamlit multipage URL for the given page and query params."""

    query: dict[str, str] = {}
    if page:
        page_param = PAGE_PARAM_NAMES.get(page)
        if page_param is None:
            cleaned = (
                page.replace("pages/", "")
                .replace(".py", "")
                .replace("_", " ")
                .strip()
            )
            page_param = cleaned or page
        query["page"] = page_param
    if extra:
        query.update(extra)
    query.update(auth_query_params())
    if not query:
        return "/"
    return "/?" + urlencode(query, doseq=False)


@lru_cache(maxsize=1)
def _brand_logo_src() -> str | None:
    """Return a base64 data URI for the brand logo if available."""

    for candidate in _LOGO_CANDIDATES:
        if candidate and candidate.exists():
            data = candidate.read_bytes()
            mime = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
            return f"data:{mime};base64," + base64.b64encode(data).decode()
    return None


def _brand_html() -> str:
    """Return the HTML snippet for the brand link with logo."""

    logo_src = _brand_logo_src()
    if logo_src:
        img_html = f'<img src="{logo_src}" alt="Araiza Intelligence logo" />'
    else:
        img_html = ""
    return (
        f'<a class="nav-brand" href="{_page_href("pages/0_Inicio.py")}">'
        f"{img_html}<span class=\"nav-brand-text\">Araiza Intelligence</span></a>"
    )


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
        href = _page_href(action.target_page, action.query)
        option_class = "nav-option"
        if active_child == action.child_id and active_top == top_key:
            option_class += " active"
        items.append(
            f'<a class="{option_class}" href="{href}" target="_self">{action.label}</a>'
        )

    dropdown_class = "nav-scope has-dropdown"
    if active_top == top_key:
        dropdown_class += " active"

    return (
        f'<div class="{dropdown_class}">' \
        f'<div class="nav-label">{label}</div>' \
        f'<div class="nav-dropdown">{"".join(items)}</div>' \
        f"</div>"
    )


def _root_link_html(
    *,
    label: str,
    target_page: str,
    top_key: str,
    active_top: str | None,
) -> str:
    """Return the HTML for a root-level navigation link without dropdown."""

    root_class = "nav-scope root-link"
    if active_top == top_key:
        root_class += " active"

    return (
        f'<div class="{root_class}">' \
        f'<a class="nav-link" href="{_page_href(target_page)}" target="_self">{label}</a>' \
        "</div>"
    )


def _resolve_nav_mode(active_top: str | None) -> str:
    """Return the navigation layout mode based on the current context."""

    rol = str(st.session_state.get("rol", "")).lower()
    logged_in = bool(st.session_state.get("usuario"))

    if logged_in and active_top in {"riesgo", "riesgo_firmes"}:
        return "riesgo"
    if logged_in and rol in {"admin", "operador"} and active_top in {"calculadora", "tarifas", "usuarios", "parametros"}:
        return "calculadora"
    return "publico"


def _build_nav_items(
    *,
    mode: str,
    active_top: str | None,
    active_child: str | None,
) -> list[str]:
    """Build the list of navigation items for the requested mode."""

    rol = str(st.session_state.get("rol", "")).lower()

    if mode == "riesgo":
        return [
            _root_link_html(
                label="Lista negra SAT",
                target_page="pages/15_Lista_negra_Sat.py",
                top_key="riesgo",
                active_top=active_top,
            ),
            _root_link_html(
                label="Archivo Firmes",
                target_page="pages/17_Archivo_firmes.py",
                top_key="riesgo_firmes",
                active_top=active_top,
            ),
        ]

    if mode == "calculadora":
        items: list[str] = []
        if active_top in {"tarifas", "usuarios", "parametros"}:
            items.append(
                _root_link_html(
                    label="Calcular",
                    target_page="pages/1_Calculadora.py",
                    top_key="calculadora",
                    active_top=active_top,
                )
            )
        if rol == "admin":
            items.extend(
                [
                    _dropdown_html(
                        label="Tarifas",
                        actions=[
                            DropdownAction("Consultar", "consultar", "pages/2_Tarifas_consultar.py"),
                            DropdownAction("Agregar", "agregar", "pages/3_Tarifas_agregar.py"),
                            DropdownAction("Modificar", "modificar", "pages/4_Tarifas_modificar.py"),
                            DropdownAction("Eliminar", "eliminar", "pages/5_Tarifas_eliminar.py"),
                        ],
                        active_top=active_top,
                        active_child=active_child,
                        top_key="tarifas",
                    ),
                    _dropdown_html(
                        label="Usuarios",
                        actions=[
                            DropdownAction("Consultar", "consultar", "pages/6_Usuarios_consultar.py"),
                            DropdownAction("Agregar", "agregar", "pages/7_Usuarios_agregar.py"),
                            DropdownAction("Modificar", "modificar", "pages/8_Usuarios_modificar.py"),
                            DropdownAction("Eliminar", "eliminar", "pages/9_Usuarios_eliminar.py"),
                        ],
                        active_top=active_top,
                        active_child=active_child,
                        top_key="usuarios",
                    ),
                    _dropdown_html(
                        label="Parametros",
                        actions=[
                            DropdownAction("Consultar", "consultar", "pages/10_Parametros_consultar.py"),
                            DropdownAction("Agregar", "agregar", "pages/11_Parametros_agregar.py"),
                            DropdownAction("Modificar", "modificar", "pages/12_Parametros_modificar.py"),
                            DropdownAction("Eliminar", "eliminar", "pages/13_Parametros_eliminar.py"),
                        ],
                        active_top=active_top,
                        active_child=active_child,
                        top_key="parametros",
                    ),
                ]
            )
        else:
            if not items:
                items.append(
                    _root_link_html(
                        label="Calcular",
                        target_page="pages/1_Calculadora.py",
                        top_key="calculadora",
                        active_top=active_top,
                    )
                )
        return items

    # Default public layout
    active_key = active_top or "inicio"
    return [
        _root_link_html(
            label="Traslados",
            target_page="pages/1_Calculadora.py",
            top_key="calculadora",
            active_top=active_key,
        ),
        _root_link_html(
            label="Riesgo Fiscal",
            target_page="pages/14_Riesgo_fiscal.py",
            top_key="riesgo",
            active_top=active_key,
        ),
        _root_link_html(
            label="Acerca de Nosotros",
            target_page="pages/16_Acerca_de_nosotros.py",
            top_key="acerca",
            active_top=active_key,
        ),
    ]




def render_nav(
    active_top: str | None = None,
    active_child: str | None = None,
    *,
    show_inicio: bool = True,
    show_cta: bool = True,
) -> None:
    """Inject shared CSS and render the sticky navigation bar.

    Parameters
    ----------
    active_top, active_child
        Optional identifiers used to highlight the active dropdown and option.
    show_inicio
        If `True` the "Inicio" link is shown; disable it on the landing page to
        avoid duplicating the current location.
    show_cta
        Controls whether the trailing call-to-action (login / logout) button is
        rendered.  The home page keeps the navigation minimalist by hiding it.
    """

    _handle_logout_query()
    st.markdown(NAV_CSS, unsafe_allow_html=True)

    token = st.session_state.get("auth_token")
    if token:
        try:
            params = {k: v for k, v in st.query_params.items()}
            if params.get("auth") != token:
                params["auth"] = token
                set_query_params(params)
        except Exception:
            pass

    mode = _resolve_nav_mode(active_top)
    nav_items = _build_nav_items(
        mode=mode,
        active_top=active_top,
        active_child=active_child,
    )

    nav_html = "".join(nav_items)
    if not nav_html:
        nav_html = "&nbsp;"
    brand_html = _brand_html()

    if mode == "riesgo" and not st.session_state.get("usuario"):
        show_cta = False

    if show_cta:
        if st.session_state.get("usuario"):
            cta_href = "/?logout=1"
            cta_label = "Cerrar sesion"
        else:
            cta_href = _page_href("pages/1_Calculadora.py")
            cta_label = "Iniciar sesion"
        logout_html = (
            f'<div class="nav-scope logout"><a class="nav-logout" href="{cta_href}" '
            f'target="_self">{cta_label}</a></div>'
        )
    else:
        logout_html = ""

    markup = (
        '<div class="nav-anchor"></div>'
        '<nav class="nav-bar">'
        '<div class="nav-inner">'
        f'{brand_html}'
        f'<div class="nav-main">{nav_html}</div>'
        f"{logout_html}"
        '</div></nav>'
    )

    st.markdown(markup, unsafe_allow_html=True)
