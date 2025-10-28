"""Funciones compartidas para la administración de usuarios y trabajadores."""

from __future__ import annotations

import sqlite3
from typing import Iterable

import pandas as pd
import streamlit as st

from core.db import get_usuario, set_usuario_trabajador


def _cols_trabajadores(conn) -> set[str]:
    return {r[1] for r in conn.execute("PRAGMA table_info(trabajadores)").fetchall()}


def rol_to_ui(rol_bd: str) -> str:
    return "Administrador" if (rol_bd or "").lower() == "admin" else "Calculadora de costos"


def rol_to_db(rol_ui: str) -> str:
    return "admin" if rol_ui == "Administrador" else "operador"


def render_consulta(conn) -> None:
    sql = """
    SELECT
      u.username         AS Usuario,
      u.rol              AS rol_bd,
      t.nombres          AS "Nombre(s)",
      t.apellido_paterno AS "Apellido paterno",
      t.apellido_materno AS "Apellido materno",
      t.rol_trabajador   AS "Rol del trabajador",
      t.numero_economico AS "Número económico",
      t.fecha_registro   AS "Fecha registro",
      t.salario_diario   AS "Salario diario (MXN)"
    FROM usuarios u
    LEFT JOIN usuario_trabajador ut ON ut.usuario_id = u.id
    LEFT JOIN trabajadores t        ON t.id = ut.trabajador_id
    ORDER BY u.username
    """
    df = pd.read_sql_query(sql, conn)
    if df.empty:
        st.info("No hay usuarios registrados.")
        return

    df.insert(1, "Tipo de usuario", df.pop("rol_bd").apply(rol_to_ui))
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_alta(conn) -> None:
    st.markdown("**Datos de acceso**")
    cu1, cu2, cu3 = st.columns([1.2, 1.2, 1.0])
    with cu1:
        nuevo_user = st.text_input("Usuario*").strip()
    with cu2:
        nuevo_pass = st.text_input("Contraseña*", type="password")
    with cu3:
        tipo_usuario = st.selectbox(
            "Tipo de usuario*",
            ["Administrador", "Calculadora de costos"],
            help="Define permisos: Administrador (gestiona todo) / Calculadora de costos (solo usa la calculadora).",
        )
    rol_bd = "admin" if tipo_usuario == "Administrador" else "operador"

    st.markdown("**Datos del trabajador**")
    ct1, ct2, ct3 = st.columns([1.2, 1.2, 1.0])
    with ct1:
        nombres = st.text_input("Nombre(s)*").strip()
        apellido_paterno = st.text_input("Apellido Paterno*").strip()
        apellido_materno = st.text_input("Apellido Materno*").strip()
    with ct2:
        edad = st.number_input("Edad*", min_value=16, max_value=90, value=30, step=1)
        rol_trabajador = st.text_input("Rol (p. ej. Operador)*").strip()
        numero_economico = st.text_input("Número Económico*").strip()
    with ct3:
        fecha_registro = st.date_input("Fecha de Registro*", help="Se usa para calcular la antigüedad.")
        salario_diario = st.number_input(
            "Salario diario (MXN)*",
            min_value=0.0,
            value=0.0,
            step=10.0,
            format="%.2f",
        )

    submitted = st.button("Crear / Actualizar y Vincular", type="primary")
    if not submitted:
        return

    faltantes: list[str] = []
    if not nuevo_user:
        faltantes.append("Usuario")
    if not nuevo_pass:
        faltantes.append("Contraseña")
    if not nombres:
        faltantes.append("Nombre(s)")
    if not apellido_paterno:
        faltantes.append("Apellido Paterno")
    if not apellido_materno:
        faltantes.append("Apellido Materno")
    if not rol_trabajador:
        faltantes.append("Rol del trabajador")
    if not numero_economico:
        faltantes.append("Número Económico")
    if float(salario_diario) <= 0:
        faltantes.append("Salario diario (> 0)")

    if faltantes:
        st.error("Faltan/son inválidos: " + ", ".join(faltantes))
        return

    try:
        cur = conn.cursor()
        cur.execute("BEGIN")

        cur.execute(
            """
            INSERT INTO usuarios(username, password, rol)
            VALUES (?,?,?)
            ON CONFLICT(username) DO UPDATE SET
              password=excluded.password,
              rol=excluded.rol
            """,
            (nuevo_user, nuevo_pass, rol_bd),
        )

        cols = _cols_trabajadores(conn)
        nombre_legacy = f"{nombres} {apellido_paterno} {apellido_materno}".strip()
        salario_mensual_legacy = float(salario_diario) * 30.4
        imss_pct = 0.41
        carga_social_pct = 0.05
        aguinaldo_dias = 15.0
        prima_vacacional_pct = 0.25
        horas_por_dia = 9.0
        dias_laborales_mes = 26.0

        col_names: list[str] = [
            "nombres",
            "apellido_paterno",
            "apellido_materno",
            "edad",
            "rol_trabajador",
            "numero_economico",
            "fecha_registro",
            "salario_diario",
        ]
        values: list[object] = [
            nombres,
            apellido_paterno,
            apellido_materno,
            int(edad),
            rol_trabajador,
            numero_economico,
            str(fecha_registro),
            float(salario_diario),
        ]

        def _append_if(col: str, value: object) -> None:
            if col in cols:
                col_names.append(col)
                values.append(value)

        _append_if("nombre", nombre_legacy)
        _append_if("salario_mensual", salario_mensual_legacy)
        _append_if("imss_pct", imss_pct)
        _append_if("carga_social_pct", carga_social_pct)
        _append_if("aguinaldo_dias", aguinaldo_dias)
        _append_if("prima_vacacional_pct", prima_vacacional_pct)
        _append_if("horas_por_dia", horas_por_dia)
        _append_if("dias_laborales_mes", dias_laborales_mes)

        placeholders = ",".join(["?"] * len(col_names))
        cols_sql = ",".join(col_names)
        set_sql = ", ".join([f"{c}=excluded.{c}" for c in col_names if c != "numero_economico"])

        cur.execute(
            f"""
            INSERT INTO trabajadores({cols_sql})
            VALUES ({placeholders})
            ON CONFLICT(numero_economico) DO UPDATE SET
              {set_sql}
            """,
            values,
        )

        uid = cur.execute("SELECT id FROM usuarios WHERE username=?", (nuevo_user,)).fetchone()[0]
        tid = cur.execute(
            "SELECT id FROM trabajadores WHERE numero_economico=?",
            (numero_economico,),
        ).fetchone()[0]
        cur.execute(
            """
            INSERT INTO usuario_trabajador(usuario_id, trabajador_id)
            VALUES (?, ?)
            ON CONFLICT(usuario_id) DO UPDATE SET trabajador_id=excluded.trabajador_id
            """,
            (uid, tid),
        )

        conn.commit()
        st.success("Usuario y trabajador creados/actualizados y vinculados ✅")
    except sqlite3.IntegrityError as e:
        conn.rollback()
        st.error(f"No se pudo crear/actualizar: {e}")
    except Exception as e:
        conn.rollback()
        st.error(f"Error inesperado: {e}")


