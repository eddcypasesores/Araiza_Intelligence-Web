"""Formulario publico para restablecer contrasenas mediante token temporal."""

from __future__ import annotations

import streamlit as st

from core.theme import apply_theme
from core.db import (
    ensure_schema,
    get_conn,
    portal_consume_reset_token,
    portal_get_reset_token,
    portal_reset_password_to_default,
)
from core.streamlit_compat import set_query_params

st.set_page_config(page_title="Restablecer contrasena", layout="centered")
apply_theme()


def _resolve_token_param() -> str:
    raw = st.query_params.get("token")
    if isinstance(raw, list):
        raw = raw[-1] if raw else None
    return (raw or "").strip()


def _resolve_mode(default: str = "token") -> str:
    raw = st.query_params.get("mode")
    if isinstance(raw, list):
        raw = raw[-1] if raw else None
    value = (raw or default).strip().lower()
    if value not in {"token", "rfc"}:
        return default
    return value


def _resolve_rfc_param() -> str:
    raw = st.query_params.get("rfc")
    if isinstance(raw, list):
        raw = raw[-1] if raw else None
    return (raw or "").strip().upper()


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


def _reset_password_to_default(rfc: str) -> bool:
    conn = get_conn()
    ensure_schema(conn)
    try:
        return portal_reset_password_to_default(conn, rfc)
    finally:
        conn.close()


def main() -> None:
    st.title("Restablecer contrasena")
    st.write(
        "Ingresa el token recibido y define una nueva contrasena para tu cuenta. "
        "El token es de un solo uso y caduca en minutos. "
        "Si no cuentas con token, utiliza la seccion de restablecimiento con RFC."
    )

    mode = _resolve_mode()
    initial_token = _resolve_token_param()
    initial_rfc = _resolve_rfc_param()
    token_record = _lookup_token(initial_token)

    token_expander = st.expander(
        "Tengo un token de recuperacion",
        expanded=(mode != "rfc"),
    )
    with token_expander:
        if token_record:
            st.success(f"Token valido para el RFC {token_record['rfc']}.")
        elif initial_token:
            st.warning("El token proporcionado no es valido o ya expiro. Ingresa uno nuevo.")

        with st.form("password_reset_form", clear_on_submit=False):
            token_input = st.text_input("Token de recuperacion", value=initial_token)
            new_password = st.text_input("Nueva contrasena", type="password")
            confirm_password = st.text_input("Confirmar contrasena", type="password")
            submitted = st.form_submit_button("Actualizar contrasena", use_container_width=True)

        if submitted:
            token_input = (token_input or "").strip()
            new_password = (new_password or "").strip()
            confirm_password = (confirm_password or "").strip()

            if not token_input:
                st.error("Debes capturar el token de recuperacion.")
            elif len(new_password) < 8:
                st.error("La contrasena debe tener al menos 8 caracteres.")
            elif new_password != confirm_password:
                st.error("Las contrasenas no coinciden.")
            else:
                try:
                    updated = _consume_token(token_input, new_password)
                except Exception as exc:
                    st.error("No fue posible actualizar la contrasena. Intenta mas tarde.")
                    st.caption(f"Detalle tecnico: {exc}")
                else:
                    if not updated:
                        st.error("El token es invalido o ya fue utilizado.")
                    else:
                        st.success("Tu contrasena se actualizo correctamente. Usa la nueva contrasena al ingresar.")
                        st.info("Regresa al modulo correspondiente (Traslados o Monitoreo especializado de EFOS) para iniciar sesion.")
                        remaining = {
                            k: v
                            for k, v in st.query_params.items()
                            if k not in {"token", "mode"}
                        }
                        try:
                            set_query_params(remaining)
                        except Exception:
                            pass
                        st.stop()

    rfc_expander = st.expander(
        "Restablecer con mi RFC",
        expanded=(mode == "rfc"),
    )
    with rfc_expander:
        st.write(
            "Si no cuentas con un token, puedes restablecer la contrasena al valor de tu RFC. "
            "Ingresa tu RFC tal como esta registrado en el portal."
        )
        with st.form("reset_by_rfc_form", clear_on_submit=False):
            rfc_input = st.text_input("RFC", value=initial_rfc, placeholder="ej. ABCD800101XXX")
            rfc_submitted = st.form_submit_button(
                "Restablecer al valor del RFC",
                use_container_width=True,
            )

        if rfc_submitted:
            normalized_rfc = (rfc_input or "").strip().upper()
            if not normalized_rfc:
                st.error("Debes capturar el RFC para continuar.")
            else:
                try:
                    ok = _reset_password_to_default(normalized_rfc)
                except Exception as exc:
                    st.error("No fue posible restablecer la contrasena. Intenta mas tarde.")
                    st.caption(f"Detalle tecnico: {exc}")
                else:
                    if ok:
                        st.success(
                            "Contrasena restablecida al valor del RFC. Inicia sesion y cambiala inmediatamente."
                        )
                        remaining = {
                            k: v
                            for k, v in st.query_params.items()
                            if k not in {"mode", "rfc"}
                        }
                        try:
                            set_query_params(remaining)
                        except Exception:
                            pass
                    else:
                        st.error("No se encontro una cuenta con ese RFC.")


if __name__ == "__main__":
    main()
