# pages/15_Lista_negra_Sat.py
from __future__ import annotations

import os
import json
import threading
import time
import zipfile
from zipfile import BadZipFile
from pathlib import Path
from typing import Dict, Any, Optional, Iterable
import tempfile

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

# -----------------------------------------------------------------------------
# Rutas de trabajo (Railway-ready)
# Usa un Volume en Railway: APP_DATA_DIR=/data/ais_lista_negra_sat
# Si no existe, cae en /tmp (efímero)
# -----------------------------------------------------------------------------
ROOT_FROM_ENV = os.getenv("APP_DATA_DIR")  # ej: /data/ais_lista_negra_sat
if ROOT_FROM_ENV:
    BASE_ROOT = Path(ROOT_FROM_ENV)
else:
    BASE_ROOT = Path(tempfile.gettempdir()) / "ais_lista_negra_sat"

DATA_DIR = BASE_ROOT
UPLOAD_DIR = DATA_DIR / "uploads"
JOBS_DIR = DATA_DIR / "jobs"
for d in (DATA_DIR, UPLOAD_DIR, JOBS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Parámetros de ejecución
MAX_MB = 250            # límite sugerido (ajústalo a tu plan)
DEFAULT_BATCH = 150     # tamaño de lote reducido para evitar picos
POLL_INTERVAL = 0.7     # s, para polling suave

# Estado global de trabajos (memoria) + lock
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


# -----------------------------------------------------------------------------
# Helpers generales
# -----------------------------------------------------------------------------
def ss() -> Dict[str, Any]:
    return st.session_state


def now_ms() -> int:
    return int(time.time() * 1000)


def _human_size(nbytes: int) -> str:
    try:
        nbytes = int(nbytes)
    except Exception:
        return "—"
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


def reset_ui_state():
    keep = set()
    for k in list(ss().keys()):
        if k not in keep:
            del ss()[k]
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
# Persistencia de JOBS (JSON en disco) — sobrevive reinicios si hay Volume
# -----------------------------------------------------------------------------
def _job_state_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _persist_job(job: Dict[str, Any]) -> None:
    try:
        _job_state_path(job["id"]).write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _load_job_from_disk(job_id: str) -> Optional[Dict[str, Any]]:
    p = _job_state_path(job_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# -----------------------------------------------------------------------------
# CRUD de trabajos (memoria + disco)
# -----------------------------------------------------------------------------
def _register_job(job: Dict[str, Any]):
    with JOBS_LOCK:
        JOBS[job["id"]] = job
        _persist_job(job)


def _get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if job is not None:
        return job
    job = _load_job_from_disk(job_id)
    if job is not None:
        with JOBS_LOCK:
            JOBS[job_id] = job
        return job
    return None


def _update_job(job_id: str, **kwargs):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            job = _load_job_from_disk(job_id)
            if job is None:
                return
            JOBS[job_id] = job
        job.update(kwargs)
        _persist_job(job)


def _cancel_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id) or _load_job_from_disk(job_id)
        if job is not None:
            job["cancel_flag"] = True
            JOBS[job_id] = job
            _persist_job(job)


def _remove_job(job_id: str):
    with JOBS_LOCK:
        JOBS.pop(job_id, None)
    try:
        _job_state_path(job_id).unlink(missing_ok=True)
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Utilidades ZIP (streaming, sin listas gigantes en memoria)
# -----------------------------------------------------------------------------
def _iter_zip_file_names(zip_path: Path) -> Iterable[str]:
    """Genera los nombres de archivo del ZIP (evita listas grandes)."""
    with zip_path.open("rb") as f:
        with zipfile.ZipFile(f) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                yield info.filename


def _open_zip_member(zip_path: Path, member: str) -> bytes:
    """Lee un miembro del ZIP a bytes (cuando sea necesario)."""
    with zip_path.open("rb") as f:
        with zipfile.ZipFile(f) as zf:
            with zf.open(member) as fh:
                return fh.read()


# -----------------------------------------------------------------------------
# Worker (hilo en segundo plano)
# -----------------------------------------------------------------------------
def process_zip_job(job_id: str, zip_path: Path, batch: int = DEFAULT_BATCH):
    """
    Procesa el ZIP (en segundo plano).
    Integra aquí el parseo real de CFDI + cruces EFOS/Lista Negra + exportaciones.
    """
    try:
        _update_job(job_id, status="running", progress=0.0, message="Abriendo ZIP…")

        # 1) Contar archivos sin construir listas
        total = 0
        try:
            for _ in _iter_zip_file_names(zip_path):
                total += 1
        except BadZipFile as e:
            _update_job(job_id, status="error", message=f"El archivo ZIP está dañado o no es válido: {e}")
            return
        except Exception as e:
            _update_job(job_id, status="error", message=f"No se pudo leer el ZIP: {e}")
            return

        if total == 0:
            _update_job(job_id, status="error", message="El ZIP no contiene archivos.")
            return

        _update_job(job_id, total=total, processed=0, status="running", message="Procesando archivos…")

        # 2) Segunda pasada: procesa en streaming por lotes
        processed = 0
        current_batch = []
        sample_first = []

        for name in _iter_zip_file_names(zip_path):
            # Cancelación
            job = _get_job(job_id)
            if job and job.get("cancel_flag"):
                _update_job(job_id, status="cancelled", message="Trabajo cancelado por el usuario.")
                return

            # Muestra de los primeros para el resumen
            if len(sample_first) < 5:
                sample_first.append(name)

            # Aquí puedes abrir/parsear cada XML si lo requieres:
            # xml_bytes = _open_zip_member(zip_path, name)
            # TODO: parsear CFDI, extraer RFCs, acumular resultados, etc.

            current_batch.append(name)
            if len(current_batch) >= batch:
                # Simulación de carga/control de picos
                time.sleep(0.15)
                processed += len(current_batch)
                current_batch.clear()
                progress = min(1.0, processed / max(1, total))
                _update_job(
                    job_id,
                    processed=processed,
                    progress=progress,
                    message=f"Procesando… {processed}/{total}",
                )

        # Último lote pendiente
        if current_batch:
            time.sleep(0.15)
            processed += len(current_batch)
            progress = min(1.0, processed / max(1, total))
            _update_job(
                job_id,
                processed=processed,
                progress=progress,
                message=f"Procesando… {processed}/{total}",
            )

        # Resumen final
        last_summary = {
            "total_archivos": total,
            "tipo_zip": "XML (estimado por nombres)",
            "ejemplo_primeros": sample_first,
        }
        _update_job(job_id, status="done", progress=1.0, message="Completado.", summary=last_summary)

    except Exception as exc:
        _update_job(job_id, status="error", message=f"Error inesperado: {exc}")

    finally:
        # Limpieza del archivo subido
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass
        # Si no quieres conservar el JSON al terminar, descomenta:
        # _remove_job(job_id)


def start_zip_job(zip_path: Path, batch: int = DEFAULT_BATCH) -> str:
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

# Reenganche de estado si hubo reinicio
jid_mem = ss().get("zip_job_id")
if jid_mem and not ss().get("zip_indexing", False):
    _job = _get_job(jid_mem)
    if _job and _job.get("status") in {"queued", "running"}:
        ss()["zip_indexing"] = True
    elif _job and _job.get("status") == "done":
        ss()["zip_done"] = True
        ss()["zip_last_summary"] = _job.get("summary")
    elif _job and _job.get("status") in {"error", "cancelled"}:
        ss()["zip_error"] = _job.get("message")

st.title("EFOS / Lista Negra SAT — Carga masiva (ZIP)")
st.write(
    "Sube tu archivo **.zip** con XML y presiona **Procesar ZIP**. "
    "Se procesa en segundo plano para evitar timeouts (502). "
    "Los archivos y el estado se guardan fuera del proyecto (Volume o /tmp) para evitar reinicios por hot-reload."
)

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
        st.caption(
            f"Archivo listo: **{getattr(uploaded, 'name', 'archivo.zip')}** · "
            f"{_human_size(getattr(uploaded, 'size', 0) or 0)}"
        )
        if size_mb > MAX_MB:
            st.warning(
                f"El ZIP pesa {size_mb:.1f} MB (> {MAX_MB} MB). "
                "Divide el archivo para evitar límites de memoria del servicio."
            )

# Botones de acción
col_btn1, col_btn2, col_btn3 = st.columns([0.5, 0.25, 0.25])

def _store_uploaded_to_disk(up) -> Optional[Path]:
    if up is None:
        return None
    safe_name = Path(getattr(up, "name", "upload.zip") or "upload.zip").name
    dest = UPLOAD_DIR / f"{now_ms()}_{safe_name}"
    try:
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
    disabled = (uploaded is None) or (ss().get("zip_indexing", False))
    if st.button("Procesar ZIP", use_container_width=True, disabled=disabled):
        prev = ss().pop("zip_job_id", None)
        if prev:
            _cancel_job(prev)
        path = _store_uploaded_to_disk(uploaded)
        if path is not None:
            job_id = start_zip_job(path, batch=DEFAULT_BATCH)
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

# Estado / Progreso
jid = ss().get("zip_job_id")
if jid:
    job = _get_job(jid)
    if job is None:
        st.warning("No se encontró el estado del trabajo (posible reinicio del servidor).")
        colx1, colx2 = st.columns([0.4, 0.6])
        with colx1:
            if st.button("Reintentar adjuntar estado"):
                job = _get_job(jid)  # reintenta desde JSON
                if job and job.get("status") in {"queued", "running"}:
                    ss()["zip_indexing"] = True
                    st.rerun()
                elif job:
                    st.experimental_rerun()
        with colx2:
            if st.button("Descartar y empezar de nuevo"):
                reset_ui_state()
                st.rerun()
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
            time.sleep(POLL_INTERVAL)
            st.rerun()

        elif status == "done":
            ss()["zip_indexing"] = False
            ss()["zip_done"] = True
            ss()["zip_last_summary"] = job.get("summary")
            st.success("Procesamiento completado.")
            st.json(job.get("summary", {}))
            # Limpia JSON si no quieres conservarlo:
            # _remove_job(jid)

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
    st.info("Sube un ZIP y presiona **Procesar ZIP** para comenzar.")

# Resumen final persistido
if ss().get("zip_done") and ss().get("zip_last_summary"):
    st.markdown("---")
    st.subheader("Resumen de la última ejecución")
    st.json(ss()["zip_last_summary"])
