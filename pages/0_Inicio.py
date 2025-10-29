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

# =========================
# helper para obtener base64 de primera imagen válida
# =========================
def image_src_for(candidates: tuple[Path, ...]) -> str | None:
    return first_image_base64(candidates)

# =========================
# imágenes asociadas a cada sección
# =========================
IMG_RIESGO = image_src_for((
    Path("assets/riesgo_cover.png"),
    Path("assets/riesgo_cover.jpg"),
    Path(__file__).resolve().parent / "assets" / "riesgo_cover.png",
    Path(__file__).resolve().parent / "assets" / "riesgo_cover.jpg",
))

IMG_TRASLADO = image_src_for((
    Path("assets/traslado_inteligente_card.png"),
    Path("assets/inicio_card.png"),
    Path("assets/calculadora_cover.png"),
    Path("assets/calculadora_cover.jpg"),
    Path(__file__).resolve().parent / "assets" / "traslado_inteligente_card.png",
    Path(__file__).resolve().parent / "assets" / "inicio_card.png",
    Path(__file__).resolve().parent / "assets" / "calculadora_cover.png",
    Path(__file__).resolve().parent / "assets" / "caliculadora_cover.png",
))

IMG_EFOS = image_src_for((
    Path("assets/efos_card.png"),
    Path(__file__).resolve().parent / "assets" / "efos_card.png",
))

IMG_XML = image_src_for((
    Path("assets/descarga_masiva_xml_card.jpg"),
    Path(__file__).resolve().parent / "assets" / "descarga_masiva_xml_card.jpg",
))

IMG_POLIZAS = image_src_for((
    Path("assets/generador_poliza_card.png"),
    Path(__file__).resolve().parent / "assets" / "generador_poliza_card.png",
))

IMG_ESTADOS_CTA = image_src_for((
    Path("assets/convertidor_estados_cuenta.jpg"),
    Path(__file__).resolve().parent / "assets" / "convertidor_estados_cuenta.jpg",
))

IMG_CEDULA = image_src_for((
    Path("assets/cedula_impuestos_card.jpg"),
    Path(__file__).resolve().parent / "assets" / "cedula_impuestos_card.jpg",
))

# =========================
# NAVBAR
# =========================
render_nav(
    active_top="inicio",
    show_inicio=False,
    show_cta=False,
)

