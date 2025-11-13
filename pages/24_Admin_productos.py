"""Pantalla para gestionar los productos/permisos disponibles para los usuarios."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import pandas as pd
import streamlit as st

from core.theme import apply_theme
from core.auth import ensure_session_from_token
from core.db import (
    ensure_schema,
    get_conn,
    portal_create_permission,
    portal_delete_permission,
    portal_list_permissions,
    portal_update_permission,
)
from core.navigation import render_nav
from core.portal_admin_ui import enforce_super_admin_password_change
from core.streamlit_compat import rerun


def _render_permissions_table(records: list[dict]) -> None:
    st.subheader("Permisos configurados")
    if not records:
        st.info("Aun no has configurado permisos. Usa el formulario de abajo para crear uno.")
        return

    df = pd.DataFrame.from_records(records)
    df = df.rename(
        columns={
            "label": "Nombre visible",
            "code": "Codigo interno",
            "description": "Descripcion",
            "created_at": "Creado",
            "updated_at": "Actualizado",
        }
    )
    st.dataframe(
        df[["Nombre visible", "Codigo interno", "Descripcion", "Creado", "Actualizado"]],
        use_container_width=True,
        hide_index=True,
    )


def _render_create_form(conn: sqlite3.Connection) -> None:
    st.subheader("Crear nuevo permiso")
    with st.form("create_permission", clear_on_submit=True):
        code = st.text_input(
            "Codigo interno*",
            help="Se recomienda usar palabras cortas en minusculas. Se normalizara a minusculas y guiones bajos.",
        )
        label = st.text_input("Nombre visible*")
        description = st.text_area("Descripcion (opcional)")
        submitted = st.form_submit_button("Guardar permiso", use_container_width=True)

    if not submitted:
        return

    try:
        portal_create_permission(conn, code=code, label=label, description=description)
        st.success("Permiso creado correctamente.")
        rerun()
    except ValueError as exc:
        st.error(str(exc))
    except sqlite3.IntegrityError:
        st.error("Ya existe un permiso con ese codigo o nombre visible.")
    except Exception as exc:  # pragma: no cover - UI path
        st.error(f"No fue posible crear el permiso: {exc}")


def _render_edit_section(conn: sqlite3.Connection, records: list[dict]) -> None:
    st.subheader("Editar o eliminar")
    if not records:
        st.info("Agrega un permiso para poder editarlo o eliminarlo.")
        return

    options = {f"{row['label']} ({row['code']})": row for row in records}
    selected_label = st.selectbox("Selecciona un permiso", list(options.keys()))
    current = options[selected_label]

    with st.form("update_permission", clear_on_submit=False):
        label = st.text_input("Nombre visible*", value=current.get("label") or "")
        description = st.text_area(
            "Descripcion (opcional)",
            value=current.get("description") or "",
        )
        submitted = st.form_submit_button("Actualizar permiso", use_container_width=True)

    if submitted:
        try:
            portal_update_permission(
                conn,
                current["id"],
                label=label,
                description=description,
            )
            st.success("Permiso actualizado.")
            rerun()
        except ValueError as exc:
            st.error(str(exc))
        except sqlite3.IntegrityError:
            st.error("Ya existe un permiso con ese nombre visible.")
        except Exception as exc:  # pragma: no cover - UI path
            st.error(f"No fue posible actualizar el permiso: {exc}")

    with st.form("delete_permission"):
        st.warning(
            "Al eliminar un permiso tambien se eliminara de todos los usuarios que lo tengan asignado."
        )
        confirm = st.checkbox("Confirmo que deseo eliminar este permiso")
        delete = st.form_submit_button(
            f"Eliminar {current['label']}", use_container_width=True, type="primary"
        )

    if delete:
        if not confirm:
            st.warning("Marca la casilla de confirmacion para eliminar el permiso.")
            return
        try:
            portal_delete_permission(conn, current["id"])
            st.success("Permiso eliminado.")
            rerun()
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:  # pragma: no cover - UI path
            st.error(f"No fue posible eliminar el permiso: {exc}")


def main() -> None:
    st.set_page_config(page_title="Administrar productos", layout="wide")
apply_theme()
    ensure_session_from_token()
    render_nav(active_top="admin_products", show_inicio=True)

    st.title("Administrar productos")
    st.caption(
        "Controla los permisos disponibles para asignar a tus usuarios. "
        "Crea nuevos accesos, renombra los existentes o elimina los que ya no necesites."
    )

    with closing(get_conn()) as conn:
        ensure_schema(conn)
        enforce_super_admin_password_change(conn)
        records = portal_list_permissions(conn)
        _render_permissions_table(records)
        st.divider()
        _render_create_form(conn)
        st.divider()
        _render_edit_section(conn, records)


if __name__ == "__main__":
    main()
