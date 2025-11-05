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
from .flash import consume_flash, set_flash
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
    Path("assets/Araiza Intelligence logo-04.jpg"),
    Path("assets/Araiza Intelligence logo-04.png"),
    Path("assets/logo_nav.png"),
    Path("assets/logo.png"),
    Path("assets/logo.jpg"),
    Path(__file__).resolve().parent.parent / "assets" / "Araiza Intelligence logo-04.jpg",
    Path(__file__).resolve().parent.parent / "assets" / "Araiza Intelligence logo-04.png",
    Path(__file__).resolve().parent.parent / "assets" / "logo_nav.png",
    Path(__file__).resolve().parent.parent / "assets" / "logo.png",
    Path(__file__).resolve().parent.parent / "assets" / "logo.jpg",
)

_ROOT_DIR = Path(__file__).resolve().parent.parent


def _script_exists(script: str | None) -> bool:
    """Return ``True`` if the target Streamlit script exists."""

    if not script:
        return False
    candidate = Path(script)
    if not candidate.is_absolute():
        candidate = _ROOT_DIR / script
    return candidate.is_file()


PAGE_PARAM_NAMES: dict[str, str] = {
    "pages/0_Inicio.py": "Inicio",
    "pages/1_Calculadora.py": "Calculadora",
    "pages/2_Tarifas_consultar.py": "Tarifas - Consultar",
    "pages/3_Tarifas_agregar.py": "Tarifas - Agregar",
    "pages/4_Tarifas_modificar.py": "Tarifas - Modificar",
    "pages/5_Tarifas_eliminar.py": "Tarifas - Eliminar",
    "pages/6_Usuarios_consultar.py": "Trabajadores - Consultar",
    "pages/7_Usuarios_agregar.py": "Trabajadores - Agregar",
    "pages/8_Usuarios_modificar.py": "Trabajadores - Modificar",
    "pages/9_Usuarios_eliminar.py": "Trabajadores - Eliminar",
    "pages/10_Parametros_consultar.py": "Parametros - Consultar",
    "pages/11_Parametros_agregar.py": "Parametros - Agregar",
    "pages/12_Parametros_modificar.py": "Parametros - Modificar",
    "pages/13_Parametros_eliminar.py": "Parametros - Eliminar",
    "pages/14_Riesgo_fiscal.py": "Monitoreo EFOS - Acceso",
    "pages/15_Lista_negra_Sat.py": "Monitoreo EFOS - Cruce de RFC",
    "pages/16_Acerca_de_nosotros.py": "Acerca de Nosotros",
    "pages/17_Archivo_firmes.py": "Monitoreo EFOS - Archivo Firmes",
    "pages/21_Archivo_exigibles.py": "Monitoreo EFOS - Archivo Exigibles",
    "pages/Riesgos_fiscales.py": "Riesgos fiscales",
    "pages/Cedula_Impuestos.py": "Cedula de impuestos - Acceso",
    "pages/Cedula_Impuestos_inicio.py": "Cedula de impuestos - Inicio",
    "pages/Cedula_Actualizacion_perdidas.py": "Cedula - Actualizacion y Amortizacion de perdidas",
    "pages/18_Restablecer_contrasena.py": "Recuperar contrasena",
    "pages/19_Admin_portal.py": "Administracion del portal",
    "pages/20_Admin_login.py": "Acceso super administrador",
    "pages/22_DIOT_excel_txt.py": "DIOT",
    "pages/23_DIOT_login.py": "DIOT - Acceso",
}


@dataclass(frozen=True)
class DropdownAction:
    """Represents an action inside a dropdown menu."""

    label: str
    child_id: str
    target_page: str
    query: dict[str, str] | None = None



LANDING_TOPS: set[str] = {"inicio", "acerca"}
TRASLADOS_TOPS: set[str] = {"calculadora", "trabajadores", "tarifas", "parametros"}
DIOT_TOPS: set[str] = {"diot", "tarifas", "trabajadores", "parametros"}
MONITOREO_TOPS: set[str] = {"monitoreo", "monitoreo_firmes", "monitoreo_exigibles"}
CEDULA_TOPS: set[str] = {"cedula"}

