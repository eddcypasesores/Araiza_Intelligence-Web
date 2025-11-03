"""Login independiente para el modulo DIOT."""

from __future__ import annotations

import streamlit as st

from core.auth import ensure_session_from_token, persist_login
from core.db import ensure_schema, get_conn, authenticate_portal_user
from core.flash import consume_flash, set_flash
from core.login_ui import render_login_header, render_token_reset_section
from core.streamlit_compat import rerun, set_query_params, normalize_page_path

def _redirect_if_authenticated() -> None:
    permisos = set(st.session_state.get("permisos") or [])
    if "diot" in permisos:
        try:
            st.switch_page("pages/22_DIOT_excel_txt.py")
        except Exception:
            rerun()
        st.stop()


def main() -> None:
    ensure_session_from_token()
    consume_flash()

    _redirect_if_authenticated()

    raw_next = st.query_params.get("next")
    if isinstance(raw_next, list):
        redirect_target = raw_next[-1] if raw_next else None
    elif isinstance(raw_next, str):
        redirect_target = raw_next or None
    else:
        redirect_target = None
    redirect_target = normalize_page_path(redirect_target)

    render_login_header("Acceso DIOT", subtitle="Inicia sesion para utilizar las herramientas DIOT")

    with st.form("diot_login_form", clear_on_submit=False):
        username = st.text_input("RFC", placeholder="ej. ABCD800101XXX")
        password = st.text_input("Contrasena", type="password", placeholder="********")
        col_submit, col_cancel = st.columns(2)
        submitted = col_submit.form_submit_button("Iniciar sesion", use_container_width=True)
        cancelled = col_cancel.form_submit_button("Cancelar", use_container_width=True)

    if cancelled:
        try:
            st.switch_page("pages/0_Inicio.py")
        except Exception:
            rerun()
        st.stop()

    handled_reset = render_token_reset_section("diot")

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
        conn.close()
        st.stop()

    if not record:
        conn.close()
        st.error("RFC o contrasena incorrectos.")
        st.stop()

    permisos = set(record.get("permisos") or [])
    if "diot" not in permisos:
        conn.close()
        st.error("Tu cuenta no tiene acceso al modulo DIOT.")
        st.stop()

    token = persist_login(
        record["rfc"],
        record["permisos"],
        must_change_password=record.get("must_change_password", False),
        user_id=record.get("id"),
    )
    conn.close()

    set_flash(f"Inicio de sesion correcto. Bienvenido, {record['rfc']}.")

    try:
        params = {k: v for k, v in st.query_params.items() if k != "auth"}
        params["auth"] = token
        if redirect_target:
            params["next"] = redirect_target
        set_query_params(params)
    except Exception:
        pass

    if redirect_target:
        try:
            st.switch_page(redirect_target)
        except Exception:
            rerun()
        st.stop()

    _redirect_if_authenticated()
    rerun()


if __name__ == "__main__":
    main()
