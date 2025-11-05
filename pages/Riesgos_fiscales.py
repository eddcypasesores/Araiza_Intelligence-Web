"""Riesgos Fiscales - analisis automatizado de CFDI masivos."""

from __future__ import annotations

import base64
import html
import io
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Iterable, List, Tuple
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import streamlit as st
import json
import streamlit.components.v1 as components
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from core.auth import ensure_session_from_token, persist_login, forget_session
from core.db import ensure_schema, get_conn, authenticate_portal_user
from core.flash import consume_flash, set_flash
from core.login_ui import render_login_header, render_token_reset_section
from core.session import process_logout_flag
from core.streamlit_compat import rerun, set_query_params, normalize_page_path


st.set_page_config(page_title="Riesgos Fiscales", layout="centered")


def _handle_logout_request() -> None:
    if process_logout_flag():
        forget_session()


def _has_permission(module: str) -> bool:
    permisos = st.session_state.get("permisos") or []
    return module in permisos


def _resolve_redirect_target() -> str | None:
    raw_next = st.query_params.get("next")
    if isinstance(raw_next, list):
        candidate = raw_next[-1] if raw_next else None
    elif isinstance(raw_next, str):
        candidate = raw_next or None
    else:
        candidate = None
    return normalize_page_path(candidate)


def _render_login() -> None:
    consume_flash()

    render_login_header("Iniciar sesion", subtitle="Acceso Riesgos fiscales")

    st.caption(
        "Valida tus credenciales para analizar tus CFDI y detectar riesgos fiscales automaticamente."
    )

    with st.form("riesgos_login", clear_on_submit=False):
        username = st.text_input("RFC", placeholder="ej. ABCD800101XXX")
        password = st.text_input("Contrasena", type="password", placeholder="********")
        col_login, col_cancel = st.columns(2)
        submitted = col_login.form_submit_button("Iniciar sesion", use_container_width=True)
        cancelled = col_cancel.form_submit_button("Cancelar", use_container_width=True)

    if cancelled:
        st.switch_page("pages/0_Inicio.py")
        st.stop()

    handled_reset = render_token_reset_section("riesgos")
    if handled_reset:
        st.stop()

    if not submitted:
        st.stop()

    username = (username or "").strip()
    password = password or ""

    conn = get_conn()
    ensure_schema(conn)
    try:
        record = authenticate_portal_user(conn, username, password)
    except Exception as exc:
        st.error("No fue posible validar las credenciales. Intentalo de nuevo.")
        st.caption(f"Detalle tecnico: {exc}")
        st.stop()
    finally:
        conn.close()

    if not record:
        st.error("RFC o contrasena incorrectos.")
        st.stop()

    permisos = set(record.get("permisos") or [])
    if "riesgos" not in permisos:
        st.error("Tu cuenta no tiene permiso para acceder al modulo de Riesgos fiscales.")
        st.stop()

    token = persist_login(
        record["rfc"],
        record["permisos"],
        must_change_password=record.get("must_change_password", False),
        user_id=record.get("id"),
    )
    set_flash("Inicio de sesion en Riesgos fiscales")

    redirect_target = _resolve_redirect_target()
    if redirect_target:
        remaining = {k: v for k, v in st.query_params.items() if k != "next"}
        remaining["auth"] = token
        try:
            set_query_params(remaining)
        except Exception:
            pass
        try:
            st.switch_page(redirect_target)
        except Exception:
            rerun()
        st.stop()

    try:
        params = {k: v for k, v in st.query_params.items() if k != "auth"}
        params["auth"] = token
        set_query_params(params)
    except Exception:
        pass
    rerun()


_handle_logout_request()
ensure_session_from_token()

if not (st.session_state.get("usuario") and _has_permission("riesgos")):
    _render_login()
    st.stop()

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
NAV_LOGO_CANDIDATES = (
    ASSETS_DIR / "logo_nav.png",
    ASSETS_DIR / "Araiza Intelligence logo-04.png",
    ASSETS_DIR / "Araiza Intelligence logo-04.jpg",
    ASSETS_DIR / "logo.png",
    ASSETS_DIR / "logo.jpg",
)
PAGE_STYLE = """
<style>
  [data-testid="stSidebar"],
  [data-testid="collapsedControl"],
  header[data-testid="stHeader"],
  div[data-testid="stToolbar"],
  #MainMenu,
  #stDecoration,
  #root > div:nth-child(1) > div[data-testid="stSidebarNav"] {
    display: none !important;
  }
  html, body, .stApp {
    background: #ffffff !important;
    color: #111111 !important;
  }
  .block-container {
    max-width: 1100px;
    padding-top: 0;
    padding-bottom: 80px;
  }
  *, *::before, *::after {
    color: #111111 !important;
    opacity: 1 !important;
  }
  h1, h2, h3, h4, h5, h6, label {
    color: #111111 !important;
  }
  div[data-testid="stTextInput"] input {
    padding: .5rem .9rem;
    font-size: .95rem;
    color: #111111 !important;
    background: #ffffff !important;
    border: 1px solid #d0d7de !important;
    border-radius: .5rem !important;
  }
  input::placeholder {
    color: #9aa0a6 !important;
    opacity: 1 !important;
  }
  .small-error {
    color: #b91c1c;
    font-size: .85rem;
    margin-top: .25rem;
  }
  .custom-nav {
    position: fixed;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: min(1100px, 100%);
    z-index: 1000;
    background: #ffffff;
    color: #0f172a;
    padding: 10px 22px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    box-shadow: 0 18px 32px rgba(15, 23, 42, 0.18);
    border: 1px solid rgba(148, 163, 184, 0.25);
  }
  .nav-brand {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    font-weight: 700;
    font-size: 1rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .nav-brand img {
    height: 28px;
    width: auto;
    display: block;
  }
  .nav-actions a,
  .nav-actions a:visited {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 6px 20px;
    border-radius: 999px;
    background: #0d3c74;
    color: #ffffff !important;
    font-weight: 600;
    text-decoration: none;
    box-shadow: 0 6px 16px rgba(13, 60, 116, 0.25);
  }
  .nav-actions a:hover {
    filter: brightness(0.95);
  }
  .nav-spacer {
    height: 80px;
  }
</style>
"""


