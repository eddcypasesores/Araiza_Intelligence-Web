"""Consulta de usuarios y sus trabajadores asociados."""

import streamlit as st

from pages.components.admin import init_admin_section
from pages.components.usuarios import render_consulta


def main() -> None:
    conn = init_admin_section(
        page_title="Usuarios — Consultar",
        active_top="usuarios",
        active_child="consultar",
        enable_foreign_keys=True,
    )

    st.title("📋 Consultar usuarios y trabajadores")
    render_consulta(conn)


if __name__ == "__main__":
    main()