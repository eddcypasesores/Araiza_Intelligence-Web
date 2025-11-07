"""Shared helpers for super administrator Streamlit pages."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import streamlit as st

from .auth import ensure_session_from_token, persist_login
from .db import (
    ensure_schema,
    get_conn,
    portal_get_user,
    portal_set_password,
)


def _refresh_permissions_from_db(username: str) -> set[str]:
    """Fetch the latest permissions for ``username`` and update session state."""

    normalized = (username or "").strip().upper()
    if not normalized:
        return set()
    try:
        with closing(get_conn()) as conn:
            ensure_schema(conn)
            record = portal_get_user(conn, normalized)
    except Exception:
        return set()
    if not record:
        return set()
    permisos = set(record.get("permisos") or [])
    if permisos:
        st.session_state["permisos"] = list(permisos)
        st.session_state["portal_user_id"] = record.get("id")
    return permisos


def require_super_admin() -> None:
    """Abort the request if the current session is not a super administrator."""

    ensure_session_from_token()
    username = st.session_state.get("usuario")
    permisos = set(st.session_state.get("permisos") or [])
    if username and "admin" not in permisos:
        permisos = _refresh_permissions_from_db(username)
    if not username or "admin" not in permisos:
        st.error(
            "Acceso restringido. Inicia sesion como super administrador desde la seccion 'Acerca de Nosotros'."
        )
        st.stop()


def enforce_super_admin_password_change(conn: sqlite3.Connection) -> None:
    """Force the user to update their password when the flag is set."""

    if not st.session_state.get("must_change_password"):
        return

    st.warning("Debes actualizar tu contrasena antes de continuar.")
    with st.form("forced_super_admin_change", clear_on_submit=False):
        nueva = st.text_input("Nueva contrasena", type="password")
        confirm = st.text_input("Confirmar contrasena", type="password")
        submitted = st.form_submit_button("Actualizar ahora", use_container_width=True)

    if not submitted:
        st.stop()

    nueva = (nueva or "").strip()
    confirm = (confirm or "").strip()
    if len(nueva) < 8:
        st.error("La contrasena debe tener al menos 8 caracteres.")
        st.stop()
    if nueva != confirm:
        st.error("Las contrasenas no coinciden.")
        st.stop()

    try:
        username = st.session_state.get("usuario", "") or ""
        portal_set_password(conn, username, nueva, require_change=False)
        permisos = st.session_state.get("permisos") or []
        persist_login(
            username,
            permisos,
            must_change_password=False,
            user_id=st.session_state.get("portal_user_id"),
        )
        st.session_state["must_change_password"] = False
        st.success("Contrasena actualizada correctamente.")
    except Exception as exc:  # pragma: no cover - UI path
        st.error(f"No fue posible actualizar la contrasena: {exc}")
        st.stop()
    finally:
        st.stop()
