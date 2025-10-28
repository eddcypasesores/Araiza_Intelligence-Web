"""Utilidades compartidas para secciones de administracion."""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path
from typing import Optional

import streamlit as st

from core.auth import ensure_session_from_token
from core.db import ensure_schema, get_conn
from core.navigation import render_nav


def _redirect_to_login(target_page: str | None = None, switch_to_page: str = "pages/1_Calculadora.py") -> None:
    """Redirige al login en caso de que la sesion no sea valida."""

    st.warning(" Debes iniciar sesion primero.")
    params = {k: v for k, v in st.query_params.items() if k not in {"logout", "next"}}
    if target_page:
        params["next"] = target_page
    try:
        st.experimental_set_query_params(**params)
    except Exception:
        pass
    try:
        st.switch_page(switch_to_page)
    except Exception:
        st.stop()
    st.stop()


def _ensure_admin_session(redirect_to: str | None = None) -> None:
    """Valida que exista una sesion activa con privilegios de administrador."""

    ensure_session_from_token()

    if "usuario" not in st.session_state or "rol" not in st.session_state:
        _redirect_to_login(redirect_to)

    if str(st.session_state.get("rol", "")).lower() != "admin":
        st.error(" No tienes permiso para acceder a esta pagina.")
        st.stop()


def _configure_page(page_title: str, layout: str) -> None:
    """Configura la pagina solo una vez por ejecucion."""

    if not st.session_state.get("_admin_page_configured"):
        st.set_page_config(page_title=page_title, layout=layout)
        st.session_state["_admin_page_configured"] = True


def init_admin_section(
    *,
    page_title: str,
    active_top: Optional[str] = None,
    active_child: Optional[str] = None,
    layout: str = "wide",
    show_inicio: bool = False,
    enable_foreign_keys: bool = True,
) -> sqlite3.Connection:
    """Inicializa el entorno de una pagina administrativa y devuelve la conexion.

    Parametros
    ----------
    page_title:
        Titulo a mostrar en la pestana del navegador.
    active_top, active_child:
        Identificadores usados para resaltar la opcion activa en la barra de
        navegacion.
    layout:
        Layout de la pagina para ``st.set_page_config`` (por defecto ``wide``).
    show_inicio:
        Indica si el enlace a Inicio debe mostrarse en la barra de navegacion.
    enable_foreign_keys:
        Si es ``True`` activa ``PRAGMA foreign_keys = ON`` en la conexion devuelta.
    """

    ensure_session_from_token()

    _configure_page(page_title, layout)

    redirect_target = None
    caller_file = inspect.stack()[1].frame.f_globals.get("__file__")
    if caller_file:
        try:
            redirect_target = str(Path(caller_file).resolve().relative_to(Path.cwd()))
        except ValueError:
            redirect_target = Path(caller_file).name

    require_auth = active_top not in {"tarifas", "usuarios"}
    # Riesgo Fiscal no requiere rol de administrador; solo sesion valida
    if active_top in {"riesgo", "riesgo_firmes"}:
        if "usuario" not in st.session_state or "rol" not in st.session_state:
            _redirect_to_login(redirect_target, switch_to_page="pages/14_Riesgo_fiscal.py")
    elif require_auth:
        _ensure_admin_session(redirect_target)

    conn = get_conn()
    ensure_schema(conn)
    if enable_foreign_keys:
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass

    render_nav(active_top=active_top, active_child=active_child, show_inicio=show_inicio, show_cta=True)
    return conn
