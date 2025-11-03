"""Pantalla de acceso al modulo Cedula de impuestos."""

from __future__ import annotations

import streamlit as st

from core.auth import ensure_session_from_token, persist_login, forget_session
from core.db import ensure_schema, get_conn, authenticate_portal_user
from core.streamlit_compat import rerun, set_query_params, normalize_page_path
from core.flash import consume_flash, set_flash
from core.login_ui import render_login_header, render_token_reset_section
from core.session import process_logout_flag

st.set_page_config(page_title="Cedula de impuestos | Araiza Intelligence", layout="wide")


def _handle_logout_request() -> None:
    if process_logout_flag():
        forget_session()


_handle_logout_request()
ensure_session_from_token()


def _has_permission(module: str) -> bool:
    permisos = st.session_state.get("permisos") or []
    return module in permisos


def _resolve_redirect_target() -> str | None:
    raw_next = st.query_params.get("next")
    if isinstance(raw_next, list):
        candidate = raw_next[-1] if raw_next else None
    elif isinstance(raw_next, str):
        candidate = raw_next or None
    else:
        candidate = None
    return normalize_page_path(candidate)


def _render_login() -> None:
    """Formulario de acceso para el modulo de Cedula de impuestos."""

    consume_flash()

    render_login_header("Iniciar sesion", subtitle="Acceso Cedula de impuestos")

    st.caption(
        "Valida tus credenciales para acceder al panel de Cedula de impuestos para cierre anual."
    )

    with st.form("cedula_login", clear_on_submit=False):
        username = st.text_input("RFC", placeholder="ej. ABCD800101XXX")
        password = st.text_input("Contrasena", type="password", placeholder="********")
        col_login, col_cancel = st.columns(2)
        submitted = col_login.form_submit_button("Iniciar sesion", use_container_width=True)
        cancelled = col_cancel.form_submit_button("Cancelar", use_container_width=True)

    if cancelled:
        st.switch_page("pages/0_Inicio.py")
        st.stop()

    handled_reset = render_token_reset_section("cedula")

    if handled_reset:
        st.stop()

    if not submitted:
        st.stop()

    username = (username or "").strip()
    password = password or ""

    conn = get_conn()
    ensure_schema(conn)
    try:
        record = authenticate_portal_user(conn, username, password)
    except Exception as exc:
        st.error("No fue posible validar las credenciales. Intentalo de nuevo.")
        st.caption(f"Detalle tecnico: {exc}")
        st.stop()
    finally:
        conn.close()

    if not record:
        st.error("RFC o contrasena incorrectos.")
        st.stop()

    permisos = set(record.get("permisos") or [])
    if "cedula" not in permisos:
        st.error("Tu cuenta no tiene permiso para acceder al modulo de Cedula de impuestos.")
        st.stop()

    token = persist_login(
        record["rfc"],
        record["permisos"],
        must_change_password=record.get("must_change_password", False),
        user_id=record.get("id"),
    )
    set_flash("Inicio de sesion en Cedula de impuestos")

    redirect_target = _resolve_redirect_target()

    if redirect_target:
        remaining = {k: v for k, v in st.query_params.items() if k != "next"}
        remaining["auth"] = token
        try:
            set_query_params(remaining)
        except Exception:
            pass
        try:
            st.switch_page(redirect_target)
        except Exception:
            rerun()
        return

    try:
        params = {k: v for k, v in st.query_params.items() if k != "auth"}
        params["auth"] = token
        set_query_params(params)
    except Exception:
        pass

    st.switch_page("pages/Cedula_Impuestos_inicio.py")


if st.session_state.get("usuario") and _has_permission("cedula"):
    st.switch_page("pages/Cedula_Impuestos_inicio.py")

_render_login()
