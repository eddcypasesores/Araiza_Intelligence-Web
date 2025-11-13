from __future__ import annotations

import base64
import mimetypes
import os
import tempfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from core.theme import apply_theme
from core.auth import ensure_session_from_token, auth_query_params
from core.custom_nav import render_brand_logout_nav
from core.extractor_banbajio import extraer_movimientos

ASSETS_DIR = next((p for p in (Path("Assets"), Path("assets")) if p.exists()), Path("."))
LEFT_LOGO_PATH = ASSETS_DIR / "logo.jpg"
RIGHT_LOGO_PATH = ASSETS_DIR / "banks/banbajio.jpeg"


def _back_href() -> str:
    params = auth_query_params()
    query = urlencode(params) if params else ""
    base = "./convertidor_estados_cuenta"
    return f"{base}?{query}" if query else base


def img_to_data_uri(path: Path) -> str | None:
    if not path.exists():
        return None
    mime, _ = mimetypes.guess_type(path.name)
    mime = mime or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def excel_por_cuenta_bytes(df: pd.DataFrame) -> bytes:
    """Genera un Excel en memoria con una hoja por cada cuenta."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        if "Cuenta" not in df.columns:
            df.to_excel(writer, index=False, sheet_name="Movimientos")
        else:
            for cuenta, dfc in df.groupby("Cuenta", dropna=False):
                nombre = str(cuenta).strip() if pd.notna(cuenta) and str(cuenta).strip() else "SIN_CUENTA"
                hoja = nombre[:31]
                dfc.drop(columns=["Cuenta", "Detalle"], errors="ignore").to_excel(writer, index=False, sheet_name=hoja)
    buffer.seek(0)
    return buffer.getvalue()


def _render_nav() -> None:
    render_brand_logout_nav(
        "pages/convertidor_estados_cuenta.py",
        brand="Extractor BanBajío",
        action_label="Atrás",
        action_href=_back_href(),
    )


st.set_page_config(page_title="Extractor BanBajío", layout="wide")
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
    #root > div:nth-child(1) > div[data-testid="stSidebarNav"] { display:none !important; }
    body, html, [data-testid="stAppViewContainer"] { background:#f5f6fb !important; }
    .block-container { padding-top:80px !important; max-width:980px; }

    /* Header con logos */
    .header {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:24px;
      margin:8px 0 24px 0;
    }
    .header .cell {
      display:flex;
      align-items:center;
      justify-content:center;
    }
    .header .logo {
      height:120px;
      object-fit:contain;
    }
    .header .title {
      text-align:center;
      font-weight:800;
      color:#0f172a;
      font-size:48px;
      line-height:1.1;
      margin:0;
    }

    .divider { height:1px; background:#e5e7eb; margin:8px 0 12px 0; }
    .section-title { font-weight:600; color:#111827; font-size:14px; margin:6px 0 12px 0; }
    .hint {
      background:#eaf2ff;
      border:1px solid #d9e6ff;
      border-radius:8px;
      padding:14px 16px;
      color:#0f1d40;
      margin-top:10px;
    }
    [data-testid="stFileUploader"] button {
        background-color:#579EF7;
        color:#fff;
        border-radius:8px;
        padding:8px 16px;
    }
    [data-testid="stFileUploader"] button:hover { background-color:#3f89e0; }
    </style>
    """,
    unsafe_allow_html=True,
)

left_logo_uri = img_to_data_uri(LEFT_LOGO_PATH)
right_logo_uri = img_to_data_uri(RIGHT_LOGO_PATH)

st.markdown(
    f"""
    <div class="header">
        <div class="cell" style="width:18%;">
            {'<img class="logo" src="'+left_logo_uri+'" alt="Logo Araiza">' if left_logo_uri else ''}
        </div>
        <div class="cell" style="flex:1;">
            <h1 class="title">EXTRACTOR BANBAJÍO</h1>
        </div>
        <div class="cell" style="width:18%;">
            {'<img class="logo" src="'+right_logo_uri+'" alt="Logo BanBajío">' if right_logo_uri else ''}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">Sube tu PDF de BanBajío</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("", type=["pdf"], label_visibility="collapsed")

if uploaded_file is None:
    st.markdown('<div class="hint">Sube un PDF para comenzar.</div>', unsafe_allow_html=True)
else:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        df = extraer_movimientos(tmp_path)

        if df.empty:
            st.warning("No se detectaron movimientos en el PDF. Verifica el archivo.")
        else:
            if "Cuenta" in df.columns:
                cuentas = [
                    str(cuenta).strip() if pd.notna(cuenta) and str(cuenta).strip() else "SIN_CUENTA"
                    for cuenta in df["Cuenta"].drop_duplicates()
                ]
                st.caption("Cuentas detectadas: " + ", ".join(cuentas))

            st.subheader("📊 Vista previa (primeras filas)")
            st.dataframe(df.head(200), use_container_width=True)

            data_xlsx = excel_por_cuenta_bytes(df)
            st.download_button(
                label="⬇️ Descargar Excel (una hoja por cuenta)",
                data=data_xlsx,
                file_name="movimientos_banbajio_por_cuenta.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    except Exception as exc:
        st.error(f"Ocurrió un error al procesar el PDF: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
