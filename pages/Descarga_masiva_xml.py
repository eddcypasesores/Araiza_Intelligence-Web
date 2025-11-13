# pages/Descarga_masiva_xml.py — Exportar CFDI (XML) a Excel
from __future__ import annotations

from datetime import datetime
from io import BytesIO
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st
from core.theme import apply_theme
from urllib.parse import urlencode

# Núcleo
from core.auth import ensure_session_from_token, auth_query_params
from core.db import get_conn
from core.custom_nav import handle_logout_request, render_brand_logout_nav

# -----------------------------------------------------------------------------
# Config + ocultar UI nativa
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Exportar CFDI XML a Excel",
    page_icon="AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_theme()
handle_logout_request()

st.markdown(
    """
<style>
#MainMenu{visibility:hidden}
header{visibility:hidden}
footer{visibility:hidden}

</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Helpers query params
# -----------------------------------------------------------------------------
def _get_params() -> dict[str, str]:
    """Return flattened query params compatible with both Streamlit APIs."""

    try:
        raw_params = st.query_params  # Streamlit >=1.31
    except Exception:
        raw_params = st.experimental_get_query_params()

    flattened: dict[str, str] = {}
    for key, value in raw_params.items():
        if isinstance(value, list):
            value = value[-1] if value else None
        if value is None:
            continue
        flattened[key] = str(value)
    return flattened

def _set_params(**kwargs) -> None:
    try:
        st.query_params.update(kwargs)
    except Exception:
        merged = _get_params()
        merged.update({k: str(v) for k, v in kwargs.items()})
        st.experimental_set_query_params(**merged)


def _back_href(target: str) -> str:
    params = {"goto": target}
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


def _to_login():
    _set_params(next="pages/Descarga_masiva_xml.py")
    try:
        st.switch_page("pages/Descarga_masiva_login.py")
    except Exception:
        st.stop()

# -----------------------------------------------------------------------------
# Auth / permisos
# -----------------------------------------------------------------------------
ensure_session_from_token()
_handle_pending_navigation()
_ = get_conn()  # si lo usas más adelante

usuario = st.session_state.get("usuario")
permisos = set(st.session_state.get("permisos") or [])
if not usuario:
    _to_login(); st.stop()

if "descarga_masiva" not in permisos and "admin" not in permisos:
    st.error("No tienes permisos para acceder a este módulo.")
    _to_login(); st.stop()

# -----------------------------------------------------------------------------
# Barra superior consistente
# -----------------------------------------------------------------------------
back_href = _back_href("pages/Descarga_masiva_inicio.py")
render_brand_logout_nav(
    "pages/Descarga_masiva_xml.py",
    brand="Descarga masiva",
    action_label="Atrás",
    action_href=back_href,
)

# -----------------------------------------------------------------------------
# === Parser CFDI (tu lógica) ===
# -----------------------------------------------------------------------------
def parse_cfdi_xml(file_bytes: bytes):
    ns = {
        "cfdi": "http://www.sat.gob.mx/cfd/4",
        "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
        "implocal": "http://www.sat.gob.mx/implocal",
    }
    root = ET.fromstring(file_bytes)

    comp = root.attrib
    emisor_node = root.find("cfdi:Emisor", ns)
    emisor = emisor_node.attrib if emisor_node is not None else {}
    receptor_node = root.find("cfdi:Receptor", ns)
    receptor = receptor_node.attrib if receptor_node is not None else {}
    complemento_node = root.find("cfdi:Complemento", ns)

    tfd_node = complemento_node.find("tfd:TimbreFiscalDigital", ns) if complemento_node is not None else None
    tfd = tfd_node.attrib if tfd_node is not None else {}

    impuestos_node = root.find("cfdi:Impuestos", ns)
    total_impuestos_trasladados = retencion_001 = retencion_002 = iva_8 = ish_importe = None
    if impuestos_node is not None:
        total_impuestos_trasladados = impuestos_node.attrib.get("TotalImpuestosTrasladados")
        rs = impuestos_node.find("cfdi:Retenciones", ns)
        if rs is not None:
            for ret in rs.findall("cfdi:Retencion", ns):
                imp = ret.attrib.get("Impuesto"); imp_importe = ret.attrib.get("Importe")
                if imp == "001": retencion_001 = imp_importe
                elif imp == "002": retencion_002 = imp_importe
        ts = impuestos_node.find("cfdi:Traslados", ns)
        if ts is not None:
            for tras in ts.findall("cfdi:Traslado", ns):
                imp = tras.attrib.get("Impuesto"); tasa = tras.attrib.get("TasaOCuota"); importe_tras = tras.attrib.get("Importe")
                if imp == "002" and tasa and tasa.startswith("0.08"): iva_8 = importe_tras

    if complemento_node is not None:
        il = complemento_node.find("implocal:ImpuestosLocales", ns)
        if il is not None:
            for loc_tr in il.findall("implocal:TrasladosLocales", ns):
                if loc_tr.attrib.get("ImpLocTrasladado") == "ISH":
                    ish_importe = loc_tr.attrib.get("Importe"); break

    encabezado_dict = {
        "Version": comp.get("Version"),
        "TipoDeComprobante": comp.get("TipoDeComprobante"),
        "Fecha": comp.get("Fecha"),
        "FechaTimbrado": tfd.get("FechaTimbrado"),

        "Emisor_Rfc": emisor.get("Rfc"),
        "Emisor_Nombre": emisor.get("Nombre"),

        "UUID": tfd.get("UUID"),
        "Serie": comp.get("Serie"),
        "Folio": comp.get("Folio"),

        "SubTotal": comp.get("SubTotal"),
        "Descuento": comp.get("Descuento"),
        "TotalImpuestosTrasladados": total_impuestos_trasladados,

        "IVA 8%": iva_8,
        "ISH": ish_importe,

        "Retencion_001": retencion_001,
        "Retencion_002": retencion_002,

        "Total": comp.get("Total"),

        "Emisor_RegimenFiscal": emisor.get("RegimenFiscal"),
        "Receptor_DomicilioFiscalReceptor": receptor.get("DomicilioFiscalReceptor"),

        "Moneda": comp.get("Moneda"),
        "FormaPago": comp.get("FormaPago"),
        "MetodoPago": comp.get("MetodoPago"),
        "CondicionesDePago": comp.get("CondicionesDePago"),
        "LugarExpedicion": comp.get("LugarExpedicion"),
        "Exportacion": comp.get("Exportacion"),

        "RfcProvCertif": tfd.get("RfcProvCertif"),
        "NoCertificado": comp.get("NoCertificado"),

        "Receptor_Rfc": receptor.get("Rfc"),
        "Receptor_Nombre": receptor.get("Nombre"),
        "Receptor_UsoCFDI": receptor.get("UsoCFDI"),
        "Receptor_RegimenFiscalReceptor": receptor.get("RegimenFiscalReceptor"),
    }

    conceptos_rows = []
    conceptos_node = root.find("cfdi:Conceptos", ns)
    if conceptos_node is not None:
        for c in conceptos_node.findall("cfdi:Concepto", ns):
            c_at = c.attrib.copy()
            iva_base = iva_tasa = iva_importe = None
            imp_node = c.find("cfdi:Impuestos", ns)
            if imp_node is not None:
                ts = imp_node.find("cfdi:Traslados", ns)
                if ts is not None:
                    tr = ts.find("cfdi:Traslado", ns)
                    if tr is not None:
                        iva_base = tr.attrib.get("Base")
                        iva_tasa = tr.attrib.get("TasaOCuota")
                        iva_importe = tr.attrib.get("Importe")

            conceptos_rows.append({
                "UUID": encabezado_dict["UUID"],
                "ClaveProdServ": c_at.get("ClaveProdServ"),
                "NoIdentificacion": c_at.get("NoIdentificacion"),
                "Descripcion": c_at.get("Descripcion"),
                "Cantidad": c_at.get("Cantidad"),
                "ClaveUnidad": c_at.get("ClaveUnidad"),
                "Unidad": c_at.get("Unidad"),
                "ValorUnitario": c_at.get("ValorUnitario"),
                "Importe": c_at.get("Importe"),
                "Descuento": c_at.get("Descuento"),
                "ObjetoImp": c_at.get("ObjetoImp"),
                "IVA_Base": iva_base,
                "IVA_TasaOCuota": iva_tasa,
                "IVA_Importe": iva_importe,
            })
    return encabezado_dict, conceptos_rows

# -----------------------------------------------------------------------------
# UI principal (subida múltiple → Excel)
# -----------------------------------------------------------------------------
st.title("Exportar CFDI (XML) a Excel")
st.write(
    "1. Sube uno o varios archivos XML del SAT.\n"
    "2. Leo cada CFDI y genero un Excel con la información."
)

xml_files = st.file_uploader(
    "Selecciona tus XML",
    type=["xml"],
    accept_multiple_files=True
)

if xml_files:
    st.success(f"Archivos cargados: {len(xml_files)}")

    registros_encabezado, registros_conceptos = [], []
    for uploaded in xml_files:
        enc, rows = parse_cfdi_xml(uploaded.read())
        registros_encabezado.append(enc)
        registros_conceptos.extend(rows)

    df_cfdIs = pd.DataFrame(registros_encabezado)

    # Numéricas + regla de IVA 8%
    cols_num = ["SubTotal","Descuento","TotalImpuestosTrasladados","IVA 8%","ISH","Retencion_001","Retencion_002","Total"]
    for c in cols_num:
        if c not in df_cfdIs.columns: df_cfdIs[c] = 0
        df_cfdIs[c] = pd.to_numeric(df_cfdIs[c], errors="coerce").fillna(0)
    df_cfdIs.loc[df_cfdIs["IVA 8%"] > 0, "TotalImpuestosTrasladados"] = 0

    # Fecha
    if "FechaTimbrado" in df_cfdIs.columns:
        df_cfdIs["FechaTimbrado"] = pd.to_datetime(df_cfdIs["FechaTimbrado"], errors="coerce")

    # Orden de columnas
    cols_pref = [
        "Version","TipoDeComprobante","Fecha","FechaTimbrado","Emisor_Rfc","Emisor_Nombre","UUID","Serie","Folio",
        "SubTotal","Descuento","TotalImpuestosTrasladados","IVA 8%","ISH","Retencion_001","Retencion_002","Total",
        "Emisor_RegimenFiscal","Receptor_DomicilioFiscalReceptor","Moneda","FormaPago","MetodoPago",
        "CondicionesDePago","LugarExpedicion","Exportacion","RfcProvCertif","NoCertificado",
        "Receptor_Rfc","Receptor_Nombre","Receptor_UsoCFDI","Receptor_RegimenFiscalReceptor",
    ]
    ordered = [c for c in cols_pref if c in df_cfdIs.columns] + [c for c in df_cfdIs.columns if c not in cols_pref]
    df_cfdIs = df_cfdIs[ordered]

    df_conceptos = pd.DataFrame(registros_conceptos)

    st.subheader("Resumen CFDIs (Encabezado por factura)")
    st.dataframe(df_cfdIs, height=260, use_container_width=True)

    st.subheader("Conceptos (Partidas)")
    st.dataframe(df_conceptos, height=260, use_container_width=True)

    # Excel en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_cfdIs.to_excel(writer, index=False, sheet_name="CFDIs")
        df_conceptos.to_excel(writer, index=False, sheet_name="Conceptos")

        # Formato dd/mm/yyyy para FechaTimbrado
        ws = writer.sheets["CFDIs"]
        if "FechaTimbrado" in df_cfdIs.columns:
            cidx = df_cfdIs.columns.get_loc("FechaTimbrado") + 1
            for r in range(2, len(df_cfdIs) + 2):
                cell = ws.cell(row=r, column=cidx)
                if isinstance(cell.value, pd.Timestamp):  # type: ignore[name-defined]
                    cell.value = cell.value.to_pydatetime().date()
                elif isinstance(cell.value, datetime):
                    cell.value = cell.value.date()
                cell.number_format = "DD/MM/YYYY"

    st.download_button(
        "DESCARGAR EXCEL",
        data=output.getvalue(),
        file_name="CFDIs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
else:
    st.info("Sube uno o varios XML para generar el Excel.")

