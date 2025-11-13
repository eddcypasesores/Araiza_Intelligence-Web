from __future__ import annotations

import base64
import mimetypes
import os
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from core.theme import apply_theme
from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import render_brand_logout_nav
from extractor import extraer_datos_banamex_formato_final

ASSETS_DIR = next((p for p in (Path("Assets"), Path("assets")) if p.exists()), Path("."))
LEFT_LOGO = ASSETS_DIR / "logo.jpg"
RIGHT_LOGO = ASSETS_DIR / "banks/banamex.jpeg"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _back_href() -> str:
    params = auth_query_params()
    query = urlencode(params) if params else ""
    base = "./convertidor_estados_cuenta"
    return f"{base}?{query}" if query else base


def _img_to_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    mime, _ = mimetypes.guess_type(path.name)
    mime = mime or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{encoded}"


def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Banamex")
    buf.seek(0)
    return buf.getvalue()


def _totals(df: pd.DataFrame) -> dict[str, float]:
    cargos = pd.to_numeric(df.get("Cargo"), errors="coerce").fillna(0).sum()
    abonos = pd.to_numeric(df.get("Abono"), errors="coerce").fillna(0).sum()
    saldos = pd.to_numeric(df.get("Saldo"), errors="coerce").dropna()
    saldo_final = float(saldos.iloc[-1]) if not saldos.empty else cargos - abonos
    return {"cargos": float(cargos), "abonos": float(abonos), "saldo": saldo_final}


def _render_nav() -> None:
    render_brand_logout_nav(
        "pages/convertidor_estados_cuenta.py",
        brand="Extractor Banamex",
        action_label="Atrás",
        action_href=_back_href(),
    )


st.set_page_config(page_title="Extractor Banamex", layout="wide")
apply_theme()
ensure_session_from_token()
_render_nav()

st.markdown(
    """
    <style>
      [data-testid="stSidebar"],
      header[data-testid="stHeader"],
      div[data-testid="stToolbar"],
      #MainMenu,
      [data-testid="collapsedControl"],
      #root > div:nth-child(1) > div[data-testid="stSidebarNav"] {
        display:none !important;
      }
      body, html, [data-testid="stAppViewContainer"] {
        background:#f5f6fb !important;
      }
      .block-container{
        max-width:100% !important;
        padding:80px 2rem 2rem;
      }
      .brand-title{
        margin:0;
        text-align:center;
        font-weight:800;
        letter-spacing:.5px;
        line-height:1.1;
        font-size:clamp(34px,4vw,56px);
      }
      .header-flex{
        display:flex; align-items:center; justify-content:space-between;
        gap:2rem; margin-bottom:.75rem;
      }
      hr.header-sep{
        margin:.75rem 0 1rem; border:none; height:1px; background:rgba(0,0,0,.08);
      }
      .hint {
        background:#eaf2ff;
        border:1px solid #d9e6ff;
        border-radius:8px;
        padding:14px 16px;
        color:#0f1d40;
        margin-top:10px;
      }
      [data-testid="stMetric"]{ background:#f8f9fa; border-radius:12px; padding:.75rem; }
      [data-testid="stFileUploader"] section{ padding:0 !important; }
      [data-testid="stFileUploader"] button {
        background-color:#579EF7; color:#fff; border-radius:8px; padding:8px 16px;
      }
      [data-testid="stFileUploader"] button:hover { background-color:#3f89e0; }
    </style>
    """,
    unsafe_allow_html=True,
)

left_logo_src = _img_to_data_uri(LEFT_LOGO)
right_logo_src = _img_to_data_uri(RIGHT_LOGO)

c1, c2, c3 = st.columns([1.2, 5, 1.2], gap="large")
with c1:
    if left_logo_src:
        st.markdown(f'<img src="{left_logo_src}" alt="Logo Araiza" style="height:180px;object-fit:contain;">', unsafe_allow_html=True)
with c2:
    st.markdown("<h2 class='brand-title'>EXTRACTOR BANAMEX</h2>", unsafe_allow_html=True)
with c3:
    if right_logo_src:
        st.markdown(f'<img src="{right_logo_src}" alt="Logo Banamex" style="height:180px;object-fit:contain;">', unsafe_allow_html=True)

st.markdown("<hr class='header-sep'/>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Sube tu PDF de Banamex", type=["pdf"])

if uploaded_file is None:
    st.info("👆 Sube un PDF para comenzar.")
else:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        st.info("⏳ Procesando archivo PDF...")
        df = extraer_datos_banamex_formato_final(tmp_path)

        if df is None or df.empty:
            st.warning("⚠ No se detectaron movimientos válidos en el archivo.")
        else:
            st.success("✅ ¡Extracción completada con éxito!")

            st.subheader("📋 Vista previa de movimientos")
            st.caption(f"Mostrando hasta 100 filas de {len(df)} en total.")
            st.dataframe(df.head(100), use_container_width=True)

            summary = _totals(df)
            m1, m2, m3 = st.columns(3)
            m1.metric("💸 Total Cargos", f"${summary['cargos']:,.2f}")
            m2.metric("💰 Total Abonos", f"${summary['abonos']:,.2f}")
            m3.metric("📊 Saldo final estimado", f"${summary['saldo']:,.2f}")

            with st.expander("🔎 Ver tabla completa"):
                st.dataframe(df, use_container_width=True, height=520)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = OUTPUT_DIR / f"banamex_{timestamp}.xlsx"
            data_xlsx = _df_to_excel_bytes(df)
            filename.write_bytes(data_xlsx)

            st.download_button(
                "📥 Descargar Excel",
                data_xlsx,
                file_name=filename.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            st.caption(f"Archivo guardado también en: {filename}")

    except Exception as exc:
        st.error(f"❌ Ocurrió un error al extraer datos: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
