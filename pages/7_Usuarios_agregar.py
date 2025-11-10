"""Alta de trabajadores."""

from __future__ import annotations

from datetime import date

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
        return "No se pudo guardar: el número económico ya está registrado."
    if "UNIQUE constraint failed" in text:
        return "No se pudo guardar (registro duplicado)."
    return f"No fue posible guardar el trabajador: {text}"


def _insert_trabajador(conn, **kwargs) -> None:
    nombre_legacy = " ".join(
        part.strip()
        for part in (kwargs.get("nombres", ""), kwargs.get("apellido_paterno", ""), kwargs.get("apellido_materno", ""))
        if str(part).strip()
    ).strip() or kwargs.get("nombres", "") or "SIN NOMBRE"

    conn.execute(
        """
        INSERT INTO trabajadores(
            nombre,
            nombres,
            apellido_paterno,
            apellido_materno,
            edad,
            rol_trabajador,
            numero_economico,
            fecha_registro,
            salario_diario
        ) VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(numero_economico) DO UPDATE SET
            nombre=excluded.nombre,
            nombres=excluded.nombres,
            apellido_paterno=excluded.apellido_paterno,
            apellido_materno=excluded.apellido_materno,
            edad=excluded.edad,
            rol_trabajador=excluded.rol_trabajador,
            fecha_registro=excluded.fecha_registro,
            salario_diario=excluded.salario_diario
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
        ),
    )
    conn.commit()


def main() -> None:
    conn = init_admin_section(
        page_title="Trabajadores — Agregar",
        active_top="trabajadores",
        active_child="agregar",
        layout="wide",
        show_inicio=False,
    )

    st.title("Registrar trabajador")

    with st.form("alta_trabajador", clear_on_submit=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            nombres = st.text_input("Nombre(s)*").strip()
            edad = st.number_input("Edad*", min_value=16, max_value=90, value=30, step=1)
            numero_economico = st.text_input("Número económico*").strip().upper()
        with col2:
            apellido_paterno = st.text_input("Apellido paterno*").strip()
            rol_trabajador = st.text_input("Rol / puesto*").strip()
            fecha_registro = st.date_input("Fecha de registro*", value=date.today())
        with col3:
            apellido_materno = st.text_input("Apellido materno*").strip()
            salario_diario = st.number_input("Salario diario (MXN)*", min_value=0.0, value=0.0, step=10.0, format="%.2f")

        submitted = st.form_submit_button("Guardar trabajador", use_container_width=True)

    if not submitted:
        return

    faltantes = [
        label
        for label, value in [
            ("Nombre(s)", nombres),
            ("Apellido paterno", apellido_paterno),
            ("Apellido materno", apellido_materno),
            ("Rol", rol_trabajador),
            ("Número económico", numero_economico),
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
        _insert_trabajador(
            conn,
            nombres=nombres,
            apellido_paterno=apellido_paterno,
            apellido_materno=apellido_materno,
            edad=int(edad),
            rol_trabajador=rol_trabajador,
            numero_economico=numero_economico,
            fecha_registro=fecha_registro.isoformat(),
            salario_diario=float(salario_diario),
        )
        _redirect_to_consulta("Trabajador registrado correctamente.")
    except Exception as exc:
        _redirect_to_consulta(_format_db_error(exc), kind="error")


if __name__ == "__main__":
    main()
