"""Edición masiva de usuarios y trabajadores."""

import streamlit as st

from pages.components.admin import init_admin_section
from pages.components.usuarios import render_modificar


def main() -> None:
    conn = init_admin_section(
        page_title="Usuarios — Modificar",
        active_top="usuarios",
        active_child="modificar",
        enable_foreign_keys=True,
    )

    st.title("✏️ Editar usuarios y trabajadores")
    render_modificar(conn)


if __name__ == "__main__":
    main()
