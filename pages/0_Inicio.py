"""Portada principal de Araiza Intelligence con modulos destacados."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.auth import ensure_session_from_token
from core.navigation import render_nav
from pages.components.hero import first_image_base64, inject_hero_css

st.set_page_config(
    page_title="Inicio - Araiza Intelligence",
    page_icon="AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ensure_session_from_token()
inject_hero_css()

st.markdown(
    """
    <style>
      .landing-wrapper {
        display: flex;
        flex-direction: column;
        gap: clamp(32px, 6vw, 56px);
        margin-top: clamp(24px, 6vw, 72px);
      }

      .landing-hero {
        font-size: clamp(30px, 4vw, 44px);
        font-weight: 800;
        color: #0f172a;
        margin-bottom: clamp(12px, 2vw, 18px);
        text-align: center;
      }

      .landing-intro {
        text-align: center;
        max-width: 720px;
        margin: 0 auto clamp(24px, 6vw, 40px);
        color: #475569;
        font-size: clamp(15px, 1.6vw, 18px);
      }

      .landing-section h2 {
        font-size: clamp(26px, 3vw, 34px);
        font-weight: 800;
        color: #111827;
        margin-bottom: clamp(12px, 2vw, 16px);
      }

      .landing-section p {
        color: #475569;
        font-size: clamp(14px, 1.4vw, 17px);
        line-height: 1.55;
        margin-bottom: clamp(12px, 2vw, 16px);
      }

      .landing-list {
        list-style: none;
        padding-left: 0;
        margin: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
        color: #1f2937;
        font-size: clamp(14px, 1.4vw, 16px);
      }

      .landing-list li::before {
        content: "\\2022";
        margin-right: 10px;
        color: #dc2626;
        font-weight: 700;
      }

      .landing-section img {
        width: 100%;
        aspect-ratio: 4 / 3;
        border-radius: 20px;
        box-shadow: 0 22px 40px rgba(15, 23, 42, 0.16);
        object-fit: cover;
      }

      .landing-section .stButton button {
        background-color: #2563eb;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 12px 26px;
        font-size: clamp(15px, 1.6vw, 17px);
        font-weight: 700;
        box-shadow: 0 12px 20px rgba(37, 99, 235, 0.25);
        transition: transform 0.15s ease, box-shadow 0.15s ease,
                    background-color 0.15s ease;
      }

      .landing-section .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 16px 26px rgba(37, 99, 235, 0.35);
        background-color: #1d4ed8;
      }

      .landing-footer {
        text-align: center;
        padding: clamp(18px, 5vw, 32px);
        color: #64748b;
        font-size: 0.9rem;
      }

      @media (max-width: 900px) {
        .landing-section .stColumn {
          margin-bottom: 18px;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

render_nav(active_top="inicio", show_inicio=False, show_cta=False)

RISK_IMAGE_CANDIDATES = (
    Path("assets/riesgo_cover.png"),
    Path("assets/riesgo_cover.jpg"),
    Path(__file__).resolve().parent / "assets" / "riesgo_cover.png",
    Path(__file__).resolve().parent / "assets" / "riesgo_cover.jpg",
)

CALC_IMAGE_CANDIDATES = (
    Path("assets/inicio_card.png"),
    Path(__file__).resolve().parent / "assets" / "inicio_card.png",
    Path("assets/calculadora_cover.png"),
    Path("assets/calculadora_cover.jpg"),
    Path(__file__).resolve().parent / "assets" / "calculadora_cover.png",
    Path(__file__).resolve().parent / "assets" / "calculadora_cover.jpg",
)

risk_image_src = first_image_base64(RISK_IMAGE_CANDIDATES)
calc_image_src = first_image_base64(CALC_IMAGE_CANDIDATES)

st.markdown('<h1 class="landing-hero">Bienvenido a Araiza Intelligence</h1>', unsafe_allow_html=True)

st.markdown('<div class="landing-wrapper">', unsafe_allow_html=True)

with st.container():
    text_col, image_col = st.columns([7, 5], gap="large")
    with text_col:
        st.markdown(
            """
            <div class="landing-section">
              <h2>Riesgo fiscal, sin sobresaltos</h2>
              <p>
                Analiza lotes completos de CFDI, identifica emisores criticos y genera reportes
                ejecutivos en segundos gracias a nuestra integracion con la lista negra del SAT.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <ul class="landing-list">
              <li>Carga masiva de XML con deteccion automatica de RFC.</li>
              <li>Cruce inmediato contra Firmes.csv y reportes descargables.</li>
              <li>Panel navegable para revisar coincidencias con detalle.</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Consultar Lista", key="home_riesgo_btn"):
            st.switch_page("pages/14_Riesgo_fiscal.py")
    with image_col:
        if risk_image_src:
            st.markdown(
                f'<img src="{risk_image_src}" alt="Modulo de Riesgo Fiscal" />',
                unsafe_allow_html=True,
            )
        else:
            st.info("Agrega la imagen 'assets/riesgo_cover.png' para ilustrar este modulo.")

with st.container():
    image_col, text_col = st.columns([5, 7], gap="large")
    with image_col:
        if calc_image_src:
            st.markdown(
                f'<img src="{calc_image_src}" alt="Modulo de traslados" />',
                unsafe_allow_html=True,
            )
        else:
            st.info("Agrega la imagen 'assets/calculadora_cover.png' para ilustrar este modulo.")
    with text_col:
        st.markdown(
            """
            <div class="landing-section">
              <h2>Traslados calculados con precision</h2>
              <p>
                Genera presupuestos confiables contemplando rutas, casetas, viaticos y operadores,
                todo en una sola pantalla y con datos actualizados.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <ul class="landing-list">
              <li>Optimizacion de rutas con Google Maps y catalogo interno.</li>
              <li>Tarifas centralizadas para garantizar consistencia.</li>
              <li>Control de operadores, paradas intermedias y viaticos.</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Calcular Traslados", key="home_calculadora_btn"):
            st.switch_page("pages/1_Calculadora.py")

st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.markdown(
    '<div class="landing-footer">&copy; 2023 Araiza Intelligence. Todos los derechos reservados.</div>',
    unsafe_allow_html=True,
)
