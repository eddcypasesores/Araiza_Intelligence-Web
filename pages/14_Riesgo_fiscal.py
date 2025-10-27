"""Página de bienvenida al módulo de Riesgo Fiscal."""

from pathlib import Path
import base64
import streamlit as st

from core.auth import ensure_session_from_token
from core.navigation import render_nav

st.set_page_config(page_title="Riesgo Fiscal | Araiza Intelligence", layout="wide")

ensure_session_from_token()
render_nav(active_top="riesgo", active_child=None)

ASSET_CANDIDATES = [
    Path("assets/riesgo_cover.jpg"),
    Path("assets/riesgo_cover.png"),
    Path(__file__).resolve().parent / "assets" / "riesgo_cover.jpg",
    Path(__file__).resolve().parent / "assets" / "riesgo_cover.png",
]


def _load_cover() -> str | None:
    for candidate in ASSET_CANDIDATES:
        if candidate.exists():
            data = candidate.read_bytes()
            mime = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
            return f"data:{mime};base64," + base64.b64encode(data).decode()
    return None


cover_src = _load_cover()

st.markdown(
    """
    <style>
      .riesgo-hero {
        display: flex;
        flex-wrap: wrap;
        gap: clamp(24px, 5vw, 40px);
        align-items: center;
        margin-top: clamp(20px, 4vw, 32px);
      }
      .riesgo-hero > div {
        flex: 1 1 320px;
        min-width: 0;
      }
      .riesgo-copy h1 {
        font-size: clamp(28px, 3.4vw, 40px);
        margin-bottom: 12px;
      }
      .riesgo-copy p {
        font-size: clamp(16px, 1.6vw, 18px);
        line-height: 1.55;
        color: #334155;
        margin-bottom: 0.8rem;
      }
      .riesgo-copy .tagline {
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #0f172a;
      }
      .riesgo-cover img {
        width: 100%;
        border-radius: 18px;
        box-shadow: 0 20px 36px rgba(15, 23, 42, 0.18);
        object-fit: cover;
        max-height: 420px;
      }
      .riesgo-actions {
        margin-top: clamp(16px, 3vw, 28px);
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
      }
      .riesgo-actions button[kind="primary"] {
        min-width: 220px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="riesgo-hero">', unsafe_allow_html=True)

st.markdown('<div class="riesgo-copy">', unsafe_allow_html=True)
st.markdown('<div class="tagline">Riesgo Fiscal SAT</div>', unsafe_allow_html=True)
st.markdown('<h1>Monitorea emisores y asegura el cumplimiento</h1>', unsafe_allow_html=True)
st.markdown(
    """
    <p>
      Centraliza en un solo lugar la verificación de contribuyentes dentro de la
      lista negra del SAT. Sube tus CFDI, cruza los RFC con la base de incumplidos
      y descarga reportes listos para auditar.
    </p>
    <p>
      Identifica riesgos antes de comprometer operaciones y mantén informada a la
      dirección con evidencia formal de cada consulta.
    </p>
    """,
    unsafe_allow_html=True,
)

if st.session_state.get("usuario") and st.session_state.get("rol"):
    st.info(
        "Estás autenticado como ``{}``. Puedes acceder directamente al módulo de consulta.".format(
            st.session_state["usuario"]
        )
    )

st.markdown('<div class="riesgo-actions">', unsafe_allow_html=True)
if st.button("Consultar lista negra", type="primary", key="btn_consultar_riesgo"):
    st.switch_page("pages/15_Lista_negra_SAT.py")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="riesgo-cover">', unsafe_allow_html=True)
if cover_src:
    st.markdown(f"<img src='{cover_src}' alt='Riesgo fiscal' />", unsafe_allow_html=True)
else:
    st.info("Agrega una imagen en assets/riesgo_cover.jpg para ilustrar el módulo.")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
