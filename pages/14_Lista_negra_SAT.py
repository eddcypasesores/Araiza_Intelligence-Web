"""Consulta de RFC contra la lista negra SAT.

Esta página permite cargar múltiples CFDI en formato XML para extraer
los RFC de los emisores y cruzarlos contra la lista oficial de
contribuyentes incumplidos (Firmes.csv o Excel). El usuario puede
generar un Excel con los RFC coincidentes.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from pages.components.admin import init_admin_section


# ---------------------------------------------------------------------------
# Inicialización y navegación
# ---------------------------------------------------------------------------
# Se reutiliza la utilería administrativa para validar sesión, preparar la
# navegación compartida y ofrecer una conexión SQLite (que cerramos de
# inmediato porque esta vista solo trabaja con archivos en memoria).
conn = init_admin_section(
    page_title="Lista negra SAT — Cruce de RFC",
    active_top="lista_negra_sat",
    layout="wide",
)
conn.close()


# ---------------------------------------------------------------------------
# CSS personalizado
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Contenedor principal más ancho y con menos padding arriba */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    /* Título centrado */
    h1.titulo-sat {
        text-align: center;
        font-family: Arial, sans-serif;
        font-size: 2.2rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 2rem;
    }

    /***************
     * Uploader #1 (XML CFDI)
     ***************/
    .file-upload-wrapper [data-testid="stFileUploader"] {
        border: 1px solid #d1d5db;
        background-color: #f5f7fa;
        border-radius: 8px;
        padding: 1rem 1rem;
        margin-bottom: 1rem;
    }

    .file-upload-wrapper [data-testid="stFileUploader"] section {
        padding: 0.5rem 0.75rem;
    }

    /* Ocultar la lista de archivos subidos del uploader #1 */
    .file-upload-wrapper [data-testid="uploadedFile"],
    .file-upload-wrapper [data-testid="stFileUploaderFileList"],
    .file-upload-wrapper [data-testid="stFileUploader"] section + div,
    .file-upload-wrapper [data-testid="stFileUploader"] ul,
    .file-upload-wrapper [data-testid="stFileUploader"] li,
    .file-upload-wrapper [data-testid="stFileUploader"] small {
        display: none !important;
    }

    /* Cambiar el texto del botón "Browse files" a "XML" SOLO en el uploader #1 */
    .file-upload-wrapper [data-testid="stFileUploader"] button {
        position: relative;
    }

    /* ocultamos el texto interno original */
    .file-upload-wrapper [data-testid="stFileUploader"] button * {
        color: transparent !important;
    }

    /* insertamos "XML" visualmente */
    .file-upload-wrapper [data-testid="stFileUploader"] button:after {
        content: "XML";
        position: absolute;
        left: 0;
        right: 0;
        top: 0;
        bottom: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #1e1e1e;
        font-size: 1rem;
        font-weight: 500;
    }

    /***************
     * Uploader #2 (Firmes.csv / XLS / XLSX)
     * Se muestra debajo de la tabla
     ***************/
    .lista-wrapper [data-testid="stFileUploader"] {
        border: 1px solid #d1d5db;
        background-color: #f5f7fa;
        border-radius: 8px;
        padding: 1rem 1rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }

    .lista-wrapper [data-testid="stFileUploader"] section {
        padding: 0.5rem 0.75rem;
    }

    /* Ocultar la lista de archivos subidos del uploader #2,
       pero aquí SÍ dejamos el texto del botón como "Browse files"
       (no lo sobreescribimos con CSS extra)
    */
    .lista-wrapper [data-testid="uploadedFile"],
    .lista-wrapper [data-testid="stFileUploaderFileList"],
    .lista-wrapper [data-testid="stFileUploader"] section + div,
    .lista-wrapper [data-testid="stFileUploader"] ul,
    .lista-wrapper [data-testid="stFileUploader"] li,
    .lista-wrapper [data-testid="stFileUploader"] small {
        display: none !important;
    }

    /* Título de la vista previa */
    .preview-title {
        font-family: Arial, sans-serif;
        font-size: 1.1rem;
        font-weight: 600;
        margin-top: 2rem;
        margin-bottom: 0.5rem;
    }

    /* Contenedor de la vista previa ~70% ancho */
    .preview-wrapper {
        max-width: 70%;
    }

    /* Tabla compacta */
    .stDataFrame {
        font-size: 0.7rem;
        line-height: 1.1rem;
    }

    .stDataFrame table tbody tr td,
    .stDataFrame table thead tr th {
        padding-top: 2px;
        padding-bottom: 2px;
        padding-left: 6px;
        padding-right: 6px;
    }

    /* Contenedor del botón GENERAR EXCEL debajo */
    .excel-button-box {
        width: 250px;
        margin-top: 0.75rem;
    }

    .excel-button-box div.stButton > button {
        width: 100%;
        height: 60px;
        background-color: #f2f2f2;
        color: #000000;
        border: 1px solid #000000;
        border-radius: 0px;
        font-size: 1.1rem;
        font-weight: 600;
        box-shadow: none;
    }

    .excel-button-box div.stButton > button:hover {
        background-color: #e6e6e6;
        color: #000000;
        border: 1px solid #000000;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _local_tag(tag: str) -> str:
    """Extrae el nombre local de un tag XML con namespace."""

    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_emisor_from_xml(xml_bytes: bytes) -> tuple[str | None, str | None]:
    """Obtiene (RFC, Nombre) del nodo <cfdi:Emisor> en un CFDI."""

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None, None

    for node in root.iter():
        if _local_tag(node.tag).lower() == "emisor":
            rfc = (
                node.attrib.get("Rfc")
                or node.attrib.get("RFC")
                or node.attrib.get("rfc")
            )
            nombre = (
                node.attrib.get("Nombre")
                or node.attrib.get("NOMBRE")
                or node.attrib.get("nombre")
            )
            return rfc, nombre

    return None, None


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Convierte un DataFrame a bytes XLSX en memoria."""

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Coincidencias")
    return output.getvalue()


