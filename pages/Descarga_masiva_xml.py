# pages/Descarga_masiva_xml.py
from __future__ import annotations
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime
from pathlib import Path
import base64

import streamlit as st
import pandas as pd

# --- Autenticación (mismo flujo que 1_Calculadora.py)
try:
    from core.auth import (
        ensure_session_from_token,
        authenticate_portal_user,
        persist_login,
    )
    # user_has_permission es opcional; si no existe, lo manejamos abajo
    try:
        from core.auth import user_has_permission as _user_has_permission
    except Exception:
        _user_has_permission = None
except Exception:
    # Si no está disponible core.auth en tu entorno local, el login mínimo se degrada
    ensure_session_from_token = lambda: None
    authenticate_portal_user = None
    persist_login = None
    _user_has_permission = None

# ──────────────────────────────────────────────────────────────────────────────
# Configuración de página
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Descarga masiva XML | Araiza Intelligence",
                   layout="wide", initial_sidebar_state="collapsed")

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_CANDIDATES = [
    ASSETS_DIR / "logo_nav.png",
    ASSETS_DIR / "Araiza Intelligence logo-04.png",
    ASSETS_DIR / "logo.png",
]

REQUIRED_PERMISSION = "xml"  # ajusta al nombre real de tu permiso, si aplica

# ──────────────────────────────────────────────────────────────────────────────
# CSS GLOBAL – Ocultar UI nativa de Streamlit y barra superior fija
# ──────────────────────────────────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
  /* Oculta interfaz nativa de Streamlit */
  [data-testid="stSidebar"], [data-testid="stSidebarNav"],
  header[data-testid="stHeader"], div[data-testid="stToolbar"],
  #MainMenu, #stDecoration, footer, [data-testid="stStatusWidget"],
  .viewerBadge_container__1QSob, .stDeployButton { display:none !important; visibility:hidden !important; }

  /* Evitar sangría del main al ocultar sidebar */
  @media (min-width: 0px){
    section[data-testid="stSidebar"] + div[role="main"] { margin-left:0 !important; }
  }
  section.main > div.block-container { padding-top: 0.75rem !important; }

  /* Barra superior fija */
  .ai-navbar {
    position: fixed; top: 0.5rem; left: 50%; transform: translateX(-50%);
    width: min(1100px, 100%); padding: 10px 18px; border-radius: 999px;
    background: #ffffff; color:#0f172a; z-index:1000;
    display:flex; align-items:center; justify-content:space-between; gap:16px;
    box-shadow: 0 18px 32px rgba(15,23,42,.18); border: 1px solid rgba(148,163,184,.25);
    font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Helvetica Neue", Arial;
  }
  .ai-left { display:flex; align-items:center; gap:12px; }
  .ai-left img { height:28px; width:auto; display:block; }
  .ai-title { font-weight:800; letter-spacing:.02em; }
  .ai-actions { display:flex; align-items:center; gap:8px; }
  .ai-btn {
    display:inline-flex; align-items:center; justify-content:center;
    padding:8px 16px; border-radius:999px; background:#0d3c74; color:#fff;
    font-weight:600; text-decoration:none; border:none; cursor:pointer;
    box-shadow:0 6px 16px rgba(13,60,116,.25);
  }
  .ai-btn:hover { filter: brightness(.95); }
  .ai-nav-spacer { height: 92px; }
