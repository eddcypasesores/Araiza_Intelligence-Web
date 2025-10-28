"""Gestion del archivo Firmes para el modulo de Riesgo Fiscal."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from pages.components.admin import init_admin_section

conn = init_admin_section(
    page_title="Archivo Firmes - Riesgo Fiscal",
    active_top="riesgo_firmes",
    layout="wide",
    show_inicio=False,
    enable_foreign_keys=False,
)
conn.close()

FIRMES_DIR = Path("data/firmes")
FIRMES_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH = FIRMES_DIR / "manifest.json"


def _load_manifest() -> dict[str, str] | None:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _save_manifest(manifest: dict[str, str]) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _clear_previous_versions(current_suffix: str) -> None:
    for previous in FIRMES_DIR.glob("firmes_latest.*"):
        if previous.suffix.lower() != current_suffix.lower():
            try:
                previous.unlink()
            except Exception:
                pass


def _store_uploaded_file(upload) -> Path:
    suffix = Path(upload.name).suffix.lower() or ".csv"
    target = FIRMES_DIR / f"firmes_latest{suffix}"
    target.write_bytes(upload.getvalue())
    _clear_previous_versions(suffix)
    manifest = {
        "filename": upload.name,
        "stored_as": target.name,
        "suffix": suffix,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": str(target.stat().st_size),
    }
    _save_manifest(manifest)
    st.session_state["firmes_manifest"] = manifest
    return target


st.title("Actualizar archivo Firmes")
st.caption(
    "Carga el archivo publicado por el SAT (Firmes.csv o Excel) para que la consulta de lista negra "
    "utilice la version mas reciente."
)

manifest = st.session_state.get("firmes_manifest") or _load_manifest()
if manifest:
    stored_path = FIRMES_DIR / manifest.get("stored_as", "")
    updated = manifest.get("updated_at")
    display_time = (
        datetime.fromisoformat(updated).astimezone().strftime("%d/%m/%Y %H:%M")
        if updated
        else "Fecha desconocida"
    )
    st.success(
        f"Archivo vigente: **{manifest.get('filename', 'Firmes')}** "
        f"(actualizado {display_time}, {stored_path.stat().st_size if stored_path.exists() else 0} bytes)."
    )
else:
    st.info("No hay un archivo Firmes registrado. Carga uno para habilitar los cruces automaticos.")

uploaded = st.file_uploader(
    "Selecciona un archivo CSV o Excel",
    type=["csv", "xls", "xlsx"],
    accept_multiple_files=False,
)

if uploaded is not None:
    target_path = _store_uploaded_file(uploaded)
    st.success(f"Archivo guardado correctamente en {target_path.name}.")

st.divider()
st.write(
    "Una vez actualizado el archivo, regresa a `Lista negra SAT` desde el menu superior "
    "para realizar los cruces de RFC."
)
