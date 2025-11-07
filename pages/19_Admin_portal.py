"""Administracion central de usuarios y permisos del portal."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import timezone
from typing import Sequence

import streamlit as st

from core.db import (
    ensure_schema,
    get_conn,
    portal_create_reset_token,
    portal_create_user,
    portal_delete_users,
    portal_list_pending_resets,
    portal_list_permissions,
    portal_list_users,
    portal_revoke_reset_tokens,
    portal_set_password,
    portal_update_user,
)
from core.portal_admin_ui import enforce_super_admin_password_change, require_super_admin
import streamlit.components.v1 as components
from core.navigation import render_nav
from core.streamlit_compat import rerun, set_query_params


def _render_feedback_modal(level: str, message: str) -> None:
    _render_feedback_toast(level, message)

def _render_feedback_toast(level: str, message: str) -> None:
    bg_color = "#0f766e" if level == "success" else "#b91c1c"
    icon = "&#10003;" if level == "success" else "&#9888;"
    title = "Movimiento exitoso" if level == "success" else "Error al procesar"
    components.html(
        f"""
        <style>
        #admin-toast {{
            position: fixed;
            top: 96px;
            right: 32px;
            background: #ffffff;
            border-radius: 18px;
            min-width: 280px;
            max-width: 360px;
            padding: 18px 22px;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.25);
            font-family: "Inter","Segoe UI",sans-serif;
            border: 1px solid rgba(15, 23, 42, 0.12);
            z-index: 9999;
            opacity: 1;
            transition: opacity 0.4s ease, transform 0.4s ease;
        }}
        #admin-toast.hide {{
            opacity: 0;
            transform: translateY(-16px);
        }}
        #admin-toast h3 {{
            margin: 0 0 8px;
            font-size: 1rem;
            color: #0f172a;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        #admin-toast p {{
            margin: 0;
            color: #475569;
            font-size: 0.92rem;
            line-height: 1.4;
        }}
        </style>
        <div id="admin-toast">
          <h3><span style="font-size:1.2rem;">{icon}</span> {title}</h3>
          <p>{message}</p>
        </div>
        <script>
        (function() {{
          const toast = document.getElementById("admin-toast");
          if (toast) {{
            toast.style.borderTop = "4px solid {bg_color}";
          }}
          setTimeout(function() {{
            const node = document.getElementById("admin-toast");
            if (node) {{
              node.classList.add("hide");
              setTimeout(function() {{ node.remove(); }}, 500);
            }}
          }}, 3200);
        }})();
        </script>
        """,
        height=120,
        scrolling=False,
    )

_MODULE_LABEL_OVERRIDES = {
    "traslados": "Traslados",
    "riesgos": "Monitoreo especializado de EFOS",
    "admin": "Administracion",
    "diot": "DIOT",
}


def _module_label(value: str) -> str:
    label = _MODULE_LABEL_OVERRIDES.get(value)
    if label:
        return label
    cleaned = value.replace("_", " ").strip()
    if not cleaned:
        return "Sin nombre"
    return cleaned.title()


@dataclass(frozen=True)
class PermissionCatalog:
    options: tuple[tuple[str, str], ...]
    label_by_value: dict[str, str]
    value_by_label: dict[str, str]


def _build_permission_catalog(conn: sqlite3.Connection) -> PermissionCatalog:
    records = portal_list_permissions(conn)
    options: list[tuple[str, str]] = []
    for row in records:
        code = str(row.get("code") or "").strip().lower()
        if not code:
            continue
        label = str(row.get("label") or "").strip() or _module_label(code)
        options.append((label, code))
    options_tuple = tuple(options)
    return PermissionCatalog(
        options=options_tuple,
        label_by_value={code: label for label, code in options_tuple},
        value_by_label={label: code for label, code in options_tuple},
    )


def _parse_permissions(raw) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [str(p) for p in data if isinstance(p, str)]


def _permisos_multiselect(
    catalog: PermissionCatalog, default: Sequence[str] | None
) -> list[str]:
    if not catalog.options:
        st.info(
            "Configura al menos un permiso desde 'Administrar productos' para poder asignarlo a los usuarios."
        )
        return []

    labels = [label for label, _ in catalog.options]
    if isinstance(default, str):
        default_values = _parse_permissions(default)
    else:
        default_values = list(default or [])
    default_labels = [
        catalog.label_by_value.get(value, value) for value in default_values if value in catalog.label_by_value
    ]
    selected_labels = st.multiselect(
        "Permisos de acceso",
        options=labels,
        default=default_labels if default_labels else [],
    )
    return [catalog.value_by_label.get(label, label) for label in selected_labels if label]


def _display_users_table(conn: sqlite3.Connection, catalog: PermissionCatalog) -> None:
    df = portal_list_users(conn)
    if df.empty:
        st.info("No hay usuarios registrados.")
        return
    modal_payload = st.session_state.pop("_admin_modal", None)
    if modal_payload:
        level, message = modal_payload
        _render_feedback_modal(level, message)
    df = df.copy()
    label_map = catalog.label_by_value
    df["permisos"] = df["permisos"].apply(
        lambda raw: ", ".join(label_map.get(p, _module_label(p)) for p in _parse_permissions(raw)) or "-"
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


def _create_user(conn: sqlite3.Connection, catalog: PermissionCatalog) -> None:
    st.subheader("Crear usuario")
    if not catalog.options:
        st.info("Configura al menos un permiso en 'Administrar productos' antes de crear usuarios.")
        return
    default_codes = [catalog.options[0][1]] if catalog.options else []
    with st.form("create_portal_user", clear_on_submit=False):
        rfc = st.text_input("RFC*", placeholder="ej. ABCD800101XXX")
        regimen = st.text_input("Regimen fiscal")
        calle = st.text_input("Calle")
        colonia = st.text_input("Colonia")
        cp = st.text_input("Codigo postal")
        municipio = st.text_input("Alcaldia o municipio")
        email = st.text_input("Correo electronico")
        telefono = st.text_input("Telefono")
        permisos = _permisos_multiselect(catalog, default_codes)
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
        st.session_state["_admin_modal"] = (
            "success",
            "Usuario creado. La contrasena inicial es el mismo RFC (mayusculas).",
        )
        st.session_state["admin_portal_view"] = "Consultar"
        try:
            st.query_params.clear()
            st.query_params["view"] = "consultar"
        except Exception:
            set_query_params({"view": "consultar"})
        rerun()
    except Exception as exc:
        st.session_state["_admin_modal"] = ("error", f"No fue posible crear el usuario: {exc}")
        st.session_state["admin_portal_view"] = "Consultar"
        try:
            st.query_params.clear()
            st.query_params["view"] = "consultar"
        except Exception:
            set_query_params({"view": "consultar"})
        rerun()


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


def _edit_user(conn: sqlite3.Connection, catalog: PermissionCatalog) -> None:
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
        permisos = _permisos_multiselect(catalog, permisos_actuales)
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
        st.session_state["_admin_modal"] = ("success", "Usuario actualizado correctamente.")
        st.session_state["admin_portal_view"] = "Consultar"
        try:
            st.query_params.clear()
            st.query_params["view"] = "consultar"
        except Exception:
            set_query_params({"view": "consultar"})
        rerun()
    except Exception as exc:
        st.session_state["_admin_modal"] = ("error", f"No fue posible actualizar el usuario: {exc}")
        st.session_state["admin_portal_view"] = "Consultar"
        try:
            st.query_params.clear()
            st.query_params["view"] = "consultar"
        except Exception:
            set_query_params({"view": "consultar"})
        rerun()


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
            st.session_state["_admin_modal"] = ("success", "Usuarios eliminados.")
            st.session_state["admin_portal_view"] = "Consultar"
            try:
                st.query_params.clear()
                st.query_params["view"] = "consultar"
            except Exception:
                set_query_params({"view": "consultar"})
            rerun()
        except Exception as exc:
            st.session_state["_admin_modal"] = ("error", f"No fue posible eliminar usuarios: {exc}")
            st.session_state["admin_portal_view"] = "Consultar"
            try:
                st.query_params.clear()
                st.query_params["view"] = "consultar"
            except Exception:
                set_query_params({"view": "consultar"})
            rerun()


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
            st.session_state["_admin_modal"] = (
                "success",
                "Contrasenas restablecidas. El RFC es la contrasena temporal y deberan cambiarla en el siguiente ingreso.",
            )
            st.session_state["admin_portal_view"] = "Consultar"
            try:
                st.query_params.clear()
                st.query_params["view"] = "consultar"
            except Exception:
                set_query_params({"view": "consultar"})
            rerun()
        except Exception as exc:
            st.session_state["_admin_modal"] = ("error", f"No fue posible restablecer contrasenas: {exc}")
            st.session_state["admin_portal_view"] = "Consultar"
            try:
                st.query_params.clear()
                st.query_params["view"] = "consultar"
            except Exception:
                set_query_params({"view": "consultar"})
            rerun()


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


def main() -> None:
    st.set_page_config(page_title="Administracion del portal", layout="wide")
    require_super_admin()
    render_nav(active_top="admin_portal", show_inicio=True)

    st.title("Administracion del portal")
    st.caption("Administra cuentas de acceso y permisos para los distintos modulos.")

    with closing(get_conn()) as conn:
        ensure_schema(conn)
        enforce_super_admin_password_change(conn)
        catalog = _build_permission_catalog(conn)
        if not catalog.options:
            st.warning(
                "Aun no tienes permisos configurados. Usa la opcion 'Administrar productos' para definirlos antes de asignarlos a tus usuarios."
            )

        view_options = ["Consultar", "Crear", "Modificar", "Eliminar", "Restablecer contrasena", "Recuperacion"]
        raw_view = st.query_params.get("view")
        if isinstance(raw_view, list):
            raw_view = raw_view[-1] if raw_view else None

        current_choice = st.session_state.get("admin_portal_view")
        if current_choice not in view_options:
            current_choice = None

        if current_choice is None and isinstance(raw_view, str):
            for opt in view_options:
                if opt.lower().startswith(raw_view.lower()):
                    current_choice = opt
                    break

        if current_choice is None:
            current_choice = view_options[0]

        st.session_state.setdefault("admin_portal_view", current_choice)

        choice = st.radio(
            "Accion",
            options=view_options,
            horizontal=True,
            index=view_options.index(st.session_state["admin_portal_view"]),
            key="admin_portal_view",
        )
        choice = st.session_state["admin_portal_view"]
        try:
            st.query_params["view"] = choice.lower()
        except Exception:
            try:
                params = dict(st.query_params)
                params["view"] = choice.lower()
                set_query_params(params)
            except Exception:
                pass

        if choice == "Consultar":
            _display_users_table(conn, catalog)
        elif choice == "Crear":
            _create_user(conn, catalog)
        elif choice == "Modificar":
            _edit_user(conn, catalog)
        elif choice == "Eliminar":
            _delete_users(conn)
        elif choice == "Restablecer contrasena":
            _reset_passwords(conn)
        elif choice == "Recuperacion":
            _manage_recovery_tokens(conn)


if __name__ == "__main__":
    main()

