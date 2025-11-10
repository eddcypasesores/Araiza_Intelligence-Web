"""Edición de trabajadores."""

from __future__ import annotations

from datetime import date

import pandas as pd
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


def _format_db_error(exc: Exception) -> str:
    text = str(exc)
    if "UNIQUE constraint failed" in text and "numero_economico" in text:
        return "No se pudo actualizar: el número económico ya está registrado."
    if "UNIQUE constraint failed" in text:
        return "No se pudo actualizar (registro duplicado)."
    return f"No fue posible actualizar el trabajador: {text}"


def _load_trabajadores(conn):
    return pd.read_sql_query(
        """
        SELECT id, nombres, apellido_paterno, apellido_materno, edad, rol_trabajador, numero_economico, fecha_registro, salario_diario
        FROM trabajadores
        ORDER BY nombres COLLATE NOCASE
        """,
        conn,
    )


def _update_trabajador(conn, trabajador_id: int, **kwargs) -> None:
    nombre_legacy = " ".join(
        part.strip()
        for part in (kwargs.get("nombres", ""), kwargs.get("apellido_paterno", ""), kwargs.get("apellido_materno", ""))
        if str(part).strip()
    ).strip() or kwargs.get("nombres", "") or "SIN NOMBRE"

    conn.execute(
        """
        UPDATE trabajadores
        SET nombre=?, nombres=?, apellido_paterno=?, apellido_materno=?, edad=?, rol_trabajador=?, numero_economico=?, fecha_registro=?, salario_diario=?
        WHERE id=?
        """,
        (
            nombre_legacy,
            kwargs["nombres"],
            kwargs["apellido_paterno"],
            kwargs["apellido_materno"],
            kwargs["edad"],
            kwargs["rol_trabajador"],
            kwargs["numero_economico"],
            kwargs["fecha_registro"],
            kwargs["salario_diario"],
            trabajador_id,
        ),
    )
    conn.commit()


def main() -> None:
    conn = init_admin_section(
        page_title="Trabajadores — Modificar",
        active_top="trabajadores",
        active_child="modificar",
        layout="wide",
        show_inicio=False,
    )

    st.title("Modificar trabajador")
    df = _load_trabajadores(conn)
    if df.empty:
        st.info("No hay trabajadores registrados.")
        return

    opciones = {
        f"{row.nombres} {row.apellido_paterno} ({row.numero_economico or 'sin numero'})": row
        for row in df.itertuples(index=False)
    }
    etiqueta = st.selectbox("Selecciona trabajador", list(opciones.keys()))
    registro = opciones[etiqueta]

    try:
        fecha_default = pd.to_datetime(registro.fecha_registro).date() if registro.fecha_registro else date.today()
    except Exception:
        fecha_default = date.today()

    with st.form("editar_trabajador", clear_on_submit=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            nombres = st.text_input("Nombre(s)*", value=registro.nombres or "").strip()
            edad = st.number_input("Edad*", min_value=16, max_value=90, value=int(registro.edad or 0), step=1)
            numero_economico = st.text_input("Numero económico", value=registro.numero_economico or "").strip().upper()
        with col2:
            apellido_paterno = st.text_input("Apellido paterno*", value=registro.apellido_paterno or "").strip()
            rol_trabajador = st.text_input("Rol / puesto*", value=registro.rol_trabajador or "").strip()
            fecha_registro = st.date_input("Fecha de registro*", value=fecha_default)
        with col3:
            apellido_materno = st.text_input("Apellido materno*", value=registro.apellido_materno or "").strip()
            salario_diario = st.number_input("Salario diario (MXN)*", min_value=0.0, value=float(registro.salario_diario or 0.0), step=10.0, format="%.2f")

        submitted = st.form_submit_button("Guardar cambios", use_container_width=True)

    if not submitted:
        return

    faltantes = [
        label
        for label, value in [
            ("Nombre(s)", nombres),
            ("Apellido paterno", apellido_paterno),
            ("Apellido materno", apellido_materno),
            ("Rol", rol_trabajador),
        ]
        if not value
    ]
    if faltantes:
        st.error("Faltan datos obligatorios: " + ", ".join(faltantes))
        return
    if salario_diario <= 0:
        st.error("El salario diario debe ser mayor a cero.")
        return

    try:
        _update_trabajador(
            conn,
            registro.id,
            nombres=nombres,
            apellido_paterno=apellido_paterno,
            apellido_materno=apellido_materno,
            edad=int(edad),
            rol_trabajador=rol_trabajador,
            numero_economico=numero_economico or None,
            fecha_registro=fecha_registro.isoformat(),
            salario_diario=float(salario_diario),
        )
        _redirect_to_consulta("Trabajador actualizado correctamente.")
    except Exception as exc:
        _redirect_to_consulta(_format_db_error(exc), kind="error")


if __name__ == "__main__":
    main()
