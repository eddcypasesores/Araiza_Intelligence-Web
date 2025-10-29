"""Eliminación de trabajadores."""

from __future__ import annotations

import streamlit as st

from core.streamlit_compat import rerun
from pages.components.admin import init_admin_section


def main() -> None:
    conn = init_admin_section(
        page_title="Trabajadores — Eliminar",
        active_top="trabajadores",
        active_child="eliminar",
        layout="wide",
        show_inicio=False,
    )

    st.title("Eliminar trabajadores")
    trabajadores = conn.execute(
        "SELECT id, nombres, apellido_paterno, numero_economico FROM trabajadores ORDER BY nombres COLLATE NOCASE"
    ).fetchall()

    if not trabajadores:
        st.info("No hay trabajadores registrados.")
        return

    opciones: dict[str, int] = {}
    for trabajador_id, nombres, apellido_paterno, numero_economico in trabajadores:
        etiqueta = f"{nombres} {apellido_paterno} ({numero_economico or 'sin numero'})"
        opciones[etiqueta] = trabajador_id

    seleccion = st.multiselect("Selecciona trabajadores a eliminar", list(opciones.keys()))

    if not seleccion:
        return

    if st.button("Eliminar seleccionados", type="primary", use_container_width=True):
        try:
            ids = [opciones[label] for label in seleccion]
            conn.executemany("DELETE FROM trabajadores WHERE id=?", [(i,) for i in ids])
            conn.commit()
            st.success("Trabajadores eliminados correctamente.")
            rerun()
        except Exception as exc:
            st.error(f"No fue posible eliminar trabajadores: {exc}")


if __name__ == "__main__":
    main()
