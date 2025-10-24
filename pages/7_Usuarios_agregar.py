"""Alta de usuarios y vínculo con trabajadores."""

import streamlit as st

from pages.components.admin import init_admin_section
from pages.components.usuarios import render_alta


def main() -> None:
    conn = init_admin_section(
        page_title="Usuarios — Agregar",
        active_top="usuarios",
        active_child="agregar",
        enable_foreign_keys=True,
    )

    st.title("➕ Alta de usuario y trabajador")
    render_alta(conn)


if __name__ == "__main__":
    main()