def _navbar_logo_data() -> str | None:
    for candidate in NAV_LOGO_CANDIDATES:
        if candidate.exists():
            try:
                encoded = base64.b64encode(candidate.read_bytes()).decode()
                return f"data:image/png;base64,{encoded}"
            except Exception:
                continue
    return None


def _handle_pending_navigation() -> None:
    params = st.query_params
    raw = params.get("goto")
    if isinstance(raw, list):
        goto = raw[-1] if raw else None
    elif isinstance(raw, str):
        goto = raw
    else:
        goto = None
    if goto:
        cleaned = {k: v for k, v in params.items() if k != "goto"}
        try:
            set_query_params(cleaned if cleaned else None)
        except Exception:
            pass
        try:
            st.switch_page(goto)
        except Exception:
            pass
        st.stop()


def render_fixed_nav() -> None:
    logo_src = _navbar_logo_data()
    href = "/?page=Inicio&logout=1"
    brand_img = f'<img src="{logo_src}" alt="Araiza logo">' if logo_src else ""
    nav_markup = dedent(
        f"""
        <div class="custom-nav">
          <div class="nav-brand">
            {brand_img}
            <span>Araiza Intelligence</span>
          </div>
          <div class="nav-actions">
            <a href="{href}" target="_self">Cerrar sesi&oacute;n</a>
          </div>
        </div>
        <div class="nav-spacer"></div>
        """
    ).strip()
    st.markdown(PAGE_STYLE + nav_markup, unsafe_allow_html=True)


_handle_pending_navigation()
render_fixed_nav()


# --- Extractor helpers ----------------------------------------------------

def _to_decimal(raw: str | None) -> Decimal:
    try:
        return Decimal(raw) if raw is not None else Decimal("0")
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _detect_cfdi_ns(root: ET.Element) -> str:
    if root.tag.startswith("{") and "}Comprobante" in root.tag:
        return root.tag.split("}")[0][1:]
    return "http://www.sat.gob.mx/cfd/4"


def parse_cfdi_bytes(data: bytes) -> Dict[str, Any]:
    tree = ET.fromstring(data)
    ns_cfdi = _detect_cfdi_ns(tree)
    ns = {"cfdi": ns_cfdi, "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital"}

    comprobante = tree
    fecha = comprobante.attrib.get("Fecha", "")

    emisor = comprobante.find("cfdi:Emisor", ns)
    rfc_emisor = emisor.attrib.get("Rfc", "") if emisor is not None else ""
    nombre_emisor = emisor.attrib.get("Nombre", "") if emisor is not None else ""

    receptor = comprobante.find("cfdi:Receptor", ns)
    regimen_receptor = receptor.attrib.get("RegimenFiscalReceptor", "") if receptor is not None else ""

    tfd = comprobante.find(".//cfdi:Complemento/tfd:TimbreFiscalDigital", ns)
    uuid = tfd.attrib.get("UUID", "") if tfd is not None else ""

    conceptos = comprobante.findall("cfdi:Conceptos/cfdi:Concepto", ns)
    total_concepto = sum(_to_decimal(c.attrib.get("Importe")) for c in conceptos)

    traslados_globales = comprobante.findall("cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", ns)
    if traslados_globales:
        total_traslados = sum(_to_decimal(t.attrib.get("Importe")) for t in traslados_globales)
    else:
        traslados_concepto = comprobante.findall(
            "cfdi:Conceptos/cfdi:Concepto/cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado",
            ns,
        )
        total_traslados = sum(_to_decimal(t.attrib.get("Importe")) for t in traslados_concepto)

    return {
        "Fecha": fecha,
        "RFC Emisor": rfc_emisor,
        "Nombre Emisor": nombre_emisor,
        "UUID": uuid,
        "cfdi:Concepto Importe": float(total_concepto),
        "cfdi:Traslado Importe": float(total_traslados),
        "RegimenFiscalReceptor": regimen_receptor,
    }


