"""Utilidades compartidas para secciones de administracion."""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path
from typing import Optional

import streamlit as st

from core.auth import ensure_session_from_token
from core.db import ensure_schema, get_conn
from core.navigation import CEDULA_TOPS, DIOT_TOPS, MONITOREO_TOPS, TRASLADOS_TOPS, render_nav
from core.streamlit_compat import set_query_params, normalize_page_path


def _redirect_to_login(
    target_page: str | None = None,
    switch_to_page: str = "pages/1_Calculadora.py",
    *,
    remember_target: bool = True,
) -> None:
    """Redirige al login en caso de que la sesion no sea valida."""

    st.warning(" Debes iniciar sesion primero.")
    target_page = normalize_page_path(target_page)
    params = {k: v for k, v in st.query_params.items() if k not in {"logout", "next"}}
    if remember_target and target_page:
        params["next"] = target_page
    try:
        st.experimental_set_query_params(**params)
    except Exception:
        pass
    try:
        st.switch_page(normalize_page_path(switch_to_page) or switch_to_page)
    except Exception:
        st.stop()
    st.stop()


def _ensure_permission(
    required_permissions: tuple[str, ...],
    *,
    redirect_to: str | None,
    fallback_page: str,
    remember_target: bool = True,
) -> None:
    """Ensure the logged-in user has the required permission for the module."""

    ensure_session_from_token()

    if "usuario" not in st.session_state:
        _redirect_to_login(
            redirect_to,
            switch_to_page=fallback_page,
            remember_target=remember_target,
        )

    permisos = set(st.session_state.get("permisos") or [])
    if not any(required in permisos for required in required_permissions):
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
            redirect_target = Path(caller_file).resolve().relative_to(Path.cwd()).as_posix()
        except ValueError:
            redirect_target = Path(caller_file).name
        redirect_target = normalize_page_path(redirect_target)

    if active_top == "diot":
        ensure_session_from_token()
        permisos = set(st.session_state.get("permisos") or [])
        if "diot" not in permisos:
            params = {k: v for k, v in st.query_params.items() if k not in {"logout", "next"}}
            if redirect_target:
                params["next"] = redirect_target
            try:
                set_query_params(params)
            except Exception:
                pass
            try:
                st.switch_page("pages/23_DIOT_login.py")
            except Exception:
                st.page_link("pages/23_DIOT_login.py", label="Ir al login DIOT")
            st.stop()

    if active_top in MONITOREO_TOPS:
        pass
    elif active_top in CEDULA_TOPS:
        _ensure_permission(
            ("cedula",),
            redirect_to=redirect_target,
            fallback_page="pages/Cedula_Impuestos.py",
            remember_target=False,
        )
    elif active_top in TRASLADOS_TOPS or active_top is None or active_top in {"tarifas", "trabajadores", "parametros"}:
        if active_top not in {"tarifas", "trabajadores", "parametros"}:
            _ensure_permission(
                ("traslados",),
                redirect_to=redirect_target,
                fallback_page="pages/1_Calculadora.py",
                remember_target=False,
            )
    else:
        _ensure_permission(
            ("admin",),
            redirect_to=redirect_target,
            fallback_page="pages/19_Admin_portal.py",
        )

    conn = get_conn()
    ensure_schema(conn)
    if enable_foreign_keys:
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass

    render_top = active_top
    render_child = active_child
    if active_top in {"tarifas", "trabajadores", "parametros"}:
        base = active_top or "tarifas"
        render_child = f"{base}_{active_child}" if active_child else f"{base}_consultar"
    if active_top == "diot" and not render_child:
        render_child = "diot_excel_txt"

    render_nav(active_top=render_top, active_child=render_child, show_inicio=show_inicio)
    return conn
