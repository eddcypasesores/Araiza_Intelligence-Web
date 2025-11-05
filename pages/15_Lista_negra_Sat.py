# pages/15_Lista_negra_Sat.py
from __future__ import annotations

import json
import threading
import time
import zipfile
from zipfile import BadZipFile
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

# Rutas locales de trabajo
BASE_DIR = Path.cwd()
DATA_DIR = BASE_DIR / ".data_lista_negra_sat"
UPLOAD_DIR = DATA_DIR / "uploads"
JOBS_DIR = DATA_DIR / "jobs"
for d in (DATA_DIR, UPLOAD_DIR, JOBS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Parámetros
MAX_MB = 250  # límite recomendado (ajústalo a tu hosting)
DEFAULT_BATCH = 300  # tamaño de lote para procesamiento

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
# Persistencia de JOBS a disco (reanudar tras reinicio)
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
    # 1) intenta memoria
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if job is not None:
        return job
    # 2) intenta disco
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
# Worker (hilo en segundo plano)
# -----------------------------------------------------------------------------
def process_zip_job(job_id: str, zip_path: Path, batch: int = DEFAULT_BATCH):
    """
    Procesa el ZIP (en segundo plano).
    Aquí integra tu parseo real de XML + lógicas EFOS/Lista Negra + exportaciones.
    """
    try:
        _update_job(job_id, status="running", progress=0.0, message="Abriendo ZIP…")

        try:
            with zip_path.open("rb") as f:
                try:
                    with zipfile.ZipFile(f) as zf:
                        all_names = [n for n in zf.namelist() if not n.endswith("/")]
                except BadZipFile as e:
                    _update_job(job_id, status="error", message=f"El archivo ZIP está dañado o no es válido: {e}")
                    return
        except Exception as e:
            _update_job(job_id, status="error", message=f"No se pudo leer el ZIP: {e}")
            return

        total = len(all_names)
        if total == 0:
            _update_job(job_id, status="error", message="El ZIP no contiene archivos.")
            return

        _update_job(job_id, total=total, processed=0, status="running", message="Procesando archivos…")

        processed = 0
        # Bucle por lotes (ajusta batch según hosting)
        # NOTA: si necesitas abrir cada XML, vuelve a abrir el ZIP dentro del bucle para leer archivos.
        # Esto evita mantener archivos abiertos si el ZIP es grande.
        for i in range(0, total, batch):
            job = _get_job(job_id)
            if job and job.get("cancel_flag"):
                _update_job(job_id, status="cancelled", message="Trabajo cancelado por el usuario.")
                return

            chunk = all_names[i : i + batch]

            # >>> Aquí: abre el ZIP y procesa cada XML del chunk <<<
            # with zip_path.open("rb") as f:
            #     with zipfile.ZipFile(f) as zf:
            #         for name in chunk:
            #             with zf.open(name) as fh:
            #                 xml_bytes = fh.read()
            #                 # TODO: parsear CFDI, extraer RFCs, etc.

            # Simulación de carga para evitar picos de CPU en hosting básico
            time.sleep(0.15)

            processed += len(chunk)
            progress = min(1.0, processed / max(1, total))
            _update_job(
                job_id,
                processed=processed,
                progress=progress,
                message=f"Procesando… {processed}/{total}",
            )

        # Resultado/resumen final
        last_summary = {
            "total_archivos": total,
            "tipo_zip": "XML (estimado por nombres)",
            "ejemplo_primeros": all_names[:5],
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
        # Si prefieres limpiar el JSON del job al terminar, descomenta:
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

# Reenganche de estado si hubo reinicio del servidor
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
    "El procesamiento se hace en segundo plano para evitar timeouts del proxy (502). "
    "Si el servidor se reinicia, el estado del proceso se reanuda automáticamente."
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
                "Divide el archivo para evitar errores por límites del hosting."
            )

# Botones de acción
col_btn1, col_btn2, col_btn3 = st.columns([0.5, 0.25, 0.25])

def _store_uploaded_to_disk(up) -> Optional[Path]:
    if up is None:
        return None
    safe_name = Path(getattr(up, "name", "upload.zip") or "upload.zip").name
    dest = UPLOAD_DIR / f"{now_ms()}_{safe_name}"
    try:
        # intentar posicionar al inicio
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
        # Cancela un trabajo previo (si hubiera)
        prev = ss().pop("zip_job_id", None)
        if prev:
            _cancel_job(prev)
        # Guarda a disco
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
            # Polling suave
            time.sleep(0.7)
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