def parse_cfdi_many(files: Iterable[Tuple[str, bytes]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _, blob in files:
        try:
            rows.append(parse_cfdi_bytes(blob))
        except Exception:
            continue
    return rows


st.title("RIESGOS FISCALES")


# --- Inputs ---------------------------------------------------------------

left_spacer, col1, col2, right_spacer = st.columns([1, 3, 3, 1])
with col1:
    regimen_fiscal_correcto = st.text_input(
        "Regimen Fiscal Correcto",
        value="",
        placeholder="Ej. 601",
    )
with col2:
    cp_referencia = st.text_input("CP", value="", placeholder="Ej. 50903")


if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0


spacer_col, upload_col, clear_col = st.columns([1, 8, 1])
with upload_col:
    st.markdown('<div class="risks-native-wrapper">', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Subir XML o ZIP",
        type=["xml", "zip"],
        accept_multiple_files=True,
        key=f"xml_uploader_{st.session_state['uploader_key']}",
        label_visibility="collapsed",
        help="Arrastra y suelta CFDI en XML o ZIP (puedes subir varios a la vez).",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <style>
        .risks-native-wrapper {
            position: relative;
        }
        .risks-native-wrapper > div[data-testid="stFileUploader"] {
            position: absolute;
            inset: 0;
            width: 1px;
            height: 1px;
            opacity: 0;
            pointer-events: none;
            overflow: hidden;
        }
        .risk-hidden-native {
            position: absolute !important;
            inset: 0 !important;
            width: 1px !important;
            height: 1px !important;
            opacity: 0 !important;
            pointer-events: none !important;
            overflow: hidden !important;
            margin: 0 !important;
        }
        .risk-hidden-native * {
            opacity: 0 !important;
            pointer-events: none !important;
            height: 0 !important;
        }
        .risk-hidden-native input[type="file"] {
            opacity: 0 !important;
            pointer-events: auto !important;
            width: 1px !important;
            height: 1px !important;
        }
        </style>
        <script>
        (function() {
            const doc = window.document;
            function hideNative(retries = 0) {
                const node = doc.querySelector("div[data-testid='stFileUploader']");
                if (!node) {
                    if (retries < 50) {
                        window.setTimeout(() => hideNative(retries + 1), 100);
                    }
                    return;
                }
                if (!node.classList.contains("risk-hidden-native")) {
                    node.classList.add("risk-hidden-native");
                }
            }
            hideNative();
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )

    uploaded_names = [f.name for f in uploaded] if uploaded else []
    if not uploaded_names:
        display_label = "Ningun archivo seleccionado"
    elif len(uploaded_names) == 1:
        display_label = uploaded_names[0]
    else:
        preview = ", ".join(uploaded_names[:2])
        if len(uploaded_names) > 2:
            preview += "…"
        display_label = f"{len(uploaded_names)} archivos: {preview}"

    display_label_html = html.escape(display_label)
    selected_json = json.dumps(uploaded_names)
    selected_class = "" if uploaded_names else " empty"

    components.html(
        f"""
<div class="risk-upload-wrapper">
  <div class="risk-dropzone" id="risk-dropzone">
    <div class="risk-dropzone-left">
      <div class="risk-icon">📂</div>
      <div class="risk-text">
        <p class="risk-title">Arrastra y suelta tus CFDI (XML o ZIP)</p>
        <p class="risk-subtitle">Puedes cargar varios archivos o ZIP a la vez</p>
      </div>
    </div>
    <button class="risk-button" type="button" id="risk-trigger">Seleccionar archivos</button>
  </div>
  <p class="risk-selected{selected_class}" id="risk-selected">{display_label_html}</p>
</div>
<style>
:root {{
  --risk-primary: #0d3c74;
  --risk-primary-dark: #0a2e58;
  --risk-border: rgba(13, 60, 116, 0.22);
  --risk-background: rgba(13, 60, 116, 0.08);
}}
.risk-upload-wrapper {{
  font-family: "Inter", "Segoe UI", sans-serif;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  width: 100%;
}}
.risk-dropzone {{
  border: 1px solid var(--risk-border);
  border-radius: 16px;
  padding: 1.2rem 1.6rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--risk-background);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
  cursor: pointer;
  gap: 1rem;
  width: 100%;
  box-sizing: border-box;
}}
.risk-dropzone--active {{
  border-color: var(--risk-primary);
  background: rgba(13, 60, 116, 0.12);
  box-shadow: 0 0 0 3px rgba(13, 60, 116, 0.18);
}}
.risk-dropzone-left {{
  display: flex;
  align-items: center;
  gap: 1rem;
}}
.risk-icon {{
  font-size: 2.25rem;
  line-height: 1;
}}
.risk-text {{
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}}
.risk-title {{
  margin: 0;
  font-weight: 600;
  color: #10223d;
  font-size: 1rem;
}}
.risk-subtitle {{
  margin: 0;
  font-size: 0.85rem;
  color: #4b5563;
}}
.risk-button {{
  background: var(--risk-primary);
  color: #ffffff;
  font-weight: 600;
  border: none;
  border-radius: 12px;
  padding: 0.75rem 1.5rem;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}}
.risk-button:hover {{
  background: var(--risk-primary-dark);
  transform: translateY(-1px);
}}
.risk-selected {{
  margin: 0;
  font-size: 0.9rem;
  color: #374151;
  padding-left: 0.25rem;
}}
.risk-selected.empty {{
  color: #9aa0a6;
}}
@media (max-width: 640px) {{
  .risk-dropzone {{
    flex-direction: column;
    align-items: stretch;
  }}
  .risk-button {{
    width: 100%;
  }}
}}
</style>
<script>
(function() {{
  const initialNames = {selected_json};
  const frameDoc = window.parent.document;

  function formatNames(list) {{
    if (!list || !list.length) {{
      return "Ningun archivo seleccionado";
    }}
    if (list.length === 1) {{
      return list[0];
    }}
    const preview = list.slice(0, 2).join(", ") + (list.length > 2 ? "…" : "");
    return `${{list.length}} archivos: ${{preview}}`;
  }}

  function setLabel(names) {{
    const label = document.getElementById("risk-selected");
    if (!label) return;
    const text = formatNames(names);
    label.textContent = text;
    if (names && names.length) {{
      label.classList.remove("empty");
    }} else {{
      label.classList.add("empty");
    }}
  }}

  function waitForInput(retries = 0) {{
    const input = frameDoc.querySelector("div[data-testid='stFileUploader'] input[type='file']");
    if (!input) {{
      if (retries < 50) {{
        setTimeout(() => waitForInput(retries + 1), 100);
      }}
      return;
    }}
    setup(input);
  }}

  function setup(input) {{
    const dropzone = document.getElementById("risk-dropzone");
    const trigger = document.getElementById("risk-trigger");
    if (!dropzone || !trigger) return;

    const nativeWrapper = input.closest("div[data-testid='stFileUploader']");
    if (nativeWrapper) {{
      nativeWrapper.classList.add("risk-hidden-native");
      nativeWrapper.setAttribute("aria-hidden", "true");
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
        dropzone.classList.add("risk-dropzone--active");
      }});
    }});

    ["dragleave", "dragend"].forEach(evt => {{
      dropzone.addEventListener(evt, event => {{
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.remove("risk-dropzone--active");
      }});
    }});

    dropzone.addEventListener("drop", event => {{
      event.preventDefault();
      event.stopPropagation();
      dropzone.classList.remove("risk-dropzone--active");

      if (!event.dataTransfer || !event.dataTransfer.files || !event.dataTransfer.files.length) {{
        return;
      }}

      const dt = new DataTransfer();
      Array.from(event.dataTransfer.files).forEach(file => dt.items.add(file));
      input.files = dt.files;
      input.dispatchEvent(new Event("change", {{ bubbles: true }}));
      setLabel(Array.from(dt.files).map(file => file.name));
    }});

    input.addEventListener("change", () => {{
      const names = Array.from(input.files || []).map(file => file.name);
      setLabel(names);
    }});

    setLabel(initialNames);
  }}

  setLabel(initialNames);
  waitForInput();
}})();
</script>
        """,
        height=260,
    )
with clear_col:
    if st.button("Limpiar"):
        st.session_state["uploader_key"] += 1
        rerun()


BASE_COLS = [
    "Fecha",
    "RFC Emisor",
    "Nombre Emisor",
    "UUID",
    "cfdi:Concepto Importe",
    "cfdi:Traslado Importe",
    "RegimenFiscalReceptor",
]


def _norm_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def _norm_text(raw: str | None) -> str:
    return (raw or "").strip().upper()


def _get_root(xml_bytes: bytes) -> ET.Element:
    return ET.fromstring(xml_bytes)


def _has_cuenta_predial(xml_bytes: bytes) -> bool:
    root = _get_root(xml_bytes)
    ns = {"cfdi": _detect_cfdi_ns(root)}
    return root.find(".//cfdi:Conceptos/cfdi:Concepto/cfdi:CuentaPredial", ns) is not None


def _get_regimen_emisor(xml_bytes: bytes) -> str:
    root = _get_root(xml_bytes)
    ns = {"cfdi": _detect_cfdi_ns(root)}
    emisor = root.find("cfdi:Emisor", ns)
    return (emisor.attrib.get("RegimenFiscal", "") if emisor is not None else "").strip()


def _get_forma_pago(xml_bytes: bytes) -> str:
    return _get_root(xml_bytes).attrib.get("FormaPago", "").strip()


def _get_metodo_pago(xml_bytes: bytes) -> str:
    return _get_root(xml_bytes).attrib.get("MetodoPago", "").strip()


def _get_tipo_comprobante(xml_bytes: bytes) -> str:
    return _get_root(xml_bytes).attrib.get("TipoDeComprobante", "").strip()


def _get_domicilio_receptor(xml_bytes: bytes) -> str:
    root = _get_root(xml_bytes)
    ns = {"cfdi": _detect_cfdi_ns(root)}
    receptor = root.find("cfdi:Receptor", ns)
    return (receptor.attrib.get("DomicilioFiscalReceptor", "") if receptor is not None else "").strip()


def _get_uso_cfdi(xml_bytes: bytes) -> str:
    root = _get_root(xml_bytes)
    ns = {"cfdi": _detect_cfdi_ns(root)}
    receptor = root.find("cfdi:Receptor", ns)
    return (receptor.attrib.get("UsoCFDI", "") if receptor is not None else "").strip()


def _get_moneda(xml_bytes: bytes) -> str:
    return _get_root(xml_bytes).attrib.get("Moneda", "").strip()


def _get_tipo_cambio(xml_bytes: bytes) -> str:
    return _get_root(xml_bytes).attrib.get("TipoCambio", "").strip()


def _fecha_solo_dia(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    text = str(value or "").strip()
    if not text:
        return text
    if "T" in text:
        return text.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return text[:10]


def _parse_fecha(value: Any) -> datetime | None:
    try:
        return datetime.strptime(_fecha_solo_dia(value), "%Y-%m-%d")
    except Exception:
        return None


SINGLE_TC_PATH = Path("data/Tipo Cambio.xls")


def _flatten_cols(cols: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for col in cols:
        if isinstance(col, tuple):
            col = " ".join(str(x) for x in col if str(x) != "None")
        result.append(str(col).strip())
    return result


def _coerce_tc_dates(series: pd.Series) -> pd.Series:
    if np.issubdtype(series.dtype, np.number):
        return pd.to_datetime(series, unit="D", origin="1899-12-30", errors="coerce").dt.date
    parsed = pd.to_datetime(
        series.astype(str), errors="coerce", dayfirst=True, infer_datetime_format=True
    ).dt.date
    if pd.isna(parsed).mean() > 0.5:
        try:
            numeric = pd.to_numeric(series, errors="coerce")
            serial = pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce").dt.date
            parsed = pd.Series(parsed).where(pd.Series(parsed).notna(), serial).values
        except Exception:
            pass
    return parsed


def _read_tc_series(path: Path) -> pd.Series | None:
    if not path.exists():
        st.error("No se encontro el archivo de tipo de cambio en data/Tipo Cambio.xls.")
        return None
    try:
        df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    except Exception:
        try:
            import xlrd  # noqa: F401
            df = pd.read_excel(path, sheet_name=0, engine="xlrd")
        except Exception:
            try:
                df = pd.read_excel(path, sheet_name=0)
            except Exception as exc:
                st.warning(
                    "No fue posible cargar 'Tipo Cambio.xls'. "
                    "Verifica que el archivo exista y que el paquete xlrd este instalado."
                )
                print(exc)
                return None

    df.columns = _flatten_cols(df.columns)

    tc_col = next((c for c in df.columns if "para solventar obligaciones" in c.lower()), None)
    if tc_col is None:
        st.error("No se encontro la columna 'Para solventar obligaciones' en Tipo Cambio.xls.")
        return None

    fecha_col = next(
        (
            c
            for c in df.columns
            if "fecha" in c.lower()
            or "public" in c.lower()
            or np.issubdtype(df[c].dtype, np.datetime64)
        ),
        None,
    )
    if fecha_col is None:
        st.error("No se encontro una columna de fecha en Tipo Cambio.xls.")
        return None

    work = df[[fecha_col, tc_col]].copy()
    work[fecha_col] = _coerce_tc_dates(work[fecha_col])
    work[tc_col] = (
        work[tc_col]
        .astype(str)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace("[^0-9.]", "", regex=True)
    )
    work[tc_col] = pd.to_numeric(work[tc_col], errors="coerce")
    work = work.dropna(subset=[fecha_col, tc_col])

    series = (
        work.drop_duplicates(subset=[fecha_col], keep="last")
        .set_index(fecha_col)[tc_col]
        .sort_index()
    )
    series.name = "TC"
    return series


tc_series = _read_tc_series(SINGLE_TC_PATH)


def _tc_lookup(timestamp: datetime | None) -> float | None:
    if tc_series is None or timestamp is None:
        return None
    value = tc_series.get(timestamp.date())
    return float(value) if pd.notna(value) else None


def _tc_prev_lookup(timestamp: datetime | None) -> float | None:
    if tc_series is None or timestamp is None:
        return None
    idx = tc_series.index
    pos = np.searchsorted(idx, timestamp.date(), side="left") - 1
    if pos >= 0:
        return float(tc_series.iloc[pos])
    return None


def _ensure_excel_date(df: pd.DataFrame, column: str = "Fecha") -> pd.DataFrame:
    if column not in df.columns:
        return df
    out = df.copy()
    parsed = pd.to_datetime(out[column], errors="coerce", dayfirst=False)
    mask = parsed.isna()
    if mask.any():
        parsed_alt = pd.to_datetime(out.loc[mask, column], errors="coerce", dayfirst=True)
        parsed.loc[mask] = parsed_alt
    out[column] = parsed
    return out


def _safe_sheet_name(name: str) -> str:
    safe = "".join("-" if ch in ":/?*[]\\" else ch for ch in str(name))
    safe = safe.strip() or "Hoja"
    return safe[:31]


def _write_sheet(writer, df: pd.DataFrame, sheet_name: str, title_text: str) -> None:
    safe_name = _safe_sheet_name(sheet_name)
    df_x = _ensure_excel_date(df, "Fecha")
    df_x.to_excel(writer, index=False, sheet_name=safe_name, startrow=2)

    wb = writer.book
    ws = wb[safe_name]

    ws["A1"].value = title_text
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")

    last_col = max(1, df_x.shape[1])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    ws.freeze_panes = "A3"

    last_col_letter = get_column_letter(last_col)
    last_row = df_x.shape[0] + 3
    ws.auto_filter.ref = f"A3:{last_col_letter}{last_row}"

    for idx, column in enumerate(df_x.columns, start=1):
        max_len = max([len(str(column))] + [len(str(x)) for x in df_x[column].astype(str).fillna("")])
        ws.column_dimensions[get_column_letter(idx)].width = min(max_len + 2, 50)

    if "Fecha" in df_x.columns:
        col_idx = list(df_x.columns).index("Fecha") + 1
        for row in ws.iter_rows(min_row=3, max_row=ws.max_row, min_col=col_idx, max_col=col_idx):
            row[0].number_format = "DD/MM/YYYY"


# --- Validacion de XML ----------------------------------------------------

valid_files: List[Tuple[str, bytes]] = []
bad_files: List[str] = []

def _extract_xml_from_zip(blob: bytes, container_name: str) -> Tuple[List[Tuple[str, bytes]], List[str]]:
    ok: List[Tuple[str, bytes]] = []
    issues: List[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            members = [
                m for m in zf.infolist()
                if (not m.is_dir()) and m.filename.lower().endswith(".xml")
            ]
            if not members:
                issues.append(f"{container_name} (sin XML)")
                return ok, issues
            for member in members:
                try:
                    xml_bytes = zf.read(member)
                    if not xml_bytes:
                        raise ValueError("Archivo vacio")
                    ET.fromstring(xml_bytes)
                    ok.append((member.filename, xml_bytes))
                except Exception:
                    issues.append(f"{container_name}:{member.filename}")
    except zipfile.BadZipFile:
        issues.append(f"{container_name} (ZIP inválido)")
    return ok, issues


if uploaded:
    for uf in uploaded:
        try:
            data = uf.read()
            if not data:
                raise ValueError("Archivo vacio")
            name_lower = uf.name.lower()
            if name_lower.endswith(".zip"):
                extracted, issues = _extract_xml_from_zip(data, uf.name)
                valid_files.extend(extracted)
                bad_files.extend(issues)
                continue
            ET.fromstring(data)
            valid_files.append((uf.name, data))
        except Exception:
            bad_files.append(uf.name)

    if bad_files:
        display = ", ".join(bad_files[:3])
        if len(bad_files) > 3:
            display += "..."
        st.markdown(
            f"<div class='small-error'>⚠️ No se pudo cargar {len(bad_files)} archivo(s): {display}</div>",
            unsafe_allow_html=True,
        )

files = valid_files

if not files:
    st.info("Carga uno o mas CFDI (XML o ZIP) para analizar los riesgos fiscales.")
    st.stop()


# --- Construccion de DataFrame base ---------------------------------------

rows = parse_cfdi_many(files)
for row in rows or []:
    if "Fecha" in row:
        row["Fecha"] = _fecha_solo_dia(row["Fecha"])

df = pd.DataFrame(rows, columns=BASE_COLS) if rows else pd.DataFrame(columns=BASE_COLS)

if df.empty:
    st.info("No se pudieron leer CFDI validos. Verifica que los XML sean correctos.")
    st.stop()

insert_pos = (
    list(df.columns).index("RegimenFiscalReceptor") + 1
    if "RegimenFiscalReceptor" in df.columns
    else len(df.columns)
)
df.insert(insert_pos, "Regimen Fiscal Correcto", regimen_fiscal_correcto)

if regimen_fiscal_correcto.strip():
    mismatches = df[
        _norm_series(df["RegimenFiscalReceptor"])
        != _norm_series(df["Regimen Fiscal Correcto"])
    ]
else:
    mismatches = pd.DataFrame(columns=df.columns)
mismatches = mismatches.reindex(columns=df.columns)

arrend_rows: List[Dict[str, Any]] = []
for (_, blob), row in zip(files, rows):
    if _get_regimen_emisor(blob) == "606" and not _has_cuenta_predial(blob):
        arrend_rows.append(row)
arrend_df = pd.DataFrame(arrend_rows, columns=BASE_COLS) if arrend_rows else pd.DataFrame(columns=BASE_COLS)
arrend_df = arrend_df.reindex(columns=BASE_COLS)

cols_efectivo = [
    "Fecha",
    "RFC Emisor",
    "Nombre Emisor",
    "UUID",
    "cfdi:Concepto Importe",
    "cfdi:Traslado Importe",
    "FormaPago",
]
efectivo_rows: List[Dict[str, Any]] = []
for (_, blob), row in zip(files, rows):
    forma = _get_forma_pago(blob)
    try:
        total = float(row.get("cfdi:Concepto Importe", 0) or 0) + float(
            row.get("cfdi:Traslado Importe", 0) or 0
        )
    except Exception:
        total = 0.0
    if forma == "01" and total > 2000:
        efectivo_rows.append(
            {
                "Fecha": row.get("Fecha", ""),
                "RFC Emisor": row.get("RFC Emisor", ""),
                "Nombre Emisor": row.get("Nombre Emisor", ""),
                "UUID": row.get("UUID", ""),
                "cfdi:Concepto Importe": row.get("cfdi:Concepto Importe", 0),
                "cfdi:Traslado Importe": row.get("cfdi:Traslado Importe", 0),
                "FormaPago": forma,
            }
        )
efectivo_df = pd.DataFrame(efectivo_rows, columns=cols_efectivo) if efectivo_rows else pd.DataFrame(columns=cols_efectivo)

cols_domcp = [
    "Fecha",
    "RFC Emisor",
    "Nombre Emisor",
    "UUID",
    "cfdi:Concepto Importe",
    "cfdi:Traslado Importe",
    "DomicilioFiscalReceptor",
    "CP",
]
domcp_rows: List[Dict[str, Any]] = []
if cp_referencia.strip():
    for (_, blob), row in zip(files, rows):
        dom_rec = _get_domicilio_receptor(blob)
        if _norm_text(dom_rec) != _norm_text(cp_referencia):
            domcp_rows.append(
                {
                    "Fecha": row.get("Fecha", ""),
                    "RFC Emisor": row.get("RFC Emisor", ""),
                    "Nombre Emisor": row.get("Nombre Emisor", ""),
                    "UUID": row.get("UUID", ""),
                    "cfdi:Concepto Importe": row.get("cfdi:Concepto Importe", 0),
                    "cfdi:Traslado Importe": row.get("cfdi:Traslado Importe", 0),
                    "DomicilioFiscalReceptor": dom_rec,
                    "CP": cp_referencia,
                }
            )
domcp_df = pd.DataFrame(domcp_rows, columns=cols_domcp) if domcp_rows else pd.DataFrame(columns=cols_domcp)

cols_sin_ret = [
    "Fecha",
    "RFC Emisor",
    "Nombre Emisor",
    "UUID",
    "cfdi:Concepto Importe",
    "cfdi:Traslado Importe",
    "RegimenFiscalEmisor",
    "Retenciones",
]
sin_ret_rows: List[Dict[str, Any]] = []
for (_, blob), row in zip(files, rows):
    regimen_emisor = _get_regimen_emisor(blob)
    if regimen_emisor != "626":
        continue
    root = _get_root(blob)
    ns = {"cfdi": _detect_cfdi_ns(root)}
    impuestos: set[str] = set()
    for ret in root.findall(".//cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion", ns):
        impuesto = ret.attrib.get("Impuesto", "").strip()
        if impuesto:
            impuestos.add(impuesto)
    for ret in root.findall(".//cfdi:Conceptos/cfdi:Concepto/cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion", ns):
        impuesto = ret.attrib.get("Impuesto", "").strip()
        if impuesto:
            impuestos.add(impuesto)
    if not any(code in {"001", "002"} for code in impuestos):
        sin_ret_rows.append(
            {
                "Fecha": row.get("Fecha", ""),
                "RFC Emisor": row.get("RFC Emisor", ""),
                "Nombre Emisor": row.get("Nombre Emisor", ""),
                "UUID": row.get("UUID", ""),
                "cfdi:Concepto Importe": row.get("cfdi:Concepto Importe", 0),
                "cfdi:Traslado Importe": row.get("cfdi:Traslado Importe", 0),
                "RegimenFiscalEmisor": regimen_emisor,
                "Retenciones": ", ".join(sorted(impuestos)) if impuestos else "SIN RETENCIONES",
            }
        )
sin_ret_df = pd.DataFrame(sin_ret_rows, columns=cols_sin_ret) if sin_ret_rows else pd.DataFrame(columns=cols_sin_ret)

cols_uso = [
    "Fecha",
    "RFC Emisor",
    "Nombre Emisor",
    "UUID",
    "cfdi:Concepto Importe",
    "cfdi:Traslado Importe",
    "UsoCFDI",
]
uso_rows: List[Dict[str, Any]] = []
for (_, blob), row in zip(files, rows):
    uso = _get_uso_cfdi(blob).upper()
    if uso == "S01":
        uso_rows.append(
            {
                "Fecha": row.get("Fecha", ""),
                "RFC Emisor": row.get("RFC Emisor", ""),
                "Nombre Emisor": row.get("Nombre Emisor", ""),
                "UUID": row.get("UUID", ""),
                "cfdi:Concepto Importe": row.get("cfdi:Concepto Importe", 0),
                "cfdi:Traslado Importe": row.get("cfdi:Traslado Importe", 0),
                "UsoCFDI": uso,
            }
        )
uso_df = pd.DataFrame(uso_rows, columns=cols_uso) if uso_rows else pd.DataFrame(columns=cols_uso)

cols_tc = [
    "Fecha",
    "RFC Emisor",
    "Nombre Emisor",
    "UUID",
    "cfdi:Concepto Importe",
    "cfdi:Traslado Importe",
    "Moneda",
    "TipoCambioXML",
    "TipoCambioDOF",
    "TipoCambioDOFAnterior",
    "Diferencia",
]
tc_rows: List[Dict[str, Any]] = []
usd_rows: List[Dict[str, Any]] = []
for (_, blob), row in zip(files, rows):
    moneda = _get_moneda(blob).upper()
    if moneda != "USD":
        continue
    fecha_dt = _parse_fecha(row.get("Fecha", ""))
    tc_xml_raw = _get_tipo_cambio(blob)
    try:
        tc_xml = float(str(tc_xml_raw).replace(",", "")) if tc_xml_raw else None
    except Exception:
        tc_xml = None
    tc_dof = _tc_lookup(fecha_dt)
    tc_prev = _tc_prev_lookup(fecha_dt)
    diff = None if tc_xml is None or tc_dof is None else round(tc_xml - tc_dof, 6)

    usd_rows.append(
        {
            "Fecha": row.get("Fecha", ""),
            "RFC Emisor": row.get("RFC Emisor", ""),
            "Nombre Emisor": row.get("Nombre Emisor", ""),
            "UUID": row.get("UUID", ""),
            "cfdi:Concepto Importe": row.get("cfdi:Concepto Importe", 0),
            "cfdi:Traslado Importe": row.get("cfdi:Traslado Importe", 0),
            "Moneda": moneda,
            "TipoCambioXML": tc_xml,
            "TipoCambioDOF": tc_dof,
            "TipoCambioDOFAnterior": tc_prev,
            "Diferencia": diff,
        }
    )

    include = False
    if tc_dof is not None and tc_xml is not None:
        include = abs(tc_xml - tc_dof) > 1e-6
    elif tc_dof is not None and tc_xml is None:
        include = True
    if include:
        tc_rows.append(usd_rows[-1])

tc_df = pd.DataFrame(tc_rows, columns=cols_tc) if tc_rows else pd.DataFrame(columns=cols_tc)
usd_all_df = pd.DataFrame(usd_rows, columns=cols_tc) if usd_rows else pd.DataFrame(columns=cols_tc)

cols_nc = [
    "Fecha",
    "RFC Emisor",
    "Nombre Emisor",
    "UUID",
    "cfdi:Concepto Importe",
    "cfdi:Traslado Importe",
    "TipoDeComprobante",
    "FormaPago",
    "MetodoPago",
]


def _norm_forma_pago(value: str | None) -> str:
    cleaned = (value or "").strip()
    cleaned = cleaned.lstrip("0")
    return cleaned or "0"


nc_rows: List[Dict[str, Any]] = []
for (_, blob), row in zip(files, rows):
    tipo = _get_tipo_comprobante(blob).upper()
    if tipo != "E":
        continue
    forma = _norm_forma_pago(_get_forma_pago(blob))
    metodo = _get_metodo_pago(blob).upper()
    if (forma != "15") or (metodo != "PUE"):
        nc_rows.append(
            {
                "Fecha": row.get("Fecha", ""),
                "RFC Emisor": row.get("RFC Emisor", ""),
                "Nombre Emisor": row.get("Nombre Emisor", ""),
                "UUID": row.get("UUID", ""),
                "cfdi:Concepto Importe": row.get("cfdi:Concepto Importe", 0),
                "cfdi:Traslado Importe": row.get("cfdi:Traslado Importe", 0),
                "TipoDeComprobante": tipo,
                "FormaPago": forma,
                "MetodoPago": metodo,
            }
        )
nc_df = pd.DataFrame(nc_rows, columns=cols_nc) if nc_rows else pd.DataFrame(columns=cols_nc)

cols_pue99 = [
    "Fecha",
    "RFC Emisor",
    "Nombre Emisor",
    "UUID",
    "cfdi:Concepto Importe",
    "cfdi:Traslado Importe",
    "FormaPago",
    "MetodoPago",
]
pue99_rows: List[Dict[str, Any]] = []
for (_, blob), row in zip(files, rows):
    tipo = _get_tipo_comprobante(blob).upper()
    if tipo != "I":
        continue
    metodo = _get_metodo_pago(blob).upper()
    fp_raw = _get_forma_pago(blob)
    fp_norm = _norm_forma_pago(fp_raw)
    if metodo == "PUE" and fp_norm == "99":
        pue99_rows.append(
            {
                "Fecha": row.get("Fecha", ""),
                "RFC Emisor": row.get("RFC Emisor", ""),
                "Nombre Emisor": row.get("Nombre Emisor", ""),
                "UUID": row.get("UUID", ""),
                "cfdi:Concepto Importe": row.get("cfdi:Concepto Importe", 0),
                "cfdi:Traslado Importe": row.get("cfdi:Traslado Importe", 0),
                "FormaPago": fp_norm,
                "MetodoPago": metodo,
            }
        )
pue99_df = pd.DataFrame(pue99_rows, columns=cols_pue99) if pue99_rows else pd.DataFrame(columns=cols_pue99)

DATASETS: List[Tuple[str, pd.DataFrame, str]] = [
    ("No Coinciden", mismatches, "CFDI con diferente regimen fiscal"),
    ("Arrendamiento sin Predial", arrend_df, "CFDI de arrendamiento sin Cuenta Predial"),
    ("Efectivo > 2000", efectivo_df, "CFDI con gasto total en efectivo mayor a 2000"),
    ("Domicilio vs CP", domcp_df, "CFDI con diferente domicilio fiscal vs CP ingresado"),
    ("Sin Retenciones 001-002 (626)", sin_ret_df, "Regimen 626 sin retenciones 001/002"),
    ("Uso CFDI S01 No Deducible", uso_df, "Uso CFDI S01 no deducible"),
    ("Tipo de Cambio Diferente", tc_df, "Tipo de cambio diferente al DOF"),
    ("USD (Todos)", usd_all_df, "CFDI en USD con referencia DOF"),
    ("NC != Condonacion/PUE", nc_df, "Notas de credito con forma/metodo distinto a condonacion y PUE"),
    ("PUE FP 99", pue99_df, "PUE con forma de pago por definir"),
]

if any(not data.empty for _, data, _ in DATASETS):
    def _build_excel() -> bytes:
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            for sheet, data, title in DATASETS:
                _write_sheet(writer, data, sheet, title)
        return out.getvalue()

    st.download_button(
        "Descargar Excel",
        _build_excel(),
        file_name="cfdi_extract.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
else:
    st.info("No hay filas para exportar en las hojas configuradas.")
