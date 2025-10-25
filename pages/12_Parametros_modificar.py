"""Edición de parámetros de costeo."""

import streamlit as st

from pages.components.admin import init_admin_section
from pages.components.parametros import render_modificar


def main() -> None:
    conn = init_admin_section(
        page_title="Parámetros — Modificar",
        active_top="parametros",
        active_child="modificar",
    )

    st.title("✏️ Editar parámetros")
    render_modificar(conn)


if __name__ == "__main__":
    main()