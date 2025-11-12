"""Herramienta para exportar XML de nómina a Excel dentro del módulo Descarga masiva."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
import unicodedata
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import handle_logout_request, render_brand_logout_nav


st.set_page_config(
    page_title="Descarga masiva | XML Nómina",
    layout="wide",
    initial_sidebar_state="collapsed",
)
handle_logout_request()

st.markdown(
    """
<style>
#MainMenu, header[data-testid="stHeader"], footer, div[data-testid="stToolbar"] {
  visibility: hidden !important;
  display: none !important;
}
.block-container {
  padding-top: 110px !important;
}
</style>
""",
    unsafe_allow_html=True,
)


def _get_params() -> dict[str, str]:
    try:
        raw = st.query_params
    except Exception:
        raw = st.experimental_get_query_params()

    flattened: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(value, list):
            value = value[-1] if value else None
        if value is None:
            continue
        flattened[key] = str(value)
    return flattened


def _redirect_to_login() -> None:
    try:
        st.query_params.update({"next": "pages/Descarga_masiva_nomina.py"})
    except Exception:
        st.experimental_set_query_params(next="pages/Descarga_masiva_nomina.py")
    try:
        st.switch_page("pages/Descarga_masiva_login.py")
    except Exception:
        st.stop()


def _back_href() -> str:
    params = {"goto": "pages/Descarga_masiva_inicio.py"}
    params.update(auth_query_params())
    query = urlencode(params, doseq=False)
    return f"?{query}"


def _handle_pending_navigation() -> None:
    params = _get_params()
    goto = params.pop("goto", None)
    if not goto:
        return
    try:
        st.query_params.clear()
        if params:
            st.query_params.update(params)
    except Exception:
        st.experimental_set_query_params(**params)
    try:
        st.switch_page(goto)
    except Exception:
        st.stop()
    st.stop()


NOMINA_NS = {"nomina12": "http://www.sat.gob.mx/nomina12"}
PERCEPCION_LABELS = {
    "001": "Sueldos y salarios",
    "002": "Aguinaldo",
    "020": "Prima Dominical",
    "028": "Comisiones",
    "045": "Asimilado a salario",
    "046": "Asimilado a salario",
}
INFONAVIT_TYPES = {"050", "051", "052", "053", "054"}
PERCEPTION_COLUMNS: tuple[str, ...] = (
    "Sueldos y salarios",
    "Asimilado a salario",
    "Aguinaldo",
    "Comisiones",
    "Prima Dominical",
)

PAYROLL_COLUMNS: tuple[str, ...] = (
    "RFC_Receptor",
    "Nombre_Receptor",
    "CURP",
    "NSS",
    "Puesto",
    "Departamento",
    "NumEmpleado",
    "TipoNomina",
    "FechaPago",
    "FechaInicialPago",
    "FechaFinalPago",
    "DiasPagados",
    "TotalPercepciones",
    "TotalDeducciones",
    "TotalOtrosPagos",
    "UUID",
    "FechaTimbrado",
    *PERCEPTION_COLUMNS,
    "Retención ISR",
    "ISR Aguinaldo",
    "Cuota IMSS",
    "Crédito Infonavit",
    "SubsidioEntregado",
    "Ajuste en Subsidio para el empleo (efectivamente entregado al trabajador)",
    "Ajuste al Subsidio Causado",
    "SubsidioCausado",
)
NUMERIC_PAYROLL_COLUMNS: tuple[str, ...] = (
    "DiasPagados",
    "TotalPercepciones",
    "TotalDeducciones",
    "TotalOtrosPagos",
    *PERCEPTION_COLUMNS,
    "Retención ISR",
    "ISR Aguinaldo",
    "Cuota IMSS",
    "Crédito Infonavit",
    "SubsidioEntregado",
    "Ajuste en Subsidio para el empleo (efectivamente entregado al trabajador)",
    "Ajuste al Subsidio Causado",
    "SubsidioCausado",
)
DATE_COLUMNS: tuple[str, ...] = ("FechaPago", "FechaInicialPago", "FechaFinalPago", "FechaTimbrado")


def _to_decimal(value: str | None) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _local_name(tag: str | None) -> str:
    if not tag:
        return ""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find_child(parent: ET.Element | None, local_name: str) -> ET.Element | None:
    if parent is None:
        return None
    for child in parent:
        if _local_name(child.tag) == local_name:
            return child
    return None


def _iter_children(parent: ET.Element | None, local_name: str) -> list[ET.Element]:
    if parent is None:
        return []
    return [child for child in parent if _local_name(child.tag) == local_name]


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _resolve_perception_label(percepcion: ET.Element) -> str | None:
    tipo = percepcion.attrib.get("TipoPercepcion")
    label = PERCEPCION_LABELS.get(tipo)
    if label:
        return label
    concepto = _normalize_text(percepcion.attrib.get("Concepto"))
    if "comision" in concepto:
        return "Comisiones"
    if "asimil" in concepto:
        return "Asimilado a salario"
    if "prima dominical" in concepto:
        return "Prima Dominical"
    if "aguinaldo" in concepto:
        return "Aguinaldo"
    return None


def parse_cfdi_xml(file_bytes: bytes) -> tuple[dict[str, str | float | None], list[dict[str, str | None]]]:
    """Parsea un CFDI 4.0 y regresa encabezado y conceptos."""

    root = ET.fromstring(file_bytes)

    receptor_node = _find_child(root, "Receptor")
    receptor = receptor_node.attrib if receptor_node is not None else {}

    complemento_node = _find_child(root, "Complemento")
    tfd_node = _find_child(complemento_node, "TimbreFiscalDigital")
    tfd = tfd_node.attrib if tfd_node is not None else {}

    nomina_node = _find_child(complemento_node, "Nomina")
    if nomina_node is None and complemento_node is not None:
        # Compatibilidad con prefijos distintos (nomina, nomina12, etc.)
        for child in complemento_node:
            if _local_name(child.tag).lower().startswith("nomina"):
                nomina_node = child
                break
    nomina_receptor = _find_child(nomina_node, "Receptor")

    payroll_row: dict[str, str | float | None] = {col: None for col in PAYROLL_COLUMNS}
    payroll_row["RFC_Receptor"] = receptor.get("Rfc")
    payroll_row["Nombre_Receptor"] = receptor.get("Nombre")
    payroll_row["UUID"] = tfd.get("UUID")
    payroll_row["FechaTimbrado"] = tfd.get("FechaTimbrado")

    if nomina_node is not None:
        payroll_row["TipoNomina"] = nomina_node.attrib.get("TipoNomina")
        payroll_row["FechaPago"] = nomina_node.attrib.get("FechaPago")
        payroll_row["FechaInicialPago"] = nomina_node.attrib.get("FechaInicialPago")
        payroll_row["FechaFinalPago"] = nomina_node.attrib.get("FechaFinalPago")
        payroll_row["DiasPagados"] = nomina_node.attrib.get("NumDiasPagados")
        payroll_row["TotalPercepciones"] = nomina_node.attrib.get("TotalPercepciones")
        payroll_row["TotalDeducciones"] = nomina_node.attrib.get("TotalDeducciones")
        payroll_row["TotalOtrosPagos"] = nomina_node.attrib.get("TotalOtrosPagos")

        if nomina_receptor is not None:
            payroll_row["CURP"] = nomina_receptor.attrib.get("Curp")
            payroll_row["NSS"] = nomina_receptor.attrib.get("NumSeguridadSocial")
            payroll_row["Puesto"] = nomina_receptor.attrib.get("Puesto")
            payroll_row["Departamento"] = nomina_receptor.attrib.get("Departamento")
            payroll_row["NumEmpleado"] = nomina_receptor.attrib.get("NumEmpleado")

        percepcion_totals = {label: 0.0 for label in PERCEPTION_COLUMNS}
        percepciones_node = _find_child(nomina_node, "Percepciones")
        if percepciones_node is not None:
            for percepcion in _iter_children(percepciones_node, "Percepcion"):
                total = _to_decimal(percepcion.attrib.get("ImporteGravado")) + _to_decimal(
                    percepcion.attrib.get("ImporteExento")
                )
                label = _resolve_perception_label(percepcion)
                if label:
                    percepcion_totals[label] += total
        for label, value in percepcion_totals.items():
            payroll_row[label] = value

        ded_isr_regular = ded_isr_aguinaldo = ded_imss = ded_infonavit = 0.0
        deducciones_node = _find_child(nomina_node, "Deducciones")
        if deducciones_node is not None:
            for deduccion in _iter_children(deducciones_node, "Deduccion"):
                tipo = (deduccion.attrib.get("TipoDeduccion") or "").strip()
                concepto = (deduccion.attrib.get("Concepto") or "").lower()
                importe = _to_decimal(deduccion.attrib.get("Importe"))
                if tipo == "002" or "isr" in concepto or "retencion" in concepto:
                    if "aguinaldo" in concepto:
                        ded_isr_aguinaldo += importe
                    else:
                        ded_isr_regular += importe
                if tipo == "001" or "imss" in concepto:
                    ded_imss += importe
                if tipo in INFONAVIT_TYPES or "infonavit" in concepto:
                    ded_infonavit += importe
        payroll_row["Retención ISR"] = ded_isr_regular
        payroll_row["ISR Aguinaldo"] = ded_isr_aguinaldo
        payroll_row["Cuota IMSS"] = ded_imss
        payroll_row["Crédito Infonavit"] = ded_infonavit

        subsidio_entregado = 0.0
        subsidio_causado = 0.0
        ajuste_subsidio_entregado = 0.0
        ajuste_subsidio_causado = 0.0
        otros_pagos_node = _find_child(nomina_node, "OtrosPagos")
        if otros_pagos_node is not None:
            for otro in _iter_children(otros_pagos_node, "OtroPago"):
                tipo_otro = otro.attrib.get("TipoOtroPago")
                importe_otro = _to_decimal(otro.attrib.get("Importe"))
                if tipo_otro == "007":
                    ajuste_subsidio_entregado += importe_otro
                elif tipo_otro == "008":
                    ajuste_subsidio_causado += importe_otro
                subsidio_node = _find_child(otro, "SubsidioAlEmpleo")
                if subsidio_node is not None:
                    subsidio_entregado += _to_decimal(subsidio_node.attrib.get("SubsidioEntregado"))
                    subsidio_causado += _to_decimal(subsidio_node.attrib.get("SubsidioCausado"))
        payroll_row["SubsidioEntregado"] = subsidio_entregado
        payroll_row[
            "Ajuste en Subsidio para el empleo (efectivamente entregado al trabajador)"
        ] = ajuste_subsidio_entregado
        payroll_row["Ajuste al Subsidio Causado"] = ajuste_subsidio_causado
        payroll_row["SubsidioCausado"] = subsidio_causado

    conceptos_rows: list[dict[str, str | None]] = []
    conceptos_node = _find_child(root, "Conceptos")
    if conceptos_node is not None:
        for concepto in _iter_children(conceptos_node, "Concepto"):
            datos = concepto.attrib.copy()
            iva_base = iva_tasa = iva_importe = None
            impuestos_concepto = _find_child(concepto, "Impuestos")
            if impuestos_concepto is not None:
                traslados = _find_child(impuestos_concepto, "Traslados")
                traslado = _find_child(traslados, "Traslado")
                if traslado is not None:
                    iva_base = traslado.attrib.get("Base")
                    iva_tasa = traslado.attrib.get("TasaOCuota")
                    iva_importe = traslado.attrib.get("Importe")

            conceptos_rows.append(
                {
                    "UUID": tfd.get("UUID"),
                    "ClaveProdServ": datos.get("ClaveProdServ"),
                    "NoIdentificacion": datos.get("NoIdentificacion"),
                    "Descripcion": datos.get("Descripcion"),
                    "Cantidad": datos.get("Cantidad"),
                    "ClaveUnidad": datos.get("ClaveUnidad"),
                    "Unidad": datos.get("Unidad"),
                    "ValorUnitario": datos.get("ValorUnitario"),
                    "Importe": datos.get("Importe"),
                    "Descuento": datos.get("Descuento"),
                    "ObjetoImp": datos.get("ObjetoImp"),
                    "IVA_Base": iva_base,
                    "IVA_TasaOCuota": iva_tasa,
                    "IVA_Importe": iva_importe,
                }
            )

    return payroll_row, conceptos_rows


ensure_session_from_token()
_handle_pending_navigation()
usuario = st.session_state.get("usuario")
permisos = set(st.session_state.get("permisos") or [])

if not usuario:
    _redirect_to_login()
    st.stop()

if "descarga_masiva" not in permisos and "admin" not in permisos:
    st.error("No tienes permiso para acceder a este módulo.")
    _redirect_to_login()
    st.stop()

render_brand_logout_nav(
    "pages/Descarga_masiva_nomina.py",
    brand="Descarga masiva",
    action_label="Atrás",
    action_href=_back_href(),
)

st.title("Exportar XML Nómina a Excel")
st.caption("Sube tus CFDI de nómina y genera un Excel con encabezados y conceptos.")
st.write(
    "1. Sube uno o varios XML emitidos por el SAT.\n"
    "2. Procesaremos cada CFDI y construiremos un Excel con hojas para encabezados y conceptos."
)

xml_files = st.file_uploader(
    "Selecciona los XML de nómina",
    type=["xml"],
    accept_multiple_files=True,
)

if xml_files:
    st.success(f"Archivos cargados: {len(xml_files)}")
    registros_nomina: list[dict[str, str | float | None]] = []
    registros_conceptos: list[dict[str, str | None]] = []
    errores: list[str] = []

    for uploaded in xml_files:
        try:
            file_bytes = uploaded.read()
            resumen_nomina, conceptos = parse_cfdi_xml(file_bytes)
            registros_nomina.append(resumen_nomina)
            registros_conceptos.extend(conceptos)
        except Exception as exc:  # pragma: no cover - retroalimentación visual
            errores.append(f"{uploaded.name}: {exc}")

    if errores:
        st.warning("Algunos archivos no se pudieron procesar:\n- " + "\n- ".join(errores), icon="⚠️")

    if registros_nomina:
        df_nomina = pd.DataFrame(registros_nomina)
        for col in PAYROLL_COLUMNS:
            if col not in df_nomina.columns:
                df_nomina[col] = None
        df_nomina = df_nomina[list(PAYROLL_COLUMNS)]

        for col in NUMERIC_PAYROLL_COLUMNS:
            if col in df_nomina.columns:
                df_nomina[col] = pd.to_numeric(df_nomina[col], errors="coerce").fillna(0)

        for col in DATE_COLUMNS:
            if col in df_nomina.columns:
                df_nomina[col] = pd.to_datetime(df_nomina[col], errors="coerce")

        df_conceptos = pd.DataFrame(registros_conceptos)

        st.subheader("Resumen de nómina")
        st.dataframe(df_nomina, height=260, use_container_width=True)

        if not df_conceptos.empty:
            st.subheader("Conceptos de nómina")
            st.dataframe(df_conceptos, height=260, use_container_width=True)
        else:
            st.info("Los XML cargados no contienen conceptos para mostrar.")

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_nomina.to_excel(writer, index=False, sheet_name="Nomina")
            df_conceptos.to_excel(writer, index=False, sheet_name="Conceptos")

            ws_nomina = writer.sheets["Nomina"]
            for date_col in DATE_COLUMNS:
                if date_col in df_nomina.columns:
                    col_idx = df_nomina.columns.get_loc(date_col) + 1
                    for row_idx in range(2, len(df_nomina) + 2):
                        cell = ws_nomina.cell(row=row_idx, column=col_idx)
                        if isinstance(cell.value, pd.Timestamp):
                            cell.value = cell.value.to_pydatetime().date()
                        elif isinstance(cell.value, datetime):
                            cell.value = cell.value.date()
                        cell.number_format = "DD/MM/YYYY"

        st.download_button(
            label="Descargar Excel de nómina",
            data=output.getvalue(),
            file_name="nomina_cfdi.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        st.error("No fue posible procesar los XML cargados. Verifica los archivos e inténtalo de nuevo.")
else:
    st.info("Sube uno o varios XML para generar el Excel.", icon="ℹ️")
