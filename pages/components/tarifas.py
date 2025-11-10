"""Funciones compartidas para las pantallas de administracion de tarifas."""

from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd
import streamlit as st

from core.db import CLASES


ViaSelection = Tuple[int, str, int, str]


def _clean_plaza_name(name: str) -> str:
    base = str(name or "").strip()
    if not base:
        return ""
    if "-" in base:
        base = base.split("-", 1)[0].strip()
    return base


def select_via_plaza(conn) -> Optional[ViaSelection]:
    plazas = pd.read_sql_query(
        (
            "SELECT "
            "p.id AS plaza_id, "
            "p.nombre AS plaza, "
            "COALESCE(v.id, 0) AS via_id, "
            "COALESCE(v.nombre, 'Sin via') AS via "
            "FROM plazas p "
            "LEFT JOIN vias v ON v.id = p.via_id "
            "ORDER BY p.nombre COLLATE NOCASE"
        ),
        conn,
    )
    if plazas.empty:
        st.info("No hay plazas registradas. Ejecuta primero el ETL de peajes.")
        return None

    plazas["display"] = plazas["plaza"].apply(_clean_plaza_name)

    search = st.text_input(
        "Buscar plaza",
        placeholder="Ingresa parte del nombre de la plaza",
        key="tarifas_search_plaza",
    ).strip()
    filtered = plazas
    if search:
        mask = plazas["display"].str.contains(search, case=False, na=False)
        filtered = plazas.loc[mask]
        if filtered.empty:
            st.warning("No se encontraron plazas que coincidan con la busqueda. Mostrando todas.")
            filtered = plazas

    options = [
        (
            int(row["plaza_id"]),
            str(row["display"]),
            int(row["via_id"]),
            str(row["via"]),
        )
        for _, row in filtered.iterrows()
    ]
    if not options:
        st.info("No hay plazas disponibles con ese criterio.")
        return None

    labels = [plaza for (_, plaza, _, _) in options]
    selected_label = st.selectbox("Plaza", labels)
    selected_idx = labels.index(selected_label)
    plaza_id, plaza_nombre, via_id, via_nombre = options[selected_idx]
    return via_id, via_nombre, plaza_id, plaza_nombre


def tarifas_por_plaza(conn, plaza_id: int) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT clase, tarifa_mxn FROM plaza_tarifas WHERE plaza_id=? ORDER BY clase",
        conn,
        params=(plaza_id,),
    )


def render_consulta(conn, plaza_id: int) -> None:
    tarifas = tarifas_por_plaza(conn, plaza_id)
    if tarifas.empty:
        st.info("No hay tarifas registradas para esta plaza.")
    else:
        st.dataframe(
            tarifas.sort_values("clase"),
            use_container_width=True,
            hide_index=True,
        )


def render_agregar(conn, plaza_id: int) -> None:
    tarifas = tarifas_por_plaza(conn, plaza_id)
    existentes = tarifas["clase"].tolist()
    faltantes = [c for c in CLASES if c not in existentes]
    sugerida = faltantes[0] if faltantes else (existentes[0] if existentes else "")

    with st.form("form_tarifa_add"):
        clase = st.text_input(
            "Clase",
            value=sugerida,
            help="Sugerimos utilizar las clases estandar en mayusculas.",
        ).strip().upper()
        tarifa = st.number_input("Tarifa (MXN)", min_value=0.0, step=1.0, format="%.2f")
        submitted = st.form_submit_button("Guardar tarifa", type="primary")

    if submitted:
        if not clase:
            st.error("La clase es obligatoria.")
            return
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO plaza_tarifas(plaza_id, clase, tarifa_mxn)
            VALUES(?,?,?)
            ON CONFLICT(plaza_id, clase) DO UPDATE SET tarifa_mxn=excluded.tarifa_mxn
            """,
            (plaza_id, clase, float(tarifa)),
        )
        conn.commit()
        st.success(f"Tarifa para {clase} guardada correctamente.")
        st.rerun()


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def render_modificar(conn, plaza_id: int) -> None:
    tarifas = tarifas_por_plaza(conn, plaza_id)
    df_edit = tarifas.copy()
    faltantes = [c for c in CLASES if c not in df_edit["clase"].tolist()]
    if faltantes:
        df_edit = pd.concat(
            [
                df_edit,
                pd.DataFrame({"clase": faltantes, "tarifa_mxn": [0.0] * len(faltantes)}),
            ],
            ignore_index=True,
        )
    df_edit = df_edit.sort_values("clase").reset_index(drop=True)

    edited = st.data_editor(
        df_edit,
        use_container_width=True,
        hide_index=True,
        column_config={
            "clase": st.column_config.TextColumn("Clase", disabled=True),
            "tarifa_mxn": st.column_config.NumberColumn("Tarifa (MXN)", format="%.2f"),
        },
        key=f"editor_admin_tarifas_{plaza_id}",
    )

    if st.button("Guardar cambios", type="primary"):
        cur = conn.cursor()
        for _, row in edited.iterrows():
            clase = str(row["clase"]).strip().upper()
            tarifa_val = _to_float(row.get("tarifa_mxn"))
            if not clase:
                continue
            cur.execute(
                """
                INSERT INTO plaza_tarifas(plaza_id, clase, tarifa_mxn)
                VALUES(?,?,?)
                ON CONFLICT(plaza_id, clase) DO UPDATE SET tarifa_mxn=excluded.tarifa_mxn
                """,
                (plaza_id, clase, tarifa_val),
            )
        conn.commit()
        st.success("Tarifas actualizadas.")
        st.rerun()


def render_eliminar(conn, plaza_id: int) -> None:
    tarifas = tarifas_por_plaza(conn, plaza_id)
    if tarifas.empty:
        st.info("No hay tarifas registradas para eliminar.")
        return

    clases = tarifas.sort_values("clase")["clase"].tolist()
    seleccion = st.multiselect(
        "Selecciona las clases a eliminar",
        clases,
        help="Las clases seleccionadas se eliminaran de la plaza actual.",
    )
    if st.button("Eliminar seleccionadas", type="primary", disabled=not seleccion):
        cur = conn.cursor()
        cur.executemany(
            "DELETE FROM plaza_tarifas WHERE plaza_id=? AND clase=?",
            [(plaza_id, clase) for clase in seleccion],
        )
        conn.commit()
        st.success("Tarifas eliminadas.")
        st.rerun()
