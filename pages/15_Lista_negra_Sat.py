# pages/15_Lista_negra_Sat.py
from __future__ import annotations

import io
import json
import threading
import time
import zipfile
from zipfile import BadZipFile
from contextlib import closing
from pathlib import Path
from typing import Dict, Any, Optional, List

import streamlit as st

# -----------------------------------------------------------------------------
# Config básica
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Lista Negra SAT — Carga masiva",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Rutas locales de trabajo (carpeta temporal dentro de .streamlit cache/user-data)
BASE_DIR = Path.cwd()
DATA_DIR = BASE_DIR / ".data_lista_negra_sat"
UPLOAD_DIR = DATA_DIR / "uploads"
JOBS_DIR = DATA_DIR / "jobs"
for d in (DATA_DIR, UPLOAD_DIR, JOBS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Límite de tamaño recomendado (opcional)
MAX_MB = 250  # ajusta según tu hosting

# Estado global de trabajos en segundo plano (vive mientras el proceso de Streamlit exista)
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


# -----------------------------------------------------------------------------
# Utilidades de estado
# -----------------------------------------------------------------------------
def ss() -> Dict[str, Any]:
    """Alias corto para st.session_state."""
    return st.session_state


def now_ms() -> int:
    return int(time.time() * 1000)


def reset_ui_state():
    """Limpia por completo el estado de la pantalla."""
    keep_keys = set()  # si quieres preservar algo, añádelo aquí
    for k in list(ss().keys()):
        if k not in keep_keys:
            del ss()[k]
    # Forzar una nueva clave del uploader para que quede "limpio"
    ss()["uploader_nonce"] = now_ms()
    ss()["zip_indexing"] = False
    ss()["zip_done"] = False
    ss()["zip_error"] = None
    ss()["zip_job_id"] = None
    ss()["zip_last_summary"] = None


def ensure_defaults():
    if "uploader_nonce" not in ss():
        reset_ui_state()


# -----------------------------------------------------------------------------
# Lógica de trabajos (thread en segundo plano)
# -----------------------------------------------------------------------------
def _register_job(job: Dict[str, Any]):
    with JOBS_LOCK:
        JOBS[job["id"]] = job


def _get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with JOBS_LOCK:
        return JOBS.get(job_id)


def _update_job(job_id: str, **kwargs):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        job.update(kwargs)


def _cancel_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is not None:
            job["cancel_flag"] = True


def _remove_job(job_id: str):
    with JOBS_LOCK:
        JOBS.pop(job_id, None)


def _human_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    kb = nbytes / 1024
    if kb < 1024:
        return f"{kb:.2f} KB"
    mb = kb / 1024
    if mb < 1024:
        return f"{mb:.2f} MB"
    gb = mb / 1024
    return f"{gb:.2f} GB"


def process_zip_job(job_id: str, zip_path: Path, batch: int = 300):
    """
    Worker que procesa el ZIP en segundo plano.

    Aquí puedes hacer el parse real de XML y la lógica de indexado/validación EFOS.
    Dejamos una implementación base que lista los archivos del ZIP y simula trabajo por lotes.
    """
    try:
        _update_job(job_id, status="running", progress=0.0, message="Abriendo ZIP…")

        # Abrimos el ZIP con manejo de corrupción
        with zip_path.open("rb") as f:
            try:
                with zipfile.ZipFile(f) as zf:
                    all_names = [n for n in zf.namelist() if not n.endswith("/")]
            except BadZipFile as e:
                _update_job(job_id, status="error", message=f"El archivo ZIP está dañado o no es válido: {e}")
                return

        total = len(all_names)
        if total == 0:
            _update_job(job_id, status="error", message="El ZIP no contiene archivos.")
            return

        _update_job(job_id, total=total, processed=0, status="running", message="Procesando archivos…")

        processed = 0
        # Simulación de trabajo en lotes; aquí harías el parseo real de cada XML
        for i in range(0, total, batch):
            # Cancelación (si el usuario aprieta "Cancelar")
            job = _get_job(job_id)
            if job and job.get("cancel_flag"):
                _update_job(job_id, status="cancelled", message="Trabajo cancelado por el usuario.")
                return

            chunk = all_names[i : i + batch]
            # Aquí podrías abrir cada archivo del chunk
            # p.ej.: for name in chunk: with zf.open(name) as fh: parse_xml(fh.read())

            # Simulamos trabajo: dormir un poco para no saturar CPU
            time.sleep(0.15)

            processed += len(chunk)
            progress = min(1.0, processed / max(1, total))
            _update_job(
                job_id,
                processed=processed,
                progress=progress,
                message=f"Procesando… {processed}/{total}",
            )

        # Si llegamos aquí, terminó bien
        last_summary = {
            "total_archivos": total,
            "tipo_zip": "XML (estimado por nombres)",  # ajusta si clasificas
            "ejemplo_primeros": all_names[:5],
        }
        _update_job(job_id, status="done", progress=1.0, message="Completado.", summary=last_summary)

    except Exception as exc:
        _update_job(job_id, status="error", message=f"Error inesperado: {exc}")

    finally:
        # Opcional: borra el archivo cargado para ahorrar espacio
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass


def start_zip_job(zip_path: Path, batch: int = 300) -> str:
    """Registra y lanza un worker en segundo plano para procesar el ZIP."""
    job_id = f"job_{now_ms()}"
    job = {
        "id": job_id,
        "status": "queued",
        "created_at": now_ms(),
        "zip_path": str(zip_path),
        "progress": 0.0,
        "message": "En cola…",
        "cancel_flag": False,
        "processed": 0,
        "total": None,
        "summary": None,
    }
    _register_job(job)

    t = threading.Thread(
        target=process_zip_job,
        kwargs={"job_id": job_id, "zip_path": zip_path, "batch": batch},
        daemon=True,
    )
    t.start()
    return job_id


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
ensure_defaults()

st.title("EFOS / Lista Negra SAT — Carga masiva (ZIP)")
st.write(
    "Sube tu archivo **.zip** con XML y presiona **Procesar ZIP**. "
    "El procesamiento se hace en segundo plano para evitar timeouts del proxy (502)."
)

# Tarjeta: Carga masiva
st.markdown("---")
st.subheader("1) Carga masiva (ZIP con miles de XML)")

col_up1, col_up2 = st.columns([0.7, 0.3])
with col_up1:
    zip_uploader_key = f"zip_bulk_uploader_{ss()['uploader_nonce']}"
    uploaded = st.file_uploader(
        "Sube tu .zip (se procesará al presionar el botón)",
        type=["zip"],
        accept_multiple_files=False,
        key=zip_uploader_key,
        label_visibility="collapsed",
    )
with col_up2:
    if uploaded is not None:
        size_mb = (getattr(uploaded, "size", 0) or 0) / (1024 * 1024)
        st.caption(f"Archivo listo: **{uploaded.name}** · {_human_size(getattr(uploaded, 'size', 0) or 0)}")
        if size_mb > MAX_MB:
            st.warning(
                f"El ZIP pesa {size_mb:.1f} MB (> {MAX_MB} MB). "
                "Te recomiendo dividirlo para evitar errores 502 en el hosting."
            )

# Botones de acción
col_btn1, col_btn2, col_btn3 = st.columns([0.5, 0.25, 0.25])

def _store_uploaded_to_disk(up) -> Optional[Path]:
    """Copia el archivo subido a UPLOAD_DIR en trozos de 1MB para evitar picos de memoria."""
    if up is None:
        return None
    safe_name = Path(getattr(up, "name", "upload.zip") or "upload.zip").name
    dest = UPLOAD_DIR / f"{now_ms()}_{safe_name}"
    try:
        # Volvemos al inicio del buffer del uploader (si soporta seek)
        try:
            up.seek(0)
        except Exception:
            pass
        with dest.open("wb") as fh:
            while True:
                chunk = up.read(1024 * 1024)  # 1 MB
                if not chunk:
                    break
                fh.write(chunk)
        try:
            up.seek(0)
        except Exception:
            pass
        return dest
    except Exception as exc:
        try:
            dest.unlink()
        except Exception:
            pass
        st.error(f"No fue posible almacenar el ZIP seleccionado. Detalle: {exc}")
        return None


with col_btn1:
    disabled = uploaded is None or ss().get("zip_indexing", False)
    if st.button("Procesar ZIP", use_container_width=True, disabled=disabled):
        # Cancela un trabajo previo (si existiera)
        prev = ss().pop("zip_job_id", None)
        if prev:
            _cancel_job(prev)
        # Guarda a disco
        path = _store_uploaded_to_disk(uploaded)
        if path is not None:
            job_id = start_zip_job(path, batch=300)
            ss()["zip_job_id"] = job_id
            ss()["zip_indexing"] = True
            ss()["zip_done"] = False
            ss()["zip_error"] = None

with col_btn2:
    if ss().get("zip_indexing", False):
        if st.button("Cancelar", use_container_width=True):
            jid = ss().get("zip_job_id")
            if jid:
                _cancel_job(jid)
            ss()["zip_indexing"] = False
            ss()["zip_done"] = False
            ss()["zip_error"] = "Trabajo cancelado por el usuario."

with col_btn3:
    if st.button("Reiniciar", use_container_width=True):
        reset_ui_state()
        st.rerun()

st.markdown("---")

# Progreso / Estado del trabajo
jid = ss().get("zip_job_id")
if jid:
    job = _get_job(jid)
    if job is None:
        st.info("No se encontró el estado del trabajo. Es posible que el proceso del servidor se haya reiniciado.")
    else:
        status = job.get("status")
        msg = job.get("message", "")
        progress = job.get("progress", 0.0)
        processed = job.get("processed", 0)
        total = job.get("total")

        if status in {"queued", "running"}:
            st.subheader("2) Progreso")
            st.progress(progress)
            st.caption(f"{msg}")
            if total:
                st.caption(f"Archivos procesados: {processed} / {total}")
            # *Polling* más suave para evitar 502 / presión de CPU
            time.sleep(0.7)
            st.rerun()

        elif status == "done":
            ss()["zip_indexing"] = False
            ss()["zip_done"] = True
            ss()["zip_last_summary"] = job.get("summary")
            st.success("Procesamiento completado.")
            st.json(job.get("summary", {}))

        elif status == "error":
            ss()["zip_indexing"] = False
            ss()["zip_done"] = False
            ss()["zip_error"] = msg or "Ocurrió un error durante el procesamiento."
            st.error(ss()["zip_error"])

        elif status == "cancelled":
            ss()["zip_indexing"] = False
            ss()["zip_done"] = False
            ss()["zip_error"] = "Trabajo cancelado por el usuario."
            st.warning(ss()["zip_error"])

else:
    # Pantalla inicial / sin trabajo activo
    st.info("Sube un ZIP y presiona **Procesar ZIP** para comenzar.")

# Resumen final (si existe de una corrida previa)
if ss().get("zip_done") and ss().get("zip_last_summary"):
    st.markdown("---")
    st.subheader("Resumen de la última ejecución")
    st.json(ss()["zip_last_summary"])
