"""Eliminación de usuarios."""

import streamlit as st

from pages.components.admin import init_admin_section
from pages.components.usuarios import render_eliminar


def main() -> None:
    conn = init_admin_section(
        page_title="Usuarios — Eliminar",
        active_top="usuarios",
        active_child="eliminar",
        enable_foreign_keys=True,
    )

    st.title("🗑️ Eliminar usuarios")
    render_eliminar(conn)


if __name__ == "__main__":
    main()
