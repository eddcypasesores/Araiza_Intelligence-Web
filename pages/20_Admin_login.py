"""Pantalla independiente de acceso para el super administrador del portal."""

from __future__ import annotations

from contextlib import closing

import streamlit as st

from core.auth import ensure_session_from_token, persist_login
from core.db import authenticate_portal_user, ensure_schema, get_conn
from core.flash import consume_flash, set_flash
from core.login_ui import render_login_header, render_token_reset_section
from core.streamlit_compat import set_query_params

st.set_page_config(
    page_title="Acceso Administrador | Araiza Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ensure_session_from_token()
consume_flash()

permisos = set(st.session_state.get("permisos") or [])
if st.session_state.get("usuario") and "admin" in permisos:
    set_flash("Sesion ya activa. Redirigiendo al panel principal.")
    st.switch_page("pages/19_Admin_portal.py")
    st.stop()

render_login_header("Iniciar sesion", subtitle="Acceso super administrador")

st.caption(
    "Valida tus credenciales de super administrador para gestionar usuarios, permisos y restablecimientos."
)

with st.form("super_admin_login", clear_on_submit=False):
    admin_rfc = st.text_input("RFC", placeholder="ej. ADMINISTRADOR")
    admin_password = st.text_input("Contrasena", type="password", placeholder="********")
    col_login, col_cancel = st.columns(2)
    submitted = col_login.form_submit_button("Iniciar sesion", use_container_width=True)
    cancelled = col_cancel.form_submit_button("Cancelar", use_container_width=True)

if cancelled:
    st.switch_page("pages/0_Inicio.py")
    st.stop()

handled_reset = render_token_reset_section("admin")

if handled_reset:
    st.stop()

if not submitted:
    st.stop()

username = (admin_rfc or "").strip().upper()
password = admin_password or ""

if not username or not password:
    st.error("Captura RFC y contrasena para continuar.")
    st.stop()

try:
    with closing(get_conn()) as conn:
        ensure_schema(conn)
        record = authenticate_portal_user(conn, username, password)
except Exception as exc:
    st.error("No fue posible validar las credenciales.")
    st.caption(f"Detalle tecnico: {exc}")
    st.stop()

if not record:
    st.error("RFC o contrasena incorrectos.")
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

set_flash("Inicio de sesion exitoso")

try:
    params = {k: v for k, v in st.query_params.items() if k != "auth"}
    params["auth"] = token
    set_query_params(params)
except Exception:
    pass

st.switch_page("pages/19_Admin_portal.py")
