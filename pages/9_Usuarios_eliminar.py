"""Eliminación de trabajadores."""

from __future__ import annotations

import streamlit as st

from core.flash import set_flash
from pages.components.admin import init_admin_section

CONSULT_PAGE = "pages/6_Usuarios_consultar.py"


def _redirect_to_consulta(message: str, *, kind: str = "success") -> None:
    set_flash(message, kind=kind)
    try:
        st.switch_page(CONSULT_PAGE)
    except Exception:
        renderer = {
            "success": st.success,
            "info": st.info,
            "warning": st.warning,
            "error": st.error,
        }.get(kind, st.info)
        renderer(message)
        st.stop()


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
            count = len(ids)
            if count == 1:
                message = "Trabajador eliminado correctamente."
            else:
                message = f"{count} trabajadores eliminados correctamente."
            _redirect_to_consulta(message)
        except Exception as exc:
            _redirect_to_consulta(f"No fue posible eliminar trabajadores: {exc}", kind="error")


if __name__ == "__main__":
    main()