PRODUCT_ACTIONS: tuple[DropdownAction, ...] = (
    DropdownAction("Traslado Inteligente", "producto_traslados", "pages/1_Calculadora.py"),
    DropdownAction("DIOT", "producto_diot", "pages/22_DIOT_excel_txt.py"),
    DropdownAction("Monitoreo especializado de EFOS", "producto_monitoreo", "pages/14_Riesgo_fiscal.py"),
    DropdownAction("Cedula de impuestos", "producto_cedula", "pages/Cedula_Impuestos.py"),
    DropdownAction("Lista Negra SAT", "producto_lista", "pages/15_Lista_negra_Sat.py"),
    DropdownAction("Archivo Firmes", "producto_firmes", "pages/17_Archivo_firmes.py"),
    DropdownAction("Descarga masiva de XML", "producto_xml", "pages/14_Riesgo_fiscal.py"),
    DropdownAction("Generador de Polizas", "producto_polizas", "pages/XX_Generador_polizas.py"),
    DropdownAction("Convertidor de Estados de Cuenta", "producto_estados", "pages/XX_Convertidor_estados.py"),
)

ABOUT_ACTIONS: tuple[DropdownAction, ...] = (
    DropdownAction("Acerca de Nosotros", "acerca_resumen", "pages/16_Acerca_de_nosotros.py"),
    DropdownAction("Administrar", "acerca_admin", "pages/20_Admin_login.py"),
)

TARIFAS_ACTIONS: tuple[DropdownAction, ...] = (
    DropdownAction("Consultar", "tarifas_consultar", "pages/2_Tarifas_consultar.py"),
    DropdownAction("Agregar", "tarifas_agregar", "pages/3_Tarifas_agregar.py"),
    DropdownAction("Modificar", "tarifas_modificar", "pages/4_Tarifas_modificar.py"),
    DropdownAction("Eliminar", "tarifas_eliminar", "pages/5_Tarifas_eliminar.py"),
)

TRASLADOS_ACTIONS: tuple[DropdownAction, ...] = (
    DropdownAction("Consultar", "trabajadores_consultar", "pages/6_Usuarios_consultar.py"),
    DropdownAction("Agregar", "trabajadores_agregar", "pages/7_Usuarios_agregar.py"),
    DropdownAction("Modificar", "trabajadores_modificar", "pages/8_Usuarios_modificar.py"),
    DropdownAction("Eliminar", "trabajadores_eliminar", "pages/9_Usuarios_eliminar.py"),
)

PARAMETROS_ACTIONS: tuple[DropdownAction, ...] = (
    DropdownAction("Consultar", "parametros_consultar", "pages/10_Parametros_consultar.py"),
    DropdownAction("Agregar", "parametros_agregar", "pages/11_Parametros_agregar.py"),
    DropdownAction("Modificar", "parametros_modificar", "pages/12_Parametros_modificar.py"),
    DropdownAction("Eliminar", "parametros_eliminar", "pages/13_Parametros_eliminar.py"),
)

DIOT_ACTIONS: tuple[DropdownAction, ...] = (
    TARIFAS_ACTIONS
    + TRASLADOS_ACTIONS
    + PARAMETROS_ACTIONS
)


def _handle_logout_query() -> None:
    """Detect the logout flag in the query string and reset the session."""

    if not process_logout_flag():
        return

    set_flash("Sesion cerrada con exito")

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
        '<a class="nav-brand" href="/?logout=1" target="_self">'
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
        if action.target_page and not _script_exists(action.target_page):
            continue
        href = _page_href(action.target_page, action.query)
        option_class = "nav-option"
        if active_child == action.child_id and active_top == top_key:
            option_class += " active"
        items.append(
            f'<a class="{option_class}" href="{href}" target="_self">{action.label}</a>'
        )

    if not items:
        return ""

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
    extra: dict[str, str] | None = None,
) -> str:
    """Return the HTML for a root-level navigation link without dropdown."""

    root_class = "nav-scope root-link"
    if active_top == top_key:
        root_class += " active"

    return (
        f'<div class="{root_class}">' \
        f'<a class="nav-link" href="{_page_href(target_page, extra)}" target="_self">{label}</a>' \
        "</div>"
    )


def _resolve_nav_mode(active_top: str | None) -> str:
    """Return the navigation layout mode based on the current context."""

    if active_top in LANDING_TOPS:
        return "landing"
    if active_top in TRASLADOS_TOPS:
        return "traslados"
    if active_top in DIOT_TOPS:
        return "diot"
    if active_top in MONITOREO_TOPS:
        return "monitoreo"
    if active_top in CEDULA_TOPS:
        return "cedula"
    if active_top == "admin_portal":
        return "portal_admin"

    logged_in = bool(st.session_state.get("usuario"))
    permisos = set(st.session_state.get("permisos") or [])

    if logged_in and "diot" in permisos:
        return "diot"
    if logged_in and "traslados" in permisos:
        return "traslados"
    if logged_in and "riesgos" in permisos:
        return "monitoreo"
    if logged_in and "cedula" in permisos:
        return "cedula"
    if logged_in and "admin" in permisos:
        return "portal_admin"
    return "publico"


