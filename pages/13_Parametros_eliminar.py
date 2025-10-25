"""Eliminación de versiones de parámetros."""

import streamlit as st

from pages.components.admin import init_admin_section
from pages.components.parametros import render_eliminar


def main() -> None:
    conn = init_admin_section(
        page_title="Parámetros — Eliminar",
        active_top="parametros",
        active_child="eliminar",
    )

    st.title("🗑️ Eliminar versión")
    render_eliminar(conn)


if __name__ == "__main__":
    main()