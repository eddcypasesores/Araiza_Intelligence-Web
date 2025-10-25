"""Clonado de versiones de parámetros."""

import streamlit as st

from pages.components.admin import init_admin_section
from pages.components.parametros import render_agregar


def main() -> None:
    conn = init_admin_section(
        page_title="Parámetros — Agregar",
        active_top="parametros",
        active_child="agregar",
    )

    st.title("➕ Crear nueva versión")
    render_agregar(conn)


if __name__ == "__main__":
    main()