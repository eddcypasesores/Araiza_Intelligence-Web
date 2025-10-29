"""Administracion central de usuarios y permisos del portal."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import timezone
from typing import Sequence

import streamlit as st

from core.auth import ensure_session_from_token, persist_login
from core.db import (
    PORTAL_ALLOWED_MODULES,
    ensure_schema,
    get_conn,
    portal_create_reset_token,
    portal_create_user,
    portal_delete_users,
    portal_list_pending_resets,
    portal_list_users,
    portal_revoke_reset_tokens,
    portal_set_password,
    portal_update_user,
)
from core.navigation import render_nav
from core.streamlit_compat import rerun

_MODULE_LABEL_OVERRIDES = {
    "traslados": "Traslados",
    "riesgos": "Riesgo Fiscal",
    "admin": "Administracion",
}


def _module_label(value: str) -> str:
    label = _MODULE_LABEL_OVERRIDES.get(value)
    if label:
        return label
    cleaned = value.replace("_", " ").strip()
    if not cleaned:
        return "Sin nombre"
    return cleaned.title()


MODULE_OPTIONS = [(_module_label(code), code) for code in PORTAL_ALLOWED_MODULES]
LABEL_BY_VALUE = {value: label for label, value in MODULE_OPTIONS}
VALUE_BY_LABEL = {label: value for label, value in MODULE_OPTIONS}


def _parse_permissions(raw) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(p) for p in data if isinstance(p, str)]


def _permisos_multiselect(default: Sequence[str] | None) -> list[str]:
    labels = [label for label, _ in MODULE_OPTIONS]
    default_values: list[str]
    if isinstance(default, str):
        default_values = _parse_permissions(default)
    else:
        default_values = list(default or [])
    selected_labels = st.multiselect(
        "Permisos de acceso",
        options=labels,
        default=[LABEL_BY_VALUE.get(value, value) for value in default_values],
    )
    return [VALUE_BY_LABEL.get(label, label) for label in selected_labels]


def _display_users_table(conn: sqlite3.Connection) -> None:
    df = portal_list_users(conn)
    if df.empty:
        st.info("No hay usuarios registrados.")
        return
    df = df.copy()
    df["permisos"] = df["permisos"].apply(
        lambda raw: ", ".join(LABEL_BY_VALUE.get(p, p) for p in _parse_permissions(raw)) or "-"
    )
    df.rename(
        columns={
            "rfc": "RFC",
            "regimen_fiscal": "Regimen fiscal",
            "calle": "Calle",
            "colonia": "Colonia",
            "cp": "C.P.",
            "municipio": "Alcaldia / Municipio",
            "email": "Email",
            "telefono": "Telefono",
            "permisos": "Modulos",
            "must_change_password": "Debe cambiar contrasena",
            "created_at": "Creado",
            "updated_at": "Actualizado",
        },
        inplace=True,
    )
    st.dataframe(df, use_container_width=True, hide_index=True)


def _create_user(conn: sqlite3.Connection) -> None:
    st.subheader("Crear usuario")
    with st.form("create_portal_user", clear_on_submit=False):
        rfc = st.text_input("RFC*", placeholder="ej. ZELE990823E20")
        regimen = st.text_input("Regimen fiscal")
        calle = st.text_input("Calle")
        colonia = st.text_input("Colonia")
        cp = st.text_input("Codigo postal")
        municipio = st.text_input("Alcaldia o municipio")
        email = st.text_input("Correo electronico")
        telefono = st.text_input("Telefono")
        permisos = _permisos_multiselect(["traslados"])
        submitted = st.form_submit_button("Guardar usuario", use_container_width=True)

    if not submitted:
        return

    rfc_normalizado = (rfc or "").strip().upper()
    if not rfc_normalizado:
        st.error("El RFC es obligatorio.")
        return
    if not permisos:
        st.error("Selecciona al menos un modulo.")
        return

    try:
        portal_create_user(
            conn,
            rfc=rfc_normalizado,
            regimen_fiscal=regimen.strip() or None,
            calle=calle.strip() or None,
            colonia=colonia.strip() or None,
            cp=cp.strip() or None,
            municipio=municipio.strip() or None,
            email=email.strip() or None,
            telefono=telefono.strip() or None,
            permisos=permisos,
            must_change_password=True,
        )
        st.success("Usuario creado. La contrasena inicial es el mismo RFC (mayusculas).")
        rerun()
    except Exception as exc:
        st.error(f"No fue posible crear el usuario: {exc}")


def _select_existing_user(conn: sqlite3.Connection):
    df = portal_list_users(conn)
    if df.empty:
        st.info("No hay usuarios registrados.")
        return df
    rfcs = df["rfc"].tolist()
    selected = st.selectbox("Selecciona un usuario", rfcs)
    if not selected:
        return df.iloc[0:0]
    return df[df["rfc"] == selected].reset_index(drop=True)


def _edit_user(conn: sqlite3.Connection) -> None:
    st.subheader("Modificar usuario")
    df = _select_existing_user(conn)
    if df.empty:
        return
    record = df.iloc[0].to_dict()
    permisos_actuales = _parse_permissions(record.get("permisos"))
    with st.form("edit_portal_user", clear_on_submit=False):
        regimen = st.text_input("Regimen fiscal", value=record.get("regimen_fiscal") or "")
        calle = st.text_input("Calle", value=record.get("calle") or "")
        colonia = st.text_input("Colonia", value=record.get("colonia") or "")
        cp = st.text_input("Codigo postal", value=record.get("cp") or "")
        municipio = st.text_input("Alcaldia o municipio", value=record.get("municipio") or "")
        email = st.text_input("Correo electronico", value=record.get("email") or "")
        telefono = st.text_input("Telefono", value=record.get("telefono") or "")
        permisos = _permisos_multiselect(permisos_actuales)
        must_change = st.checkbox(
            "Solicitar cambio de contrasena al siguiente inicio",
            value=bool(record.get("must_change_password")),
        )
        nueva_contrasena = st.text_input("Nueva contrasena (opcional)", type="password")
        submitted = st.form_submit_button("Guardar cambios", use_container_width=True)

    if not submitted:
        return
    try:
        portal_update_user(
            conn,
            record["rfc"],
            regimen_fiscal=regimen.strip() or None,
            calle=calle.strip() or None,
            colonia=colonia.strip() or None,
            cp=cp.strip() or None,
            municipio=municipio.strip() or None,
            email=email.strip() or None,
            telefono=telefono.strip() or None,
            permisos=permisos,
            must_change_password=must_change,
        )
        nueva_contrasena = nueva_contrasena.strip()
        if nueva_contrasena:
            portal_set_password(conn, record["rfc"], nueva_contrasena, require_change=must_change)
        st.success("Usuario actualizado correctamente.")
        rerun()
    except Exception as exc:
        st.error(f"No fue posible actualizar el usuario: {exc}")


def _delete_users(conn: sqlite3.Connection) -> None:
    st.subheader("Eliminar usuarios")
    df = portal_list_users(conn)
    if df.empty:
        st.info("No hay usuarios registrados.")
        return
    rfcs = df["rfc"].tolist()
    seleccion = st.multiselect("Selecciona los usuarios a eliminar", options=rfcs)
    if not seleccion:
        return
    if st.button("Eliminar seleccionados", type="primary", use_container_width=True):
        try:
            portal_delete_users(conn, seleccion)
            st.success("Usuarios eliminados.")
            rerun()
        except Exception as exc:
            st.error(f"No fue posible eliminar usuarios: {exc}")


def _reset_passwords(conn: sqlite3.Connection) -> None:
    st.subheader("Restablecer contrasena a RFC")
    df = portal_list_users(conn)
    if df.empty:
        st.info("No hay usuarios registrados.")
        return
    rfcs = df["rfc"].tolist()
    seleccion = st.multiselect("Selecciona los usuarios a restablecer", options=rfcs)
    if not seleccion:
        return
    if st.button("Restablecer contrasenas", type="primary", use_container_width=True):
        try:
            for rfc in seleccion:
                portal_set_password(conn, rfc, rfc.strip().upper(), require_change=True)
            st.success(
                "Contrasenas restablecidas. El RFC es la contrasena temporal y deberan cambiarla en el siguiente ingreso."
            )
        except Exception as exc:
            st.error(f"No fue posible restablecer contrasenas: {exc}")


def _manage_recovery_tokens(conn: sqlite3.Connection) -> None:
    st.subheader("Recuperacion de contrasenas")
    df = portal_list_users(conn)
    if df.empty:
        st.info("No hay usuarios registrados.")
        return

    rfcs = df["rfc"].tolist()
    col_form, col_tokens = st.columns([1, 1])

    with col_form:
        st.write("Genera un enlace temporal para que el usuario restablezca su contrasena.")
        selected_rfc = st.selectbox("Selecciona un usuario", rfcs, key="reset_link_user")
        ttl_minutes = st.number_input(
            "Vigencia del enlace (minutos)",
            min_value=5,
            max_value=1440,
            value=60,
            step=5,
        )
        if st.button("Generar enlace de recuperacion", use_container_width=True):
            try:
                token = portal_create_reset_token(
                    conn,
                    selected_rfc,
                    ttl_minutes=int(ttl_minutes),
                )
                reset_url = f"/?page=pages/18_Restablecer_contrasena.py&token={token}"
                st.success("Enlace generado. Compartelo de forma segura con el usuario.")
                st.code(reset_url, language="text")
            except Exception as exc:
                st.error(f"No fue posible generar el enlace: {exc}")

    with col_tokens:
        st.write("Enlaces activos")
        tokens = portal_list_pending_resets(conn)
        if not tokens:
            st.caption("No hay enlaces pendientes.")
            return

        options = []
        for item in tokens:
            expires = item["expires_at"]
            if expires and expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires:
                expires_text = expires.strftime("%Y-%m-%d %H:%M UTC")
            else:
                expires_text = "Sin fecha"
            options.append(f"{item['rfc']} -> vence {expires_text}")

        seleccion = st.multiselect(
            "Selecciona enlaces a revocar",
            options=options,
            key="reset_links_to_revoke",
        )
        if seleccion:
            indices = [options.index(label) for label in seleccion]
            tokens_to_revoke = [tokens[i]["token"] for i in indices]
            if st.button("Revocar seleccionados", type="primary", use_container_width=True):
                try:
                    portal_revoke_reset_tokens(conn, tokens=tokens_to_revoke)
                    st.success("Enlaces revocados.")
                    rerun()
                except Exception as exc:
                    st.error(f"No fue posible revocar los enlaces: {exc}")


def _enforce_password_change(conn: sqlite3.Connection) -> None:
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
    except Exception as exc:
        st.error(f"No fue posible actualizar la contrasena: {exc}")
        st.stop()
    finally:
        st.stop()


def _require_super_admin() -> None:
    ensure_session_from_token()
    permisos = set(st.session_state.get("permisos") or [])
    if not st.session_state.get("usuario") or "admin" not in permisos:
        st.error(
            "Acceso restringido. Inicia sesion como super administrador desde la seccion 'Acerca de Nosotros'."
        )
        st.stop()


def main() -> None:
    st.set_page_config(page_title="Administracion del portal", layout="wide")
    _require_super_admin()
    render_nav(active_top="admin_portal", show_inicio=True)

    st.title("Administracion del portal")
    st.caption("Administra cuentas de acceso y permisos para los distintos modulos.")

    with closing(get_conn()) as conn:
        ensure_schema(conn)
        _enforce_password_change(conn)

        choice = st.radio(
            "Accion",
            options=["Consultar", "Crear", "Modificar", "Eliminar", "Restablecer contrasena", "Recuperacion"],
            horizontal=True,
        )

        if choice == "Consultar":
            _display_users_table(conn)
        elif choice == "Crear":
            _create_user(conn)
        elif choice == "Modificar":
            _edit_user(conn)
        elif choice == "Eliminar":
            _delete_users(conn)
        elif choice == "Restablecer contrasena":
            _reset_passwords(conn)
        elif choice == "Recuperacion":
            _manage_recovery_tokens(conn)


if __name__ == "__main__":
    main()