# =========================
# CSS COMPACTO
# =========================
st.markdown(
    """
    <style>
    /* --- NAV / LAYOUT --- */
    .nav-anchor {
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .nav-bar {
        margin-bottom: 0 !important;
    }
    .block-container {
        padding-top: 56px !important;
        padding-left: clamp(12px,2vw,20px) !important;
        padding-right: clamp(12px,2vw,20px) !important;
        padding-bottom: 40px !important;
        max-width: 1100px !important;
        margin: 0 auto !important;
    }

    .landing-wrapper {
        max-width: 1050px !important;
        margin: 0 auto !important;
    }

    /* --- TÍTULO GENERAL --- */
    .landing-welcome {
        font-family: system-ui,-apple-system,BlinkMacSystemFont,"Inter",Roboto,Arial,sans-serif !important;
        font-size: 1.4rem !important;
        font-weight: 700 !important;
        color: #0f172a !important;
        text-align: center !important;
        line-height: 1.1 !important;
        margin: 0 0 0.75rem 0 !important;
    }

    /* --- BLOQUE TEXTO DE CADA SECCIÓN --- */
    .landing-section {
        max-width: 600px !important;
    }

    .landing-section h2 {
        font-size: 1.2rem !important;
        font-weight: 700 !important;
        color: #0f172a !important;
        line-height: 1.15 !important;
        margin: 0 0 0.4rem 0 !important; /* menos espacio debajo del título */
    }

    .landing-section p {
        font-size: 0.88rem !important;
        line-height: 1.15rem !important;
        color: #475569 !important;
        margin: 0 0 0.4rem 0 !important;
        text-align: justify !important;
    }

    .landing-section .subheading {
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        color: #0f172a !important;
        line-height: 1.15rem !important;
        margin: 0.5rem 0 0.3rem 0 !important;
    }

    /* --- LISTAS --- */
    .landing-list {
        margin: 0 !important;
        padding-left: 0.7rem !important;
        list-style: none !important;
    }

    .landing-list li {
        position: relative !important;
        padding-left: 0.7rem !important;
        margin: 0 0 0.25rem 0 !important;
        font-size: 0.86rem !important;
        line-height: 1.15rem !important;
        color: #475569 !important;
        text-align: justify !important;
    }

    .landing-list li::before {
        content: "\\2022" !important;
        position: absolute !important;
        left: 0 !important;
        top: 0 !important;
        color: #dc2626 !important;
        font-weight: 700 !important;
        line-height: 1rem !important;
    }

    /* --- IMAGEN DE LA SECCIÓN --- */
    .landing-illustration img {
        width: 100% !important;
        max-width: 360px !important;
        border-radius: 12px !important;
        box-shadow: 0 12px 24px rgba(15,23,42,0.14) !important;
        border: 1px solid rgba(0,0,0,0.04) !important;
        margin: 0 !important;
        display: block !important;
    }

    /* --- BOTÓN ROJO --- */
    div.stButton > button {
        background-color: #dc2626 !important;
        color: #fff !important;
        border: 1px solid #dc2626 !important;
        border-radius: 9999px !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        line-height: 1rem !important;
        padding: 0.4rem 0.8rem !important;
        min-width: 140px !important;
        box-shadow: 0 6px 14px rgba(220,38,38,0.3) !important;
        transition: all .15s ease !important;
        margin-top: 0.4rem !important;
        margin-bottom: 0.4rem !important;
    }
    div.stButton > button:hover {
        background-color: #b91c1c !important;
        border: 1px solid #b91c1c !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 8px 16px rgba(185,28,28,0.4) !important;
    }

    /* --- ESPACIO ENTRE SECCIONES --- */
    .section-spacer {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }

    /* --- CONTACTO --- */
    .contact-wrapper {
        max-width: 1000px !important;
        margin: 0.75rem auto 1rem auto !important;
        border-radius: 12px !important;
        background-color: #f8fafc !important;
        border: 1px solid rgba(0,0,0,0.04) !important;
        box-shadow: 0 6px 16px rgba(15,23,42,0.06) !important;
        padding: 0.75rem 1rem !important;
    }

    .contact-text {
        font-size: 0.8rem !important;
        line-height: 1.1rem !important;
        color: #475569 !important;
        margin: 0.2rem 0 !important;
    }

    /* --- FOOTER --- */
    .landing-footer {
        text-align: center !important;
        color: #64748b !important;
        font-size: 0.7rem !important;
        padding: 0.75rem 0 1.5rem 0 !important;
        line-height: 1rem !important;
        margin: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# helper para renderizar cada sección en el layout 2 columnas
# =========================
def render_section(
    *,
    title: str,
    paragraphs: list[str],
    bullet_title: str | None,
    bullets: list[str],
    img_src: str | None,
    button_key: str,
    page_target: str,
    reverse: bool = False,
):
    """
    reverse = False  -> texto izquierda, imagen derecha
    reverse = True   -> imagen izquierda, texto derecha
    """
    with st.container():
        if reverse:
            image_col, text_col = st.columns([5, 7], gap="large")
        else:
            text_col, image_col = st.columns([7, 5], gap="large")

        # TEXTO
        with text_col:
            st.markdown('<div class="landing-section">', unsafe_allow_html=True)
            st.markdown(f"<h2>{title}</h2>", unsafe_allow_html=True)

            # agrupar ideas en menos párrafos ayuda a bajar altura vertical
            for p in paragraphs:
                st.markdown(f"<p>{p}</p>", unsafe_allow_html=True)

            if bullet_title:
                st.markdown(
                    f'<div class="subheading">{bullet_title}</div>',
                    unsafe_allow_html=True,
                )
            if bullets:
                st.markdown('<ul class="landing-list">', unsafe_allow_html=True)
                for item in bullets:
                    st.markdown(f"<li>{item}</li>", unsafe_allow_html=True)
                st.markdown("</ul>", unsafe_allow_html=True)

            # botón
            if reverse:
                # imagen izq, texto der → botón alineado derecha
                _, btn_col_right = st.columns([3, 1])
                with btn_col_right:
                    if st.button("INICIAR", key=button_key):
                        st.switch_page(page_target)
            else:
                # texto izq → botón alineado izq
                btn_col_left, _ = st.columns([1, 5])
                with btn_col_left:
                    if st.button("INICIAR", key=button_key):
                        st.switch_page(page_target)

            st.markdown("</div>", unsafe_allow_html=True)

        # IMAGEN
        with image_col:
            st.markdown('<div class="landing-illustration">', unsafe_allow_html=True)
            if img_src:
                st.markdown(
                    f'<img src="{img_src}" alt="{title}" />',
                    unsafe_allow_html=True,
                )
            else:
                st.info("Falta imagen para esta sección.")
            st.markdown('</div>', unsafe_allow_html=True)

# =========================
# CONTENIDO PRINCIPAL
# =========================
st.markdown('<div class="landing-wrapper">', unsafe_allow_html=True)

# título arriba
st.markdown(
    '<div class="landing-welcome">Bienvenido a Araiza Intelligence</div>',
    unsafe_allow_html=True,
)

# -------- SECCIÓN: Riesgo Fiscal --------
render_section(
    title="Riesgo fiscal, sin sobresaltos",
    paragraphs=[
        "La lista negra del SAT es un registro público que incluye a los contribuyentes (personas físicas y morales) que han cometido irregularidades fiscales, como emitir comprobantes fiscales falsos o tener adeudos fiscales. Nuestro sistema analiza de forma masiva los CFDI de tus proveedores, identifica automáticamente los RFC y los cruza contra esa lista oficial para ayudarte a detectar posibles riesgos fiscales antes de que se conviertan en un problema.",
    ],
    bullet_title=None,
    bullets=[],
    img_src=IMG_RIESGO,
    button_key="btn_riesgo_fiscal",
    page_target="pages/14_Riesgo_fiscal.py",
    reverse=False,  # texto izq, imagen der
)

st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

# -------- SECCIÓN: Traslado Inteligente / Costos de Ruta --------
render_section(
    title="Precisión en movimiento",
    paragraphs=[
        "Nuestra plataforma calcula con exactitud los costos reales de cada flete, integrando tecnología avanzada, APIs de Google Maps y bases de datos inteligentes para ofrecer resultados precisos y actualizados en tiempo real. Obtén en segundos el costo total de una ruta — peajes, combustible, mantenimiento y demás gastos operativos — con una interfaz ágil, intuitiva y confiable. Además, administra fácilmente usuarios y trabajadores, garantizando control, trazabilidad y eficiencia en cada viaje.",
    ],
    bullet_title="Características principales:",
    bullets=[
        "Cálculo automático de rutas, distancias y casetas.",
        "Estimación real de combustible y costos operativos.",
        "Gestión integrada de usuarios y trabajadores.",
        "Reportes claros y listos para la toma de decisiones.",
        "Transparencia y precisión en cada operación.",
    ],
    img_src=IMG_TRASLADO,
    button_key="btn_traslado",
    page_target="pages/1_Calculadora.py",
    reverse=True,  # imagen izq, texto der
)

st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

# -------- SECCIÓN: EFOS --------
render_section(
    title="Verificación EFOS",
    paragraphs=[
        "¿Sabes si la empresa con la que trabajas aparece como EFOS ante el SAT? Evita multas, pérdida de deducciones y riesgos legales. Te ayudamos a verificar si un proveedor está listado como emisor de comprobantes fiscales simulados antes de operar con él.",
    ],
    bullet_title="Riesgos que evitamos:",
    bullets=[
        "Multas y recargos.",
        "Pérdida de deducciones fiscales.",
        "Auditorías y revisiones fiscales.",
        "Responsabilidades legales en casos graves.",
    ],
    img_src=IMG_EFOS,
    button_key="btn_efos",
    page_target="pages/14_Riesgo_fiscal.py",  # ajusta si tienes otra vista EFOS específica
    reverse=False,
)

st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

# -------- SECCIÓN: Descarga masiva de XML --------
render_section(
    title="Descarga masiva de XML",
    paragraphs=[
        "Centraliza y valida CFDI de manera automática. Descarga tus facturas en bloque, asegura su autenticidad y mantén un control documental listo para auditoría. Automatiza conciliaciones y acelera el análisis financiero con información confiable.",
    ],
    bullet_title="Beneficios clave:",
    bullets=[
        "Asegura la veracidad y autenticidad de los comprobantes.",
        "Optimiza la gestión documental y el cumplimiento fiscal.",
        "Permite conciliación y análisis financiero automatizado.",
    ],
    img_src=IMG_XML,
    button_key="btn_xml",
    page_target="pages/14_Riesgo_fiscal.py",  # o módulo específico de XML si lo tienes
    reverse=True,
)

st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

# -------- SECCIÓN: Generador de Pólizas --------
render_section(
    title="Generador de Pólizas",
    paragraphs=[
        "Automatiza el registro contable de ingresos, egresos y provisiones. Convierte archivos Excel (.xlsx) en pólizas listas para subir de forma masiva a sistemas como COI. Menos captura manual. Más consistencia. Más velocidad en cierres contables.",
    ],
    bullet_title="Lo que automatizamos:",
    bullets=[
        "Ingresos y egresos.",
        "Provisiones.",
        "Carga masiva a sistemas contables.",
    ],
    img_src=IMG_POLIZAS,
    button_key="btn_polizas",
    page_target="pages/XX_Generador_polizas.py",
    reverse=False,
)

st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

# -------- SECCIÓN: Convertidor de Estados de Cuenta --------
render_section(
    title="Convertidor de Estados de Cuenta",
    paragraphs=[
        "Convierte tus estados de cuenta bancarios en información clara y analizable. Automatizamos la lectura y descarga de movimientos bancarios, organizando cargos, abonos, fechas y saldos directamente en Excel en segundos.",
    ],
    bullet_title="Beneficios:",
    bullets=[
        "Ahorra tiempo en registros.",
        "Control inmediato del flujo de efectivo.",
        "Datos precisos listos para análisis financiero.",
    ],
    img_src=IMG_ESTADOS_CTA,
    button_key="btn_estados_cuenta",
    page_target="pages/XX_Convertidor_estados.py",
    reverse=True,
)

st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

# -------- SECCIÓN: Cédula de Impuestos --------
render_section(
    title="Cédula de Impuestos",
    paragraphs=[
        "Papel de trabajo diseñado para Personas Morales en Régimen General. Facilita el cálculo y la conciliación de ingresos, deducciones, coeficiente de utilidad, PTU y otros rubros clave de la declaración anual. Minimiza errores y acelera el cumplimiento fiscal con formatos estructurados en Excel.",
    ],
    bullet_title="Te ayuda a:",
    bullets=[
        "Calcular coeficiente de utilidad.",
        "Integrar PTU.",
        "Conciliar ingresos y deducciones.",
        "Cumplir obligaciones fiscales con orden.",
    ],
    img_src=IMG_CEDULA,
    button_key="btn_cedula",
    page_target="pages/XX_Cedula_impuestos.py",
    reverse=False,
)

st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

# =========================
# CONTACTO / UBICACIÓN (sin el título "Contáctanos")
# =========================
st.markdown(
    """
    <div class="contact-wrapper">
      <div class="contact-text">
        Teléfono: <strong>55 1234 5678</strong><br/>
        Ubicación: Av. Cuitláhuac 3139, Claveria, Azcapotzalco, 02840 Ciudad de México, CDMX<br/>
        Mapa: <a href="https://maps.app.goo.gl/txTQ6SF57XanDBBG7?g_st=aw" target="_blank">Ver en Google Maps</a>
      </div>
      <div class="contact-text">
        Transformamos operación logística, contable y fiscal en información procesable.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================
# FOOTER
# =========================
st.markdown("---")
st.markdown(
    '<div class="landing-footer">&copy; 2025 Araiza Intelligence. Todos los derechos reservados.</div>',
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)  # /landing-wrapper