def _iter_rows(df: pd.DataFrame) -> Iterable[pd.Series]:
    for _, row in df.iterrows():
        yield row


def render_modificar(conn) -> None:
    sql = """
    SELECT
      u.id               AS usuario_id,
      u.username         AS usuario,
      u.password         AS contrasena,
      u.rol              AS rol_bd,
      t.id               AS trabajador_id,
      t.nombres,
      t.apellido_paterno,
      t.apellido_materno,
      t.edad,
      t.rol_trabajador,
      t.numero_economico,
      t.fecha_registro,
      t.salario_diario
    FROM usuarios u
    LEFT JOIN usuario_trabajador ut ON ut.usuario_id = u.id
    LEFT JOIN trabajadores t        ON t.id = ut.trabajador_id
    ORDER BY u.username
    """
    df = pd.read_sql_query(sql, conn)

    df["Tipo de usuario"] = df["rol_bd"].apply(rol_to_ui)

    edited = st.data_editor(
        df[[
            "usuario_id",
            "usuario",
            "contrasena",
            "Tipo de usuario",
            "trabajador_id",
            "nombres",
            "apellido_paterno",
            "apellido_materno",
            "edad",
            "rol_trabajador",
            "numero_economico",
            "fecha_registro",
            "salario_diario",
        ]],
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "usuario_id": st.column_config.NumberColumn("UsuarioID", disabled=True),
            "usuario": st.column_config.TextColumn("Usuario"),
            "contrasena": st.column_config.TextColumn("Contraseña"),
            "Tipo de usuario": st.column_config.SelectboxColumn(
                "Tipo de usuario",
                options=["Administrador", "Calculadora de costos"],
            ),
            "trabajador_id": st.column_config.NumberColumn("TrabajadorID", disabled=True),
            "nombres": st.column_config.TextColumn("Nombre(s)"),
            "apellido_paterno": st.column_config.TextColumn("Apellido Paterno"),
            "apellido_materno": st.column_config.TextColumn("Apellido Materno"),
            "edad": st.column_config.NumberColumn("Edad", min_value=16, max_value=90, step=1),
            "rol_trabajador": st.column_config.TextColumn("Rol"),
            "numero_economico": st.column_config.TextColumn("Número Económico"),
            "fecha_registro": st.column_config.TextColumn("Fecha de Registro (YYYY-MM-DD)"),
            "salario_diario": st.column_config.NumberColumn("Salario diario (MXN)", format="%.2f"),
        },
        key="editor_usuarios_trabajadores",
    )

    if not st.button("💾 Guardar cambios", type="primary"):
        return

    try:
        cur = conn.cursor()
        cur.execute("BEGIN")
        for row in _iter_rows(edited):
            u = (row.get("usuario") or "").strip()
            p = (row.get("contrasena") or "")
            rol_ui = row.get("Tipo de usuario") or "Calculadora de costos"
            rol_bd = rol_to_db(rol_ui)

            if not u or not p:
                st.error("Usuario y Contraseña son obligatorios en todas las filas.")
                continue

            cur.execute(
                """
                INSERT INTO usuarios(username, password, rol)
                VALUES (?,?,?)
                ON CONFLICT(username) DO UPDATE SET
                  password=excluded.password,
                  rol=excluded.rol
                """,
                (u, p, rol_bd),
            )

            nombres = (row.get("nombres") or "").strip()
            ap_pat = (row.get("apellido_paterno") or "").strip()
            ap_mat = (row.get("apellido_materno") or "").strip()
            rol_trab = (row.get("rol_trabajador") or "").strip()
            numeco = (row.get("numero_economico") or "").strip()
            fec = (row.get("fecha_registro") or "").strip()
            saldia = float(row.get("salario_diario") or 0.0)
            edad_val = int(row.get("edad") or 0)

            if all([nombres, ap_pat, ap_mat, rol_trab, numeco, fec]) and saldia > 0:
                cur.execute(
                    """
                    INSERT INTO trabajadores(
                        nombres, apellido_paterno, apellido_materno, edad, rol_trabajador,
                        numero_economico, fecha_registro, salario_diario
                    ) VALUES (?,?,?,?,?,?,?,?)
                    ON CONFLICT(numero_economico) DO UPDATE SET
                        nombres=excluded.nombres,
                        apellido_paterno=excluded.apellido_paterno,
                        apellido_materno=excluded.apellido_materno,
                        edad=excluded.edad,
                        rol_trabajador=excluded.rol_trabajador,
                        fecha_registro=excluded.fecha_registro,
                        salario_diario=excluded.salario_diario
                    """,
                    (nombres, ap_pat, ap_mat, edad_val, rol_trab, numeco, fec, saldia),
                )

                uid = get_usuario(conn, u)[0]
                tid = cur.execute(
                    "SELECT id FROM trabajadores WHERE numero_economico=?",
                    (numeco,),
                ).fetchone()[0]
                set_usuario_trabajador(conn, u, tid)

        conn.commit()
        st.success("Cambios guardados ✅")
    except sqlite3.IntegrityError as e:
        conn.rollback()
        st.error(f"No se pudieron guardar los cambios: {e}")
    except Exception as e:
        conn.rollback()
        st.error(f"Error inesperado: {e}")