</style>
"""
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Navbar (logo + título + Cerrar sesión)
#   - El botón dispara ?logout=1 para limpiar sesión y redirigir a pages/0_Inicio.py
# ──────────────────────────────────────────────────────────────────────────────
def _logo_b64() -> str | None:
    for p in LOGO_CANDIDATES:
        if p.exists():
            try:
                return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
            except Exception:
                pass
    return None

def _is_logged_in() -> bool:
    # Usa el estado que maneje tu core.auth; soporta varias llaves típicas
    return any(k in st.session_state for k in ("user", "usuario", "auth_user", "auth_token"))

def _has_required_permission(user_obj, perm: str) -> bool:
    if not perm:
        return True
    if _user_has_permission is None:
        # Si no existe la función en tu core.auth, no bloqueamos por permiso
        return True
    try:
        return _user_has_permission(user_obj, perm)
    except Exception:
        return True

# Handler de logout por query param
try:
    qp = dict(st.query_params)  # Streamlit >= 1.32
except Exception:
    qp = st.experimental_get_query_params()

if qp.get("logout") in (["1"], "1", 1, True):
    st.session_state.clear()
    try:
        st.switch_page("pages/0_Inicio.py")
    except Exception:
        st.stop()

logo_src = _logo_b64()
logout_href = "?logout=1"
st.markdown(
    f"""
    <div class="ai-navbar">
      <div class="ai-left">
        {'<img src="'+logo_src+'" alt="Araiza"/>' if logo_src else ''}
        <div class="ai-title">Araiza Intelligence</div>
      </div>
      <div class="ai-actions">
        <a class="ai-btn" href="{logout_href}" target="_self">Cerrar sesión</a>
      </div>
    </div>
    <div class="ai-nav-spacer"></div>
    """,
    unsafe_allow_html=True
)

# ──────────────────────────────────────────────────────────────────────────────
# Login (mismo flujo mental que 1_Calculadora.py)
# ──────────────────────────────────────────────────────────────────────────────
def _render_login():
    st.title("Iniciar sesión")
    st.caption("Autentícate para continuar con la descarga masiva de XML.")

    col1, col2 = st.columns([1,1])
    with col1:
        rfc = st.text_input("RFC", placeholder="XAXX010101000").strip()
    with col2:
        pwd = st.text_input("Contraseña", type="password")

    c1, c2 = st.columns([1,1])
    go = c1.button("Entrar", type="primary", use_container_width=True)
    cancel = c2.button("Cancelar", use_container_width=True)

    if cancel:
        try:
            st.switch_page("pages/0_Inicio.py")
        except Exception:
            st.stop()

    if go:
        if not authenticate_portal_user:
            st.error("El módulo de autenticación no está disponible en este entorno.")
            st.stop()
        try:
            user_obj = authenticate_portal_user(rfc, pwd)
        except Exception as e:
            st.error(f"Credenciales inválidas o error de autenticación. {e}")
            st.stop()
            return

        if not user_obj:
            st.error("RFC o contraseña incorrectos.")
            st.stop()
            return

        # Verificar permiso del módulo (si tu core.auth lo maneja)
        if not _has_required_permission(user_obj, REQUIRED_PERMISSION):
            st.error("Tu usuario no tiene permiso para 'Descarga masiva de XML'.")
            st.stop()
            return

        try:
            persist_login(user_obj)
        except Exception:
            # fallback mínimo
            st.session_state["user"] = user_obj

        st.rerun()

# Hidratar sesión desde token si viene en la URL
try:
    ensure_session_from_token()
except Exception:
    pass

if not _is_logged_in():
    _render_login()
    st.stop()

# ──────────────────────────────────────────────────────────────────────────────
# Lógica: Parse CFDI 4.0 y exportación a Excel (igual que tu versión anterior)
# ──────────────────────────────────────────────────────────────────────────────
def parse_cfdi_xml(file_bytes: bytes):
    ns = {
        "cfdi": "http://www.sat.gob.mx/cfd/4",
        "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
        "implocal": "http://www.sat.gob.mx/implocal",
    }
    root = ET.fromstring(file_bytes)

    comp = root.attrib
    emisor_node = root.find("cfdi:Emisor", ns); emisor = emisor_node.attrib if emisor_node is not None else {}
    receptor_node = root.find("cfdi:Receptor", ns); receptor = receptor_node.attrib if receptor_node is not None else {}
    complemento_node = root.find("cfdi:Complemento", ns)

    tfd_node = complemento_node.find("tfd:TimbreFiscalDigital", ns) if complemento_node is not None else None
    tfd = tfd_node.attrib if tfd_node is not None else {}

    impuestos_node = root.find("cfdi:Impuestos", ns)
    total_impuestos_trasladados = None; retencion_001 = None; retencion_002 = None
    iva_8 = None; ish_importe = None

    if impuestos_node is not None:
        total_impuestos_trasladados = impuestos_node.attrib.get("TotalImpuestosTrasladados")

        retenciones_node = impuestos_node.find("cfdi:Retenciones", ns)
        if retenciones_node is not None:
            for ret in retenciones_node.findall("cfdi:Retencion", ns):
                imp_clave = ret.attrib.get("Impuesto"); imp_importe = ret.attrib.get("Importe")
                if imp_clave == "001": retencion_001 = imp_importe
                elif imp_clave == "002": retencion_002 = imp_importe

        traslados_node = impuestos_node.find("cfdi:Traslados", ns)
        if traslados_node is not None:
            for tras in traslados_node.findall("cfdi:Traslado", ns):
                impuesto_clave = tras.attrib.get("Impuesto"); tasa = tras.attrib.get("TasaOCuota")
                if impuesto_clave == "002" and tasa and tasa.startswith("0.08"):
                    iva_8 = tras.attrib.get("Importe")

    if complemento_node is not None:
        impuestos_locales_node = complemento_node.find("implocal:ImpuestosLocales", ns)
        if impuestos_locales_node is not None:
            for loc_tr in impuestos_locales_node.findall("implocal:TrasladosLocales", ns):
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
                traslados = imp_node.find("cfdi:Traslados", ns)
                if traslados is not None:
                    traslado = traslados.find("cfdi:Traslado", ns)
                    if traslado is not None:
                        iva_base = traslado.attrib.get("Base")
                        iva_tasa = traslado.attrib.get("TasaOCuota")
                        iva_importe = traslado.attrib.get("Importe")

            conceptos_rows.append({
                "UUID": tfd.get("UUID"),
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

# ──────────────────────────────────────────────────────────────────────────────
# UI: carga de archivos y descarga
# ──────────────────────────────────────────────────────────────────────────────
st.title("Descarga masiva de XML (CFDI) a Excel")
st.caption("Sube uno o varios CFDI 4.0 en XML y descarga un Excel con encabezados y conceptos.")

xml_files = st.file_uploader("Selecciona tus XML", type=["xml"], accept_multiple_files=True)

if xml_files:
    registros_encabezado, registros_conceptos = [], []
    for uploaded in xml_files:
        file_bytes = uploaded.read()
        try:
            enc, conc = parse_cfdi_xml(file_bytes)
            registros_encabezado.append(enc)
            registros_conceptos.extend(conc)
        except Exception as e:
            st.error(f"Archivo inválido ({uploaded.name}): {e}")

    df_cfdis = pd.DataFrame(registros_encabezado)
    df_conceptos = pd.DataFrame(registros_conceptos)

    # Numéricos + regla IVA 8%
    columnas_numericas = ["SubTotal","Descuento","TotalImpuestosTrasladados","IVA 8%","ISH","Retencion_001","Retencion_002","Total"]
    for col in columnas_numericas:
        if col not in df_cfdis.columns:
            df_cfdis[col] = 0
        df_cfdis[col] = pd.to_numeric(df_cfdis[col], errors="coerce").fillna(0)

    if "FechaTimbrado" in df_cfdis.columns:
        df_cfdis["FechaTimbrado"] = pd.to_datetime(df_cfdis["FechaTimbrado"], errors="coerce")

    df_cfdis.loc[df_cfdis["IVA 8%"] > 0, "TotalImpuestosTrasladados"] = 0

    # Orden sugerido
    cols_preferidas = [
        "Version","TipoDeComprobante","Fecha","FechaTimbrado","Emisor_Rfc","Emisor_Nombre","UUID","Serie","Folio",
        "SubTotal","Descuento","TotalImpuestosTrasladados","IVA 8%","ISH","Retencion_001","Retencion_002","Total",
        "Emisor_RegimenFiscal","Receptor_DomicilioFiscalReceptor","Moneda","FormaPago","MetodoPago","CondicionesDePago",
        "LugarExpedicion","Exportacion","RfcProvCertif","NoCertificado","Receptor_Rfc","Receptor_Nombre",
        "Receptor_UsoCFDI","Receptor_RegimenFiscalReceptor",
    ]
    ordered_cols = [c for c in cols_preferidas if c in df_cfdis.columns] + [c for c in df_cfdis.columns if c not in cols_preferidas]
    df_cfdis = df_cfdis[ordered_cols]

    # Construir Excel en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_cfdis.to_excel(writer, index=False, sheet_name="CFDIs")
        df_conceptos.to_excel(writer, index=False, sheet_name="Conceptos")

        # Formato corto dd/mm/aaaa para FechaTimbrado
        ws = writer.sheets["CFDIs"]
        if "FechaTimbrado" in df_cfdis.columns:
            col_idx = df_cfdis.columns.get_loc("FechaTimbrado") + 1
            for row_idx in range(2, len(df_cfdis) + 2):
                cell = ws.cell(row=row_idx, column=col_idx)
                if isinstance(cell.value, pd.Timestamp):
                    cell.value = cell.value.to_pydatetime().date()
                elif isinstance(cell.value, datetime):
                    cell.value = cell.value.date()
                cell.number_format = "DD/MM/YYYY"

    st.download_button(
        "📥 Descargar Excel",
        data=output.getvalue(),
        file_name="CFDIs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
else:
    st.info("Sube uno o varios XML para generar el Excel.")
