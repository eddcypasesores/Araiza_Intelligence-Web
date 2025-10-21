# core/utils.py
from pathlib import Path
import re
import unicodedata
import streamlit as st

# -------------------------------
# CSS loader robusto
# -------------------------------
def _candidate_dirs_for_assets() -> list[Path]:
    """
    Carpetas candidatas donde podría estar assets/styles.css
    sin depender del cwd. Cubre estructuras típicas de apps Streamlit.
    """
    here = Path(__file__).resolve()     # .../core/utils.py
    root = here.parents[1]              # raíz del proyecto
    cwd  = Path.cwd().resolve()         # directorio de ejecución

    return [
        root / "assets",
        root / "pages" / "assets",
        root / "static",
        cwd / "assets",
        cwd / "pages" / "assets",
        cwd / "static",
    ]

def inject_css(file_name: str = "styles.css") -> bool:
    """
    Inyecta un archivo CSS dentro de <style>...</style>.
    Busca en varias ubicaciones típicas. Retorna True si lo cargó.
    Deja un comentario HTML con la ruta cargada para depuración.
    """
    for d in _candidate_dirs_for_assets():
        css_path = d / file_name
        try:
            if css_path.exists():
                css = css_path.read_text(encoding="utf-8")
                st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
                st.markdown(f"<!-- CSS loaded from: {css_path} -->", unsafe_allow_html=True)
                return True
        except Exception as e:
            st.warning(f"No se pudo leer CSS en {css_path}: {e}")
            return False

    tested = ", ".join(str(p) for p in _candidate_dirs_for_assets())
    st.warning(f"No se encontró el archivo de estilos: {file_name} en {tested}")
    return False

# -------------------------------
# Helpers existentes
# -------------------------------
def _cols_trabajadores(conn):
    return {r[1] for r in conn.execute("PRAGMA table_info(trabajadores)").fetchall()}

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))

def normalize_name(s: str) -> str:
    s = strip_accents(s).upper()
    s = s.replace(".", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("NUEVO ", "NVO ").replace("KM 26", "KM26").replace("KM-26", "KM26")
    s = s.replace(" ORIENTE ", " OTE ").replace(" LIBRE ", " LIB ").replace(" LIBR ", " LIB ")
    return s

def is_excluded(idx: int) -> bool:
    return "excluded_set" in st.session_state and idx in st.session_state["excluded_set"]

def set_excluded(idx: int, value: bool):
    st.session_state.setdefault("excluded_set", set())
    if value:
        st.session_state["excluded_set"].add(idx)
    else:
        st.session_state["excluded_set"].discard(idx)