def render_eliminar(conn) -> None:
    todos = pd.read_sql_query(
        "SELECT username FROM usuarios ORDER BY username",
        conn,
    )["username"].tolist()
    if not todos:
        st.info("No hay usuarios registrados para eliminar.")
        return

    seleccion = st.multiselect(
        "Selecciona usuarios a eliminar",
        options=todos,
        help="Elimina el usuario y su vínculo con trabajador (no borra al trabajador).",
    )
    usuario_actual = st.session_state["usuario"]

    if st.button(
        "Eliminar seleccionados",
        type="primary",
        disabled=len(seleccion) == 0,
    ):
        if usuario_actual in seleccion:
            st.error(f"No puedes eliminar tu propio usuario activo ({usuario_actual}).")
            return
        try:
            cur = conn.cursor()
            cur.execute("BEGIN")
            for u in seleccion:
                cur.execute(
                    "DELETE FROM usuario_trabajador WHERE usuario_id = (SELECT id FROM usuarios WHERE username=?)",
                    (u,),
                )
                cur.execute("DELETE FROM usuarios WHERE username=?", (u,))
            conn.commit()
            st.success(f"Usuarios eliminados: {', '.join(seleccion)} ✅")
            st.rerun()
        except Exception as e:
            conn.rollback()
            st.error(f"No se pudieron eliminar: {e}")
    st.caption(
        "El trabajador permanece en el catálogo. Si deseas borrarlo, hazlo desde la BD o añade un módulo de eliminación de trabajadores.",
    )
    