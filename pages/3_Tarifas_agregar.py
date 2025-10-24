"""Alta de tarifas por plaza."""

import streamlit as st

from pages.components.admin import init_admin_section
from pages.components.tarifas import render_agregar, select_via_plaza


def main() -> None:
    conn = init_admin_section(
        page_title="Tarifas — Agregar",
        active_top="tarifas",
        active_child="agregar",
    )

    selection = select_via_plaza(conn)
    if selection is None:
        return

    _, via_nombre, plaza_id, plaza_nombre = selection
    st.title("➕ Agregar tarifa")
    st.caption(f"Vía seleccionada: **{via_nombre}** · Plaza: **{plaza_nombre}**")
    render_agregar(conn, plaza_id)


if __name__ == "__main__":
    main()
