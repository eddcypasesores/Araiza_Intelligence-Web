"""Shared helpers for admin-only Streamlit pages."""

from __future__ import annotations

import streamlit as st

from core.auth import ensure_session_from_token
from core.db import ensure_schema, get_conn
from core.navigation import render_nav


def init_admin_section(
    *,
    page_title: str,
    active_top: str,
    active_child: str,
    layout: str = "wide",
    show_inicio: bool = True,
    enable_foreign_keys: bool = False,
):
    """Configure the page, enforce admin access and render the navbar.

    Returns the SQLite connection ready to be used by the page.
    """

    st.set_page_config(page_title=page_title, layout=layout)
    ensure_session_from_token()

    if "usuario" not in st.session_state or "rol" not in st.session_state:
        st.warning("⚠️ Debes iniciar sesión primero.")
        try:
            st.switch_page("app.py")
        except Exception:
            st.stop()
        st.stop()

    if st.session_state["rol"] != "admin":
        st.error("🚫 No tienes permiso para acceder a esta página.")
        st.stop()

    conn = get_conn()
    ensure_schema(conn)

    if enable_foreign_keys:
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass

    render_nav(active_top=active_top, active_child=active_child, show_inicio=show_inicio)

    return conn