def load_blacklist_file(file) -> pd.DataFrame:
    """Carga la lista negra SAT desde CSV o Excel normalizando la columna RFC."""

    name_lower = file.name.lower()

    if name_lower.endswith(".csv"):
        df = pd.read_csv(file, encoding="latin-1")
    elif name_lower.endswith(".xlsx") or name_lower.endswith(".xls"):
        df = pd.read_excel(file)
    else:
        df = pd.DataFrame()

    if "RFC" in df.columns:
        df["RFC"] = df["RFC"].astype(str).str.strip()

    return df


# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------
if "parsed_df" not in st.session_state:
    st.session_state.parsed_df = pd.DataFrame(
        columns=["Archivo XML", "RFC Emisor", "Nombre Emisor"]
    )

if "blacklist_df" not in st.session_state:
    st.session_state.blacklist_df = pd.DataFrame()

if "excel_ready" not in st.session_state:
    st.session_state.excel_ready = False

if "excel_bytes" not in st.session_state:
    st.session_state.excel_bytes = b""


# ---------------------------------------------------------------------------
# UI: Título principal
# ---------------------------------------------------------------------------
st.markdown(
    '<h1 class="titulo-sat">Consulta la Relación de Contribuyentes Incumplidos (Lista Negra SAT)</h1>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Uploader #1: CFDI XML
# ---------------------------------------------------------------------------
st.markdown('<div class="file-upload-wrapper">', unsafe_allow_html=True)

uploaded_xml_files = st.file_uploader(
    label="",
    type=["xml"],
    accept_multiple_files=True,
    key="xml_files",
)

st.markdown('</div>', unsafe_allow_html=True)

if uploaded_xml_files:
    rows: list[dict[str, str]] = []
    for file in uploaded_xml_files:
        file.seek(0)
        xml_bytes = file.read()
        rfc, nombre = parse_emisor_from_xml(xml_bytes)
        rows.append(
            {
                "Archivo XML": file.name,
                "RFC Emisor": (rfc or "").strip(),
                "Nombre Emisor": (nombre or "").strip(),
            }
        )

    st.session_state.parsed_df = pd.DataFrame(rows)
    st.session_state.excel_ready = False
    st.session_state.excel_bytes = b""


# ---------------------------------------------------------------------------
# Vista previa de RFCs y carga de lista negra
# ---------------------------------------------------------------------------
if not st.session_state.parsed_df.empty:
    st.markdown(
        '<div class="preview-title">Vista previa de RFC encontrados en los CFDI</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="preview-wrapper">', unsafe_allow_html=True)

    st.dataframe(
        st.session_state.parsed_df[["RFC Emisor"]],
        use_container_width=True,
        height=200,
    )

    st.markdown('<div class="lista-wrapper">', unsafe_allow_html=True)

    uploaded_blacklist_file = st.file_uploader(
        label="",
        type=["csv", "xls", "xlsx"],
        accept_multiple_files=False,
        key="blacklist_file",
    )

    st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_blacklist_file:
        uploaded_blacklist_file.seek(0)
        st.session_state.blacklist_df = load_blacklist_file(uploaded_blacklist_file)
        st.session_state.excel_ready = False
        st.session_state.excel_bytes = b""

    if not st.session_state.blacklist_df.empty:
        st.markdown('<div class="excel-button-box">', unsafe_allow_html=True)
        generar_btn = st.button("GENERAR EXCEL", key="generar_excel_btn")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        generar_btn = False
        st.info(
            "Sube el archivo Firmes.csv (lista negra SAT) para habilitar 'GENERAR EXCEL'."
        )

    if generar_btn:
        df_xml = st.session_state.parsed_df.copy()
        rfcs_xml_unicos = (
            df_xml["RFC Emisor"].astype(str).str.strip().unique().tolist()
        )

        if "RFC" not in st.session_state.blacklist_df.columns:
            st.error("El archivo de la lista negra no tiene la columna 'RFC'.")
            st.session_state.excel_ready = False
            st.session_state.excel_bytes = b""
        else:
            df_blacklist = st.session_state.blacklist_df.copy()
            df_blacklist["RFC"] = df_blacklist["RFC"].astype(str).str.strip()

            coincidencias = df_blacklist[
                df_blacklist["RFC"].isin(rfcs_xml_unicos)
            ].copy()

            if coincidencias.empty:
                st.info(
                    "No hubo coincidencias de RFC con la lista negra SAT. "
                    "Se genera Excel vacío con encabezados."
                )
                st.session_state.excel_bytes = dataframe_to_excel_bytes(
                    pd.DataFrame(columns=df_blacklist.columns)
                )
                st.session_state.excel_ready = True
            else:
                st.success(
                    f"Se encontraron {len(coincidencias)} coincidencia(s). "
                    "Ya puedes descargar el Excel."
                )
                st.session_state.excel_bytes = dataframe_to_excel_bytes(coincidencias)
                st.session_state.excel_ready = True

    if st.session_state.excel_ready and st.session_state.excel_bytes:
        st.download_button(
            label="Descargar Excel",
            data=st.session_state.excel_bytes,
            file_name="RFCs_Coinciden_Lista_Negra.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_excel_btn",
        )

    st.markdown('</div>', unsafe_allow_html=True)
