# pages/17_Archivo_firmes.py
from __future__ import annotations
import os, json, time, shutil, tempfile
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Cargar Firmes / Exigibles SAT", page_icon="📥", layout="centered")

# --- Dónde guardar (mismo esquema de tu página principal) ---
ROOT_FROM_ENV = os.getenv("APP_DATA_DIR")  # ej: /data/ais_lista_negra_sat
BASE_ROOT = Path(ROOT_FROM_ENV) if ROOT_FROM_ENV else Path(tempfile.gettempdir()) / "ais_lista_negra_sat"
DATA_DIR = BASE_ROOT
FIRMES_DIR = DATA_DIR / "firmes"
EXIGIBLES_DIR = DATA_DIR / "exigibles"
for d in (FIRMES_DIR, EXIGIBLES_DIR):
    d.mkdir(parents=True, exist_ok=True)

FIRMES_MANIFEST_PATH = FIRMES_DIR / "manifest.json"
EXIGIBLES_MANIFEST_PATH = EXIGIBLES_DIR / "manifest.json"

def _write_manifest(manifest_path: Path, stored_as: str) -> None:
    try:
        manifest_path.write_text(json.dumps({"stored_as": stored_as}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _has_rfc_column(uploaded_file) -> bool:
    name = (uploaded_file.name or "").lower()
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, nrows=50, encoding="latin-1")
        elif name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file, nrows=50)
        else:
            return False
        return isinstance(df, pd.DataFrame) and ("RFC" in df.columns)
    except Exception:
        return False

st.title("📥 Cargar archivos SAT: Firmes y Exigibles")
st.caption(f"Destino en servidor: `{DATA_DIR}`")

st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Firmes")
    up_firmes = st.file_uploader("Selecciona archivo de Firmes (.csv/.xlsx/.xls)", type=["csv", "xlsx", "xls"], key="up_firmes")
    if up_firmes is not None:
        if not _has_rfc_column(up_firmes):
            st.error("El archivo de Firmes no parece tener columna 'RFC'. Verifica e intenta de nuevo.")
        else:
            # guardar
            safe_name = f"firmes_{int(time.time())}_{Path(up_firmes.name).name}"
            dest = FIRMES_DIR / safe_name
            up_firmes.seek(0)
            with dest.open("wb") as fh:
                shutil.copyfileobj(up_firmes, fh, length=1024*1024)
            _write_manifest(FIRMES_MANIFEST_PATH, safe_name)
            st.success(f"Firmes cargado como: {safe_name}")
            st.caption(f"Guardado en: {dest}")

with col2:
    st.subheader("Exigibles")
    up_exig = st.file_uploader("Selecciona archivo de Exigibles (.csv/.xlsx/.xls)", type=["csv", "xlsx", "xls"], key="up_exigibles")
    if up_exig is not None:
        if not _has_rfc_column(up_exig):
            st.error("El archivo de Exigibles no parece tener columna 'RFC'. Verifica e intenta de nuevo.")
        else:
            # guardar
            safe_name = f"exigibles_{int(time.time())}_{Path(up_exig.name).name}"
            dest = EXIGIBLES_DIR / safe_name
            up_exig.seek(0)
            with dest.open("wb") as fh:
                shutil.copyfileobj(up_exig, fh, length=1024*1024)
            _write_manifest(EXIGIBLES_MANIFEST_PATH, safe_name)
            st.success(f"Exigibles cargado como: {safe_name}")
            st.caption(f"Guardado en: {dest}")

st.markdown("---")
st.info("Cuando termines de subir, vuelve a la página **EFOS / Lista Negra** y usa el botón **“Re-escanear archivos SAT (Firmes/Exigibles)”** si es necesario.")
