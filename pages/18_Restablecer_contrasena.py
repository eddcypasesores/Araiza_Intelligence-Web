"""Formulario publico para restablecer contrasenas mediante token temporal."""

from __future__ import annotations

import streamlit as st

from core.db import (
    ensure_schema,
    get_conn,
    portal_consume_reset_token,
    portal_get_reset_token,
)
from core.streamlit_compat import set_query_params

st.set_page_config(page_title="Restablecer contrasena", layout="centered")


def _resolve_token_param() -> str:
    raw = st.query_params.get("token")
    if isinstance(raw, list):
        raw = raw[-1] if raw else None
    return (raw or "").strip()


def _lookup_token(token: str):
    if not token:
        return None
    conn = get_conn()
    ensure_schema(conn)
    try:
        return portal_get_reset_token(conn, token)
    finally:
        conn.close()


def _consume_token(token: str, new_password: str) -> bool:
    conn = get_conn()
    ensure_schema(conn)
    try:
        return portal_consume_reset_token(conn, token, new_password)
    finally:
        conn.close()


def main() -> None:
    st.title("Restablecer contrasena")
    st.write(
        "Ingresa el token recibido y define una nueva contrasena para tu cuenta. "
        "El token es de un solo uso y caduca en minutos."
    )

    initial_token = _resolve_token_param()
    token_record = _lookup_token(initial_token)

    if token_record:
        st.success(f"Token valido para el RFC {token_record['rfc']}.")
    elif initial_token:
        st.warning("El token proporcionado no es valido o ya expiro. Ingresa uno nuevo.")

    with st.form("password_reset_form", clear_on_submit=False):
        token_input = st.text_input("Token de recuperacion", value=initial_token)
        new_password = st.text_input("Nueva contrasena", type="password")
        confirm_password = st.text_input("Confirmar contrasena", type="password")
        submitted = st.form_submit_button("Actualizar contrasena", use_container_width=True)

    if not submitted:
        return

    token_input = (token_input or "").strip()
    new_password = (new_password or "").strip()
    confirm_password = (confirm_password or "").strip()

    if not token_input:
        st.error("Debes capturar el token de recuperacion.")
        return
    if len(new_password) < 8:
        st.error("La contrasena debe tener al menos 8 caracteres.")
        return
    if new_password != confirm_password:
        st.error("Las contrasenas no coinciden.")
        return

    try:
        updated = _consume_token(token_input, new_password)
    except Exception as exc:
        st.error("No fue posible actualizar la contrasena. Intenta mas tarde.")
        st.caption(f"Detalle tecnico: {exc}")
        return

    if not updated:
        st.error("El token es invalido o ya fue utilizado.")
        return

    st.success("Tu contrasena se actualizo correctamente. Usa la nueva contrasena al ingresar.")
    st.info("Regresa al modulo correspondiente (Traslados o Riesgo Fiscal) para iniciar sesion.")
    remaining = {k: v for k, v in st.query_params.items() if k != "token"}
    try:
        set_query_params(remaining)
    except Exception:
        pass


if __name__ == "__main__":
    main()
