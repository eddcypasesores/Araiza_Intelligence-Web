"""Utilidades compartidas para secciones de administración."""

from __future__ import annotations

import sqlite3
from typing import Optional

import streamlit as st

from core.auth import ensure_session_from_token
from core.db import ensure_schema, get_conn
from core.navigation import render_nav


def _redirect_to_login() -> None:
    """Redirige al login en caso de que la sesión no sea válida."""

    st.warning("⚠️ Debes iniciar sesión primero.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()
    st.stop()


def _ensure_admin_session() -> None:
    """Valida que exista una sesión activa con privilegios de administrador."""

    ensure_session_from_token()

    if "usuario" not in st.session_state or "rol" not in st.session_state:
        _redirect_to_login()

    if str(st.session_state.get("rol", "")).lower() != "admin":
        st.error("🚫 No tienes permiso para acceder a esta página.")
        st.stop()


def _configure_page(page_title: str, layout: str) -> None:
    """Configura la página solo una vez por ejecución."""

    if not st.session_state.get("_admin_page_configured"):
        st.set_page_config(page_title=page_title, layout=layout)
        st.session_state["_admin_page_configured"] = True


def init_admin_section(
    *,
    page_title: str,
    active_top: Optional[str] = None,
    active_child: Optional[str] = None,
    layout: str = "wide",
    show_inicio: bool = True,
) -> sqlite3.Connection:
    """Inicializa el entorno de una página administrativa y devuelve la conexión.

    Parámetros
    ----------
    page_title:
        Título a mostrar en la pestaña del navegador.
    active_top, active_child:
        Identificadores usados para resaltar la opción activa en la barra de
        navegación.
    layout:
        Layout de la página para ``st.set_page_config`` (por defecto ``wide``).
    show_inicio:
        Indica si el enlace a Inicio debe mostrarse en la barra de navegación.
    """

    _configure_page(page_title, layout)
    _ensure_admin_session()

    conn = get_conn()
    ensure_schema(conn)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass

    render_nav(active_top=active_top, active_child=active_child, show_inicio=show_inicio)
    return conn