def _build_nav_items(
    *,
    mode: str,
    active_top: str | None,
    active_child: str | None,
) -> list[str]:
    """Build the list of navigation items for the requested mode."""

    if mode == "landing":
        return [
            _dropdown_html(
                label="Productos",
                actions=PRODUCT_ACTIONS,
                active_top=active_top,
                active_child=active_child,
                top_key="productos",
            ),
            _dropdown_html(
                label="Acerca de Nosotros",
                actions=ABOUT_ACTIONS,
                active_top=active_top,
                active_child=active_child,
                top_key="acerca",
            ),
        ]

    if mode == "traslados":
        current_child: str | None = None
        if active_top in {"trabajadores", "tarifas", "parametros"}:
            current_child = (
                f"{active_top}_{active_child}"
                if active_child
                else f"{active_top}_consultar"
            )

        items: list[str] = [
            _root_link_html(
                label="Calculadora",
                target_page="pages/1_Calculadora.py",
                top_key="calculadora",
                active_top=active_top,
            ),
            _dropdown_html(
                label="Trabajadores",
                actions=TRASLADOS_ACTIONS,
                active_top=active_top,
                active_child=current_child,
                top_key="trabajadores",
            ),
            _dropdown_html(
                label="Tarifas",
                actions=TARIFAS_ACTIONS,
                active_top=active_top,
                active_child=current_child,
                top_key="tarifas",
            ),
            _dropdown_html(
                label="Parametros",
                actions=PARAMETROS_ACTIONS,
                active_top=active_top,
                active_child=current_child,
                top_key="parametros",
            ),
        ]
        items.append(
            _root_link_html(
                label="Cerrar sesion",
                target_page="pages/0_Inicio.py",
                top_key="logout",
                active_top=active_top,
                extra={"logout": "1"},
            )
        )
        return items

    if mode == "monitoreo":
        return [
            _root_link_html(
                label="Monitoreo EFOS",
                target_page="pages/15_Lista_negra_Sat.py",
                top_key="monitoreo",
                active_top=active_top,
            ),
            _root_link_html(
                label="Archivo Firmes",
                target_page="pages/17_Archivo_firmes.py",
                top_key="monitoreo_firmes",
                active_top=active_top,
            ),
            _root_link_html(
                label="Archivo Exigibles",
                target_page="pages/21_Archivo_exigibles.py",
                top_key="monitoreo_exigibles",
                active_top=active_top,
            ),
            _root_link_html(
                label="Cerrar sesion",
                target_page="pages/14_Riesgo_fiscal.py",
                top_key="logout",
                active_top=active_top,
                extra={"logout": "1"},
            ),
        ]

    if mode == "cedula":
        return [
            _root_link_html(
                label="Cédula de impuestos",
                target_page="pages/Cedula_Impuestos_inicio.py",
                top_key="cedula",
                active_top=active_top,
            ),
            _root_link_html(
                label="Cerrar sesion",
                target_page="pages/Cedula_Impuestos.py",
                top_key="logout",
                active_top=active_top,
                extra={"logout": "1"},
            ),
        ]

    if mode == "portal_admin":
        return [
            _root_link_html(
                label="Administracion",
                target_page="pages/19_Admin_portal.py",
                top_key="admin_portal",
                active_top=active_top,
            ),
            _root_link_html(
                label="Cerrar sesion",
                target_page="pages/0_Inicio.py",
                top_key="logout",
                active_top=active_top,
                extra={"logout": "1"},
            ),
        ]

    return []




def render_nav(
    active_top: str | None = None,
    active_child: str | None = None,
    *,
    show_inicio: bool = True,
    show_cta: bool = False,
) -> None:
    """Inject shared CSS and render the sticky navigation bar.

    Parameters
    ----------
    active_top, active_child
        Optional identifiers used to highlight the active dropdown and option.
    show_inicio
        Conservado por compatibilidad. Actualmente no agrega enlaces de inicio.
    show_cta
        Parametro en desuso; se ignora. El parametro se mantiene por compatibilidad.
    """

    _handle_logout_query()
    st.markdown(NAV_CSS, unsafe_allow_html=True)
    consume_flash()

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
