"""Pantalla de acceso al modulo de Riesgo Fiscal."""

from __future__ import annotations

import streamlit as st

from core.auth import ensure_session_from_token, persist_login
from core.db import ensure_schema, get_conn, authenticate_portal_user, portal_reset_password_to_default
from core.navigation import render_nav
from core.streamlit_compat import set_query_params

st.set_page_config(page_title="Riesgo Fiscal | Araiza Intelligence", layout="wide")

ensure_session_from_token()


def _has_permission(module: str) -> bool:
    permisos = st.session_state.get("permisos") or []
    return module in permisos


def _render_login() -> None:
    """Renderiza el formulario de acceso al módulo de Riesgo Fiscal."""

    render_nav(active_top="riesgo", active_child=None, show_inicio=False)

    st.title("Acceso a Riesgo Fiscal")
    st.caption("Valida tus credenciales para consultar el cruce de RFC con la lista negra del SAT.")

    with st.form("riesgo_login", clear_on_submit=False):
        username = st.text_input("RFC", placeholder="ej. ZELE990823E20")
        password = st.text_input("Contrasena", type="password", placeholder="********")
        submitted = st.form_submit_button("Iniciar sesión", use_container_width=True)

    with st.expander("¿Olvidaste tu contrasena?", expanded=False):
        st.markdown("[Ya tengo un token de recuperacion](?page=pages/18_Restablecer_contrasena.py)")
        st.caption("Solicita a un administrador que genere un enlace temporal si no cuentas con uno.")
        recovery_rfc = st.text_input("RFC para restablecer", key="riesgo_recovery_rfc")
        if st.button("Restablecer al RFC", key="riesgo_recovery_btn"):
            rec_conn = get_conn()
            ensure_schema(rec_conn)
            try:
                ok = portal_reset_password_to_default(rec_conn, recovery_rfc)
            finally:
                rec_conn.close()
            if ok:
                st.success("Contrasena restablecida al valor del RFC. Inicia sesion y cambiala inmediatamente.")
            else:
                st.error("No se encontro una cuenta con ese RFC.")

    if not submitted:
        st.stop()

    username = (username or "").strip()
    password = password or ""

    conn = get_conn()
    ensure_schema(conn)
    try:
        record = authenticate_portal_user(conn, username, password)
    except Exception as exc:
        st.error("No fue posible validar las credenciales. Inténtalo de nuevo.")
        st.caption(f"Detalle técnico: {exc}")
        st.stop()
    finally:
        conn.close()

    if not record:
        st.error("RFC o contrasena incorrectos.")
        st.stop()

    permisos = set(record.get("permisos") or [])
    if "riesgos" not in permisos:
        st.error("Tu cuenta no tiene permiso para acceder al módulo de Riesgo Fiscal.")
        st.stop()

    token = persist_login(
        record["rfc"],
        record["permisos"],
        must_change_password=record.get("must_change_password", False),
        user_id=record.get("id"),
    )
    try:
        params = {k: v for k, v in st.query_params.items() if k != "auth"}
        params["auth"] = token
        set_query_params(params)
    except Exception:
        pass

    st.switch_page("pages/15_Lista_negra_Sat.py")

if st.session_state.get("usuario") and _has_permission("riesgos"):
    st.switch_page("pages/15_Lista_negra_Sat.py")

_render_login()
