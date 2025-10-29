"""Consulta de trabajadores registrados."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pages.components.admin import init_admin_section


def main() -> None:
    conn = init_admin_section(
        page_title="Trabajadores — Consultar",
        active_top="trabajadores",
        active_child="consultar",
        layout="wide",
        show_inicio=False,
    )

    st.title("Consultar trabajadores")

    df = pd.read_sql_query(
        """
        SELECT
            nombres AS "Nombre(s)",
            apellido_paterno AS "Apellido paterno",
            apellido_materno AS "Apellido materno",
            edad AS "Edad",
            rol_trabajador AS "Rol",
            numero_economico AS "Numero económico",
            fecha_registro AS "Fecha de registro",
            salario_diario AS "Salario diario (MXN)"
        FROM trabajadores
        ORDER BY nombres COLLATE NOCASE
        """,
        conn,
    )

    if df.empty:
        st.info("No hay trabajadores registrados.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
