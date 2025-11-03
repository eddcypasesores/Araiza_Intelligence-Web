"""Monitoreo especializado de EFOS - Cruce de RFC contra Lista Negra SAT.

Proceso guiado en espanol con:
- Carga de CFDI en XML y parseo inmediato.
- Uso del archivo Firmes administrado desde la opcion dedicada del menu.
- Un unico boton "Generar y descargar Excel" para obtener coincidencias.
- Sin mensajes adicionales ni descargas redundantes.
"""

from __future__ import annotations

import html
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import textwrap
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core.auth import persist_login
from core.db import portal_set_password
from core.streamlit_compat import rerun
from pages.components.admin import init_admin_section


def _enforce_password_change(conn) -> None:
    if not st.session_state.get('must_change_password'):
        return

    st.warning('Debes actualizar tu contrasena antes de continuar.')
    with st.form('monitoreo_force_password_change', clear_on_submit=False):
        new_password = st.text_input('Nueva contrasena', type='password')
        confirm_password = st.text_input('Confirmar contrasena', type='password')
        submitted = st.form_submit_button('Actualizar contrasena', use_container_width=True)

    if not submitted:
        st.stop()

    new_password = (new_password or '').strip()
    confirm_password = (confirm_password or '').strip()
    if len(new_password) < 8:
        st.error('La contrasena debe tener al menos 8 caracteres.')
        st.stop()
    if new_password != confirm_password:
        st.error('Las contrasenas no coinciden.')
        st.stop()

    try:
        portal_set_password(
            conn,
            st.session_state.get('usuario', '') or '',
            new_password,
            require_change=False,
        )
        permisos_actuales = st.session_state.get('permisos') or []
        persist_login(
            st.session_state.get('usuario', ''),
            permisos_actuales,
            must_change_password=False,
            user_id=st.session_state.get('portal_user_id'),
        )
        st.success('Contrasena actualizada correctamente.')
        rerun()
    except Exception as exc:
        st.error(f'No fue posible actualizar la contrasena: {exc}')
        st.stop()


# ---------------------------------------------------------------------------
# Configuracion de rutas para Firmes persistente
# ---------------------------------------------------------------------------
FIRMES_DIR = Path("data/firmes")
MANIFEST_PATH = FIRMES_DIR / "manifest.json"
FIRMES_DIR.mkdir(parents=True, exist_ok=True)  # aseguramos carpeta


