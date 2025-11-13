"""Sección informativa sobre Araiza Intelligence."""

from pathlib import Path
import base64
import streamlit as st

from core.theme import apply_theme
from core.auth import ensure_session_from_token
from core.navigation import render_nav

st.set_page_config(page_title="Acerca de Nosotros | Araiza Intelligence", layout="wide")
apply_theme()

ensure_session_from_token()
render_nav(active_top="acerca", active_child="acerca_resumen")

st.markdown(
    """
    <style>
      .about-wrapper {
        display: grid;
        gap: clamp(20px, 4vw, 36px);
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        margin-top: clamp(24px, 5vw, 40px);
      }
      .about-card {
        border-radius: 18px;
        padding: clamp(18px, 3vw, 28px);
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        box-shadow: 0 18px 32px rgba(15, 23, 42, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.25);
      }
      .about-card h3 {
        margin-top: 0;
        font-size: clamp(20px, 2.2vw, 26px);
      }
      .about-card p {
        color: #334155;
        font-size: clamp(15px, 1.55vw, 17px);
        line-height: 1.55;
      }
      .about-hero {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        align-items: center;
        gap: clamp(24px, 5vw, 40px);
        margin-top: clamp(16px, 4vw, 32px);
      }
      .about-hero h1 {
        font-size: clamp(30px, 3.6vw, 44px);
        margin-bottom: 16px;
      }
      .about-hero p {
        font-size: clamp(16px, 1.6vw, 19px);
        line-height: 1.6;
        color: #1f2937;
      }
      .about-hero img {
        width: 100%;
        border-radius: 18px;
        object-fit: cover;
        box-shadow: 0 22px 38px rgba(15, 23, 42, 0.18);
        max-height: 420px;
      }
      .about-contact {
        margin-top: clamp(24px, 4vw, 36px);
        border-radius: 14px;
        background: #f8fafc;
        border: 1px solid rgba(148, 163, 184, 0.25);
        box-shadow: 0 16px 28px rgba(15, 23, 42, 0.1);
        padding: clamp(18px, 3vw, 28px);
        color: #334155;
        font-size: clamp(15px, 1.5vw, 17px);
        line-height: 1.55;
      }
      .about-contact a {
        color: #1d4ed8;
        font-weight: 600;
        text-decoration: none;
      }
      .about-contact a:hover {
        text-decoration: underline;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="about-hero">', unsafe_allow_html=True)

st.markdown('<div>', unsafe_allow_html=True)
st.markdown('<h1>Somos Araiza Intelligence</h1>', unsafe_allow_html=True)
st.markdown(
    """
    <p>
      Nacimos dentro del Grupo Araiza para transformar la operación logística en
      información procesable. Construimos modelos que unen datos de transporte,
      finanzas y cumplimiento regulatorio para anticipar decisiones clave.
    </p>
    <p>
      Nuestros equipos multidisciplinarios diseñan herramientas que integran
      algoritmos, experiencia de campo y visualizaciones ejecutivas para impulsar
      a las áreas de logística, finanzas y dirección.
    </p>
    """,
    unsafe_allow_html=True,
)
st.markdown('</div>', unsafe_allow_html=True)

image_candidates = [
    Path("assets/about_cover.jpg"),
    Path("assets/about_cover.png"),
    Path(__file__).resolve().parent / "assets" / "about_cover.jpg",
    Path(__file__).resolve().parent / "assets" / "about_cover.png",
]
cover_data = None
for candidate in image_candidates:
    if candidate.exists():
        mime = "image/png" if candidate.suffix.lower() == ".png" else "image/jpeg"
        cover_data = f"data:{mime};base64," + base64.b64encode(candidate.read_bytes()).decode()
        break

if cover_data:
    st.markdown(f"<img src='{cover_data}' alt='Equipo Araiza Intelligence' />", unsafe_allow_html=True)
else:
    st.info("Agrega una imagen en assets/about_cover.jpg para complementar esta sección.")

st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="about-wrapper">', unsafe_allow_html=True)

st.markdown(
    """
    <div class="about-card">
      <h3>Visión</h3>
      <p>
        Convertir a Araiza Intelligence en el centro de inteligencia operativa
        del grupo, habilitando decisiones rápidas basadas en datos confiables y
        procesos automatizados.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="about-card">
      <h3>Capacidades</h3>
      <p>
        Especialistas en analítica de costos, automatización de reportes,
        integraciones con proveedores de datos (como Google Maps) y diseño de
        experiencias digitales para equipos internos.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="about-card">
      <h3>Alianzas</h3>
      <p>
        Colaboramos con áreas clave del grupo y aliados externos para mantener
        los modelos actualizados, garantizar el cumplimiento fiscal y asegurar
        la continuidad operativa de nuestras soluciones.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    """
    <p style="margin-top:32px; font-size:15px; color:#475569;">
      ¿Quieres saber más? Escríbenos a <strong>intelligence@grupoaraiza.mx</strong>.
    </p>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="about-contact">
      Teléfono: <strong>55 1234 5678</strong><br/>
      Ubicación: Av. Cuitláhuac 3139, Clavería, Azcapotzalco, 02840 Ciudad de México, CDMX<br/>
      Mapa: <a href="https://maps.app.goo.gl/txTQ6SF57XanDBBG7?g_st=aw" target="_blank" rel="noopener noreferrer">Ver en Google Maps</a>
      <br/><br/>
      Transformamos operación logística, contable y fiscal en información procesable.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")
