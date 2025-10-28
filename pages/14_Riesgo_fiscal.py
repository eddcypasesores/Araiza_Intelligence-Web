"""Pantalla de acceso al modulo de Riesgo Fiscal."""

from __future__ import annotations

import streamlit as st

from core.auth import ensure_session_from_token, persist_login
from core.db import ensure_schema, get_conn, validar_usuario
from core.navigation import render_nav
from core.streamlit_compat import set_query_params

st.set_page_config(page_title="Riesgo Fiscal | Araiza Intelligence", layout="wide")

ensure_session_from_token()

ALLOWED_ROLES = {"admin", "operador"}


def _render_login() -> None:
    """Mostrar formulario de autenticacion especifico para Riesgo Fiscal."""

    render_nav(active_top=None, show_cta=False)

    st.title("Acceso a Riesgo Fiscal")
    st.caption(
        "Valida tus credenciales para consultar el cruce de RFC con la lista negra del SAT."
    )

    with st.form("riesgo_login", clear_on_submit=False):
        username = st.text_input("Usuario", placeholder="ej. admin")
        password = st.text_input("Contrasena", type="password", placeholder="********")
        submitted = st.form_submit_button("Iniciar sesion", use_container_width=True)

    if not submitted:
        st.stop()

    username = username.strip()
    conn = get_conn()
    ensure_schema(conn)
    try:
        rol = validar_usuario(conn, username, password)
    except Exception as exc:
        st.error("No fue posible validar las credenciales. Intentalo de nuevo.")
        st.caption(f"Detalle tecnico: {exc}")
        st.stop()
    finally:
        conn.close()

    if not rol or rol not in ALLOWED_ROLES:
        st.error("Usuario o contrasena incorrectos, o sin permiso para Riesgo Fiscal.")
        st.stop()

    token = persist_login(username, rol)
    try:
        params = {k: v for k, v in st.query_params.items() if k != "auth"}
        params["auth"] = token
        set_query_params(params)
    except Exception:
        pass

    st.switch_page("pages/15_Lista_negra_Sat.py")


if st.session_state.get("usuario") and st.session_state.get("rol") in ALLOWED_ROLES:
    st.switch_page("pages/15_Lista_negra_Sat.py")

_render_login()