# ---------------------------------------------------------------------------
# Inicializacion de sesion / navegacion
# ---------------------------------------------------------------------------
conn = init_admin_section(
    page_title="Monitoreo EFOS - Cruce de RFC",
    active_top="monitoreo",
    layout="wide",
    show_inicio=False,
)
_enforce_password_change(conn)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown(
    '''
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 800px;
    }

    h1.titulo-sat {
        text-align: center;
        font-family: Arial, sans-serif;
        font-size: 2rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 2rem;
    }

    .card-box {
        border: 1px solid #d1d5db;
        background-color: #f9fafb;
        border-radius: 8px;
        padding: 1rem 1rem;
        margin-bottom: 1rem;
    }

    /* Ocultar el listado nativo de archivos del uploader */
    [data-testid="stFileUploader"] section + div,
    [data-testid="stFileUploader"] ul,
    [data-testid="stFileUploader"] li,
    [data-testid="stFileUploader"] small {
        display: none !important;
    }

    .accion-titulo {
        font-family: Arial, sans-serif;
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }

    .toggle-box {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        align-items: flex-start;
        margin-bottom: 0.5rem;
    }

    .lista-archivos-box {
        font-family: Arial, sans-serif;
        font-size: 0.9rem;
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        max-height: 200px;
        overflow-y: auto;
        margin-bottom: 1rem;
    }

    .info-texto,
    .error-texto {
        font-family: Arial, sans-serif;
        font-size: 0.9rem;
        font-weight: 500;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        margin-bottom: 1rem;
    }

    .info-texto {
        background-color: #eef2ff;
        color: #1e1e1e;
        border: 1px solid #c7d2fe;
    }

    .error-texto {
        background-color: #fee2e2;
        color: #7f1d1d;
        border: 1px solid #ef4444;
    }

    .descargar-excel-box {
        width: 100%;
        max-width: 320px;
        margin-bottom: 1rem;
    }

    .descargar-excel-box div.stDownloadButton > button {
        width: 100%;
        height: 56px;
        background-color: #f2f2f2;
        color: #000000;
        border: 1px solid #000000;
        border-radius: 6px;
        font-size: 1rem;
        font-weight: 600;
        box-shadow: none;
    }

    .descargar-excel-box div.stDownloadButton > button:hover {
        background-color: #e6e6e6;
        color: #000000;
        border: 1px solid #000000;
    }
    </style>
    ''',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _local_tag(tag: str) -> str:
    """Quita namespace de la etiqueta XML."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_emisor_from_xml(xml_bytes: bytes) -> tuple[str | None, str | None]:
    """Regresa (RFC, Nombre) del nodo <cfdi:Emisor>."""
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


def load_blacklist_file(handle) -> pd.DataFrame:
    """Lee Firmes.csv / Excel en DataFrame normalizando la columna RFC.
    handle puede ser un archivo subido (UploadedFile) o un file handle local (open('rb')).
    """
    # Nota: si es UploadedFile, tiene .name
    name_lower = getattr(handle, "name", "firmes_subido").lower()

    if name_lower.endswith(".csv"):
        df = pd.read_csv(handle, encoding="latin-1")
    elif name_lower.endswith(".xlsx") or name_lower.endswith(".xls"):
        df = pd.read_excel(handle)
    else:
        # fallback: intentar CSV latin-1
        try:
            df = pd.read_csv(handle, encoding="latin-1")
        except Exception:
            df = pd.DataFrame()

    if "RFC" in df.columns:
        df["RFC"] = df["RFC"].astype(str).str.strip()

    return df


def build_coincidencias_excel_bytes(df_xml: pd.DataFrame, df_blacklist: pd.DataFrame) -> bytes:
    """Cruza RFCs y devuelve bytes XLSX listo para descargar."""
    rfcs_xml_unicos = df_xml["RFC Emisor"].astype(str).str.strip().unique().tolist()

    df_blacklist_norm = df_blacklist.copy()
    df_blacklist_norm["RFC"] = df_blacklist_norm["RFC"].astype(str).str.strip()

    coincidencias = df_blacklist_norm[df_blacklist_norm["RFC"].isin(rfcs_xml_unicos)].copy()

    final_df = coincidencias if not coincidencias.empty else pd.DataFrame(columns=df_blacklist_norm.columns)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        final_df.to_excel(writer, index=False, sheet_name="Coincidencias")
    return output.getvalue()


def read_manifest() -> dict | None:
    """Lee manifest.json si existe y lo parsea."""
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def load_firmes_from_disk() -> pd.DataFrame:
    """Intenta cargar Firmes previamente guardado en disco, usando manifest."""
    manifest = read_manifest()
    if not manifest:
        return pd.DataFrame()

    stored_name = manifest.get("stored_as", "")
    if not stored_name:
        return pd.DataFrame()

    stored_path = FIRMES_DIR / stored_name
    if not stored_path.exists():
        return pd.DataFrame()

    # Abrimos en binario y pasamos el handle a load_blacklist_file
    try:
        with stored_path.open("rb") as handle:
            df = load_blacklist_file(handle)
    except Exception:
        return pd.DataFrame()

    # Validamos que realmente sirva
    if df.empty or "RFC" not in df.columns:
        return pd.DataFrame()

    return df




# ---------------------------------------------------------------------------
# Estado de sesion
# ---------------------------------------------------------------------------
if "parsed_df" not in st.session_state:
    st.session_state.parsed_df = pd.DataFrame(
        columns=["Archivo XML", "RFC Emisor", "Nombre Emisor"]
    )

autoload_message = None

if "archivos_xml_nombres" not in st.session_state:
    st.session_state.archivos_xml_nombres = []

if "blacklist_df" not in st.session_state:
    disk_df = load_firmes_from_disk()
    if disk_df.empty:
        st.session_state.blacklist_df = pd.DataFrame()
    else:
        st.session_state.blacklist_df = disk_df
        manifest = read_manifest() or {}
        nombre = manifest.get("filename", manifest.get("stored_as", "Firmes"))
        autoload_message = f"Archivo Firmes cargado automaticamente: {nombre}."

if "mostrar_lista_xml" not in st.session_state:
    st.session_state.mostrar_lista_xml = False

if "status_msg" not in st.session_state:
    st.session_state.status_msg = ""
    st.session_state.status_is_error = False

if autoload_message and not st.session_state.status_msg:
    st.session_state.status_msg = autoload_message
    st.session_state.status_is_error = False

# ---------------------------------------------------------------------------
# Titulo
# ---------------------------------------------------------------------------
st.markdown(
    '<h1 class="titulo-sat">Cruce de RFC con Lista Negra del SAT</h1>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Paso actual del flujo
# ---------------------------------------------------------------------------
tengo_xml = not st.session_state.parsed_df.empty
tengo_firmes = (
    (not st.session_state.blacklist_df.empty)
    and ("RFC" in st.session_state.blacklist_df.columns)
)


# ---------------------------------------------------------------------------
# 1. Uploader dinamico con rerun inmediato
#    Paso 1: subir XML
#    Paso 2: subir Firmes (solo si no lo encontramos ya en disco)
# ---------------------------------------------------------------------------

if not tengo_xml:
    # Paso 1: Subir CFDI XML
    st.markdown('<div class="card-box">', unsafe_allow_html=True)
    st.markdown('<div class="accion-titulo">Cargar archivos XML</div>', unsafe_allow_html=True)

    uploaded_xml_files = st.file_uploader(
        label="Selecciona o arrastra tus CFDI en XML",
        type=["xml"],
        accept_multiple_files=True,
        key="xml_files_uploader",
        label_visibility="collapsed",
    )

    xml_names = [file.name for file in (uploaded_xml_files or [])]
    escaped_names = [html.escape(name) for name in xml_names]
    if not escaped_names:
        summary_html = "Ningún archivo seleccionado"
        selected_class = " empty"
    elif len(escaped_names) == 1:
        summary_html = escaped_names[0]
        selected_class = ""
    else:
        bullets = "<br>".join(f"&bull; {name}" for name in escaped_names)
        summary_html = f"{len(escaped_names)} archivos seleccionados<br>{bullets}"
        selected_class = ""

    uploader_html = textwrap.dedent(
        f"""\
<div class="upload-wrapper monitoreo-upload" data-uploader="monitoreo-xml">
  <div class="upload-dropzone" id="monitoreo-xml-dropzone">
    <div class="upload-left">
      <div class="upload-icon">📁</div>
      <div class="upload-text">
        <p class="upload-title">Arrastra y suelta tus CFDI en XML aquí</p>
        <p class="upload-subtitle">Límite de 200 MB por archivo - XML</p>
      </div>
    </div>
    <button class="upload-button" type="button" id="monitoreo-xml-trigger">Seleccionar archivo</button>
  </div>
  <p class="upload-selected{selected_class}" id="monitoreo-xml-selected">{summary_html}</p>
</div>
<style>
:root {{
  --upload-primary: #4a5cff;
  --upload-primary-dark: #3e50f5;
  --upload-border: rgba(90, 94, 154, 0.25);
  --upload-background: rgba(226, 229, 255, 0.45);
}}
.upload-wrapper {{
  font-family: "Segoe UI", sans-serif;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}}
.upload-dropzone {{
  border: 1px solid var(--upload-border);
  border-radius: 14px;
  padding: 1.2rem 1.6rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--upload-background);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
  cursor: pointer;
  gap: 1rem;
}}
.upload-dropzone--active {{
  border-color: var(--upload-primary);
  background: rgba(226, 229, 255, 0.8);
  box-shadow: 0 0 0 3px rgba(74, 92, 255, 0.18);
}}
.upload-left {{
  display: flex;
  align-items: center;
  gap: 1rem;
}}
.upload-icon {{
  font-size: 2.25rem;
  line-height: 1;
}}
.upload-text {{
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}}
.upload-title {{
  margin: 0;
  font-weight: 600;
  color: #1f1f2d;
  font-size: 1rem;
}}
.upload-subtitle {{
  margin: 0;
  font-size: 0.85rem;
  color: #5c6070;
}}
.upload-button {{
  background: var(--upload-primary);
  color: #fff;
  font-weight: 600;
  border: none;
  border-radius: 10px;
  padding: 0.7rem 1.4rem;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}}
