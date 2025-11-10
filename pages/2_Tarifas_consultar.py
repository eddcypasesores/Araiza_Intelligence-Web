"""Consulta de tarifas por plaza."""

import streamlit as st

from pages.components.admin import init_admin_section
from pages.components.tarifas import render_consulta, select_via_plaza


def main() -> None:
    conn = init_admin_section(
        page_title="Tarifas - Consultar",
        active_top="tarifas",
        active_child="consultar",
    )

    selection = select_via_plaza(conn)
    if selection is None:
        return

    _, _, plaza_id, plaza_nombre = selection
    st.title("Consultar tarifas")
    st.caption(f"Plaza seleccionada: **{plaza_nombre}**")
    render_consulta(conn, plaza_id)


if __name__ == "__main__":
    main()
