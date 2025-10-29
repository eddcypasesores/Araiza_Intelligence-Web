"""Pantalla independiente de acceso para el super administrador del portal."""

from __future__ import annotations

from contextlib import closing

import streamlit as st

from core.auth import ensure_session_from_token, persist_login
from core.db import authenticate_portal_user, ensure_schema, get_conn
from core.navigation import render_nav
from core.streamlit_compat import set_query_params

st.set_page_config(page_title="Acceso Administrador | Araiza Intelligence", layout="wide")

ensure_session_from_token()

permisos = set(st.session_state.get("permisos") or [])
if st.session_state.get("usuario") and "admin" in permisos:
    render_nav(active_top="acerca", active_child="acerca_admin")
    st.success("Ya tienes una sesión activa. Redirigiendo al panel principal...")
    st.switch_page("pages/19_Admin_portal.py")
    st.stop()

render_nav(active_top="acerca", active_child="acerca_admin")

st.title("Acceso a la administración del portal")
st.caption(
    "Valida tus credenciales de super administrador para gestionar usuarios, permisos y restablecimientos."
)

with st.form("super_admin_login", clear_on_submit=False):
    admin_rfc = st.text_input("RFC", placeholder="ej. ADMINISTRADOR")
    admin_password = st.text_input("Contraseña", type="password", placeholder="********")
    submitted = st.form_submit_button("Iniciar sesión", use_container_width=True)

st.caption(
    "¿Olvidaste tu contraseña? Solicita un enlace temporal y utiliza "
    "[esta página](?page=pages/18_Restablecer_contrasena.py) para restablecerla."
)

if not submitted:
    st.stop()

username = (admin_rfc or "").strip().upper()
password = admin_password or ""

if not username or not password:
    st.error("Captura RFC y contraseña para continuar.")
    st.stop()

try:
    with closing(get_conn()) as conn:
        ensure_schema(conn)
        record = authenticate_portal_user(conn, username, password)
except Exception as exc:
    st.error("No fue posible validar las credenciales.")
    st.caption(f"Detalle técnico: {exc}")
    st.stop()

if not record:
    st.error("RFC o contraseña incorrectos.")
    st.stop()

permisos_record = set(record.get("permisos") or [])
if "admin" not in permisos_record:
    st.error("Tu cuenta no tiene privilegios de super administrador.")
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

st.success("Acceso concedido. Redirigiendo al panel de administración...")
st.switch_page("pages/19_Admin_portal.py")
