"""Gestión del archivo Firmes para el módulo de Monitoreo especializado de EFOS."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from core.auth import persist_login
from core.db import portal_set_password
from core.streamlit_compat import rerun
from pages.components.admin import init_admin_section


def _enforce_password_change(conn) -> None:
    if not st.session_state.get("must_change_password"):
        return

    st.warning("Debes actualizar tu contraseña antes de administrar el archivo Firmes.")
    with st.form("firmes_force_password_change", clear_on_submit=False):
        new_password = st.text_input("Nueva contraseña", type="password")
        confirm_password = st.text_input("Confirmar contraseña", type="password")
        submitted = st.form_submit_button("Actualizar contraseña", use_container_width=True)

    if not submitted:
        st.stop()

    new_password = (new_password or "").strip()
    confirm_password = (confirm_password or "").strip()
    if len(new_password) < 8:
        st.error("La contraseña debe tener al menos 8 caracteres.")
        st.stop()
    if new_password != confirm_password:
        st.error("Las contraseñas no coinciden.")
        st.stop()

    try:
        portal_set_password(
            conn,
            st.session_state.get("usuario", "") or "",
            new_password,
            require_change=False,
        )
        permisos_actuales = st.session_state.get("permisos") or []
        persist_login(
            st.session_state.get("usuario", ""),
            permisos_actuales,
            must_change_password=False,
            user_id=st.session_state.get("portal_user_id"),
        )
        st.success("Contraseña actualizada correctamente.")
        rerun()
    except Exception as exc:
        st.error(f"No fue posible actualizar la contraseña: {exc}")
        st.stop()


conn = init_admin_section(
    page_title="Archivo Firmes - Monitoreo especializado de EFOS",
    active_top="monitoreo_firmes",
    layout="wide",
    show_inicio=False,
    enable_foreign_keys=False,
)

_enforce_password_change(conn)
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
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


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
    "Carga el archivo publicado por el SAT (Firmes.csv o Excel) para que el cruce de lista negra utilice la versión "
    "más reciente."
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
    size_bytes = stored_path.stat().st_size if stored_path.exists() else 0
    st.success(
        f"Archivo vigente: **{manifest.get('filename', 'Firmes')}** "
        f"(actualizado {display_time}, {size_bytes} bytes)."
    )
else:
    st.info("No hay un archivo Firmes registrado. Carga uno para habilitar los cruces automáticos.")

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
    "Una vez actualizado el archivo, regresa a `Lista negra SAT` desde el menú superior "
    "para ejecutar nuevamente los cruces de RFC."
)
