import re, unicodedata
import streamlit as st

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