.upload-button:hover {{
  background: var(--upload-primary-dark);
  transform: translateY(-1px);
}}
.upload-selected {{
  margin: 0;
  font-size: 0.9rem;
  color: #3f4254;
  padding-left: 0.25rem;
}}
.upload-selected.empty {{
  color: #888b9c;
}}
@media (max-width: 640px) {{
  .upload-dropzone {{
    flex-direction: column;
    align-items: stretch;
  }}
  .upload-button {{
    width: 100%;
  }}
}}
</style>
<script>
(function() {{
  const frameDoc = window.parent.document;
  const escapeMap = {{"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}};
  function escapeHtml(value) {{ return String(value || "").replace(/[&<>"']/g, s => escapeMap[s] || s); }}
  function buildSummary(names) {{
    if (!names || !names.length) {{ return "Ningún archivo seleccionado"; }}
    if (names.length === 1) {{ return names[0]; }}
    const bullets = names.map(name => `&bull; ${{name}}`).join("<br>");
    return `${{names.length}} archivos seleccionados<br>${{bullets}}`;
  }}
  function setLabel(names) {{
    const label = document.getElementById("monitoreo-xml-selected");
    if (!label) return;
    label.innerHTML = buildSummary(names);
    if (names && names.length) {{ label.classList.remove("empty"); }}
    else {{ label.classList.add("empty"); }}
  }}
  function findInput() {{
    const inputs = Array.from(frameDoc.querySelectorAll("div[data-testid='stFileUploader'] input[type='file']"));
    return inputs.find(node => {{
      const accept = (node.getAttribute("accept") || "").toLowerCase();
      return accept.includes("xml");
    }});
  }}
  function waitForInput(retries = 0) {{
    const input = findInput();
    if (!input) {{
      if (retries < 50) {{ setTimeout(() => waitForInput(retries + 1), 100); }}
      return;
    }}
    setup(input);
  }}
  function setup(input) {{
    const dropzone = document.getElementById("monitoreo-xml-dropzone");
    const trigger = document.getElementById("monitoreo-xml-trigger");
    if (!dropzone || !trigger) return;

    const root = input.closest("div[data-testid='stFileUploader']");
    if (root) {{
      root.style.position = "absolute";
      root.style.opacity = "0";
      root.style.pointerEvents = "none";
      root.style.width = "1px";
      root.style.height = "1px";
      root.style.overflow = "hidden";
      root.style.margin = "0";
      root.style.padding = "0";
    }}

    function openDialog(event) {{
      event.preventDefault();
      input.click();
    }}

    trigger.addEventListener("click", openDialog);
    dropzone.addEventListener("click", openDialog);

    ["dragenter", "dragover"].forEach(evt => {{
      dropzone.addEventListener(evt, event => {{
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.add("upload-dropzone--active");
      }});
    }});

    ["dragleave", "dragend"].forEach(evt => {{
      dropzone.addEventListener(evt, event => {{
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.remove("upload-dropzone--active");
      }});
    }});

    dropzone.addEventListener("drop", event => {{
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.remove("upload-dropzone--active");

      if (!event.dataTransfer || !event.dataTransfer.files || !event.dataTransfer.files.length) {{
        return;
      }}

      const dt = new DataTransfer();
      Array.from(event.dataTransfer.files).forEach(file => dt.items.add(file));
      input.files = dt.files;
      input.dispatchEvent(new Event("change", {{ bubbles: true }}));
      const names = Array.from(dt.files).map(file => escapeHtml(file.name));
      setLabel(names);
    }});

    input.addEventListener("change", () => {{
      const names = Array.from(input.files || []).map(file => escapeHtml(file.name));
      setLabel(names);
    }});

    setLabel({json.dumps(escaped_names)});
  }}

  waitForInput();
}})();
</script>
"""
    )
    components.html(uploader_html, height=280)

    if uploaded_xml_files:
        rows = []
        nombres_xml = []
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
            nombres_xml.append(file.name)

        st.session_state.parsed_df = pd.DataFrame(rows)
        st.session_state.archivos_xml_nombres = nombres_xml

        st.session_state.status_msg = f"Se cargaron {len(nombres_xml)} archivo(s) XML correctamente."
        st.session_state.status_is_error = False

        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

elif tengo_xml and not tengo_firmes:
    st.markdown('<div class="card-box">', unsafe_allow_html=True)
    st.markdown(
        '<div class="accion-titulo">Cargar archivo Firmes (SAT)</div>',
        unsafe_allow_html=True,
    )
    st.write(
        "Actualiza el archivo Firmes desde la opcion 'Archivo Firmes' en la barra superior. "
        "Una vez hecho, regresa a esta pantalla y usa el boton 'Reintentar' para recargar la informacion."
    )
    if st.button('Reintentar', key='firmes_reload_btn'):
        rerun()



# Si ya tenemos XML y Firmes valido, ya no mostramos uploader.


# ---------------------------------------------------------------------------
# 2. Bloque para ver / ocultar nombres de XML cargados
#    Este bloque aparece desde que ya hay XML en memoria.
# ---------------------------------------------------------------------------
if tengo_xml:
    st.markdown('<div class="card-box">', unsafe_allow_html=True)

    col_toggle, col_info = st.columns([1, 3])

    with col_toggle:
        if st.button("Mostrar / ocultar archivos cargados", key="toggle_xml_btn"):
            st.session_state.mostrar_lista_xml = not st.session_state.mostrar_lista_xml

    with col_info:
        if st.session_state.status_msg:
            css_class = "error-texto" if st.session_state.status_is_error else "info-texto"
            st.markdown(
                f'<div class="{css_class}">{st.session_state.status_msg}</div>',
                unsafe_allow_html=True,
            )

    if st.session_state.mostrar_lista_xml:
        if st.session_state.archivos_xml_nombres:
            listado = "<br>".join(f"- {n}" for n in st.session_state.archivos_xml_nombres)
        else:
            listado = "No hay archivos XML en memoria."

        st.markdown(
            f'<div class="lista-archivos-box">{listado}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 3. Generar y descargar Excel
#    - Solo se muestra si ya tenemos XML y Firmes validos.
#    - Sin mensajes verdes extra ni boton doble.
#    - El unico boton ya dispara la descarga.
#    - El Excel se calcula aqui mismo en cada render.
# ---------------------------------------------------------------------------
tengo_todo = tengo_xml and tengo_firmes

if tengo_todo:
    excel_bytes_ready = build_coincidencias_excel_bytes(
        st.session_state.parsed_df,
        st.session_state.blacklist_df,
    )

    st.markdown('<div class="card-box">', unsafe_allow_html=True)
    st.markdown('<div class="accion-titulo">Cruce y descarga</div>', unsafe_allow_html=True)

    st.markdown('<div class="descargar-excel-box">', unsafe_allow_html=True)
    st.download_button(
        label="Generar y descargar Excel",
        data=excel_bytes_ready,
        file_name="Cruce_RFC_vs_Lista_Negra_SAT.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_excel_btn_final",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)