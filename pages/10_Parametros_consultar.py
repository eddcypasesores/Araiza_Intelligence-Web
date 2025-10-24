"""Consulta de versiones de parámetros de costeo."""

import streamlit as st

from pages.components.admin import init_admin_section
from pages.components.parametros import render_consultar


def main() -> None:
    conn = init_admin_section(
        page_title="Parámetros — Consultar",
        active_top="parametros",
        active_child="consultar",
    )

    st.title("📊 Consultar versiones de parámetros")
    render_consultar(conn)


if __name__ == "__main__":
    main()
