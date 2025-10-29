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
# helper para obtener base64 de primera imagen vÃ¡lida
# =========================
def image_src_for(candidates: tuple[Path, ...]) -> str | None:
    return first_image_base64(candidates)

# =========================
# imÃ¡genes asociadas a cada secciÃ³n
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

    /* --- TÃTULO GENERAL --- */
    .landing-welcome {
        font-family: system-ui,-apple-system,BlinkMacSystemFont,"Inter",Roboto,Arial,sans-serif !important;
        font-size: 1.4rem !important;
        font-weight: 700 !important;
        color: #0f172a !important;
        text-align: center !important;
        line-height: 1.1 !important;
        margin: 0 0 0.75rem 0 !important;
    }

    /* --- BLOQUE TEXTO DE CADA SECCIÃ“N --- */
    .landing-section {
        max-width: 600px !important;
    }

    .landing-section h2 {
        font-size: 1.2rem !important;
        font-weight: 700 !important;
        color: #0f172a !important;
        line-height: 1.15 !important;
        margin: 0 0 0.4rem 0 !important; /* menos espacio debajo del tÃ­tulo */
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

    /* --- IMAGEN DE LA SECCIÃ“N --- */
    .landing-illustration img {
        width: 100% !important;
        max-width: 360px !important;
        border-radius: 12px !important;
        box-shadow: 0 12px 24px rgba(15,23,42,0.14) !important;
        border: 1px solid rgba(0,0,0,0.04) !important;
        margin: 0 !important;
        display: block !important;
    }

    /* --- BOTÃ“N ROJO --- */
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
# helper para renderizar cada secciÃ³n en el layout 2 columnas
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

            # agrupar ideas en menos pÃ¡rrafos ayuda a bajar altura vertical
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

            # botÃ³n
            if reverse:
                # imagen izq, texto der â†’ botÃ³n alineado derecha
                _, btn_col_right = st.columns([3, 1])
                with btn_col_right:
                    if st.button("INICIAR", key=button_key):
                        st.switch_page(page_target)
            else:
                # texto izq â†’ botÃ³n alineado izq
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
                st.info("Falta imagen para esta secciÃ³n.")
            st.markdown('</div>', unsafe_allow_html=True)

# =========================
# CONTENIDO PRINCIPAL
# =========================
st.markdown('<div class="landing-wrapper">', unsafe_allow_html=True)

# tÃ­tulo arriba
st.markdown(
    '<div class="landing-welcome">Bienvenido a Araiza Intelligence</div>',
    unsafe_allow_html=True,
)

# -------- SECCIÓN: Cédula de Impuestos --------
render_section(
    title="Cédula de impuestos para cierre anual",
    paragraphs=[
        "Calcula coeficiente de utilidad, integra PTU y cruza deducciones con facilidad para preparar tus declaraciones anuales.",
        "Documenta decisiones clave con evidencia y formatos listos para revisión fiscal o auditoría.",
    ],
    bullet_title="Te permite:",
    bullets=[
        "Simular escenarios antes de enviar la declaración.",
        "Controlar obligaciones fiscales por entidad o razón social.",
        "Producir reportes ejecutivos para dirección y comités.",
    ],
    img_src=IMG_CEDULA,
    button_key="btn_cedula_impuestos",
    page_target="pages/XX_Cedula_impuestos.py",
    reverse=True,
)
st.markdown("<div class=\"section-spacer\"></div>", unsafe_allow_html=True)

# -------- SECCIÓN: Riesgo Fiscal --------
render_section(
    title="Riesgo fiscal sin sobresaltos",
    paragraphs=[
        "Cruza automáticamente tus CFDI contra la lista negra del SAT y conoce en qué momento uno de tus proveedores aparece en los listados 69, 69-B o 69-B Bis.",
        "Genera reportes de seguimiento para auditorías internas y demuestra acciones preventivas frente a autoridades fiscales.",
    ],
    bullet_title="Te ayuda a:",
    bullets=[
        "Detectar operaciones con EFOS publicados.",
        "Monitorear cambios cada vez que el SAT actualiza los listados.",
        "Alertar a finanzas y cumplimiento antes de que se genere una contingencia.",
    ],
    img_src=IMG_RIESGO,
    button_key="btn_riesgo_fiscal",
    page_target="pages/14_Riesgo_fiscal.py",
    reverse=False,
)
st.markdown("<div class=\"section-spacer\"></div>", unsafe_allow_html=True)

# -------- SECCIÓN: Monitoreo especializado de EFOS --------
render_section(
    title="Monitoreo especializado de EFOS",
    paragraphs=[
        "Identifica proveedores señalados como EFOS y documenta acciones de corrección con respaldo de evidencia oficial.",
        "Centraliza el historial de gestiones para auditores internos y externos sin depender de hojas de cálculo dispersas.",
    ],
    bullet_title="Beneficios clave:",
    bullets=[
        "Alertas automáticas cuando un RFC cambia de estatus.",
        "Historial de revisiones por periodo fiscal.",
        "Bitácora de seguimiento para áreas legales y fiscales.",
    ],
    img_src=IMG_EFOS,
    button_key="btn_efos",
    page_target="pages/14_Riesgo_fiscal.py",
    reverse=True,
)
st.markdown("<div class=\"section-spacer\"></div>", unsafe_allow_html=True)

# -------- SECCIÓN: Descarga masiva de XML --------
render_section(
    title="Descarga masiva de XML simplificada",
    paragraphs=[
        "Automatiza la descarga de CFDI directamente desde los servicios del SAT sin depender de tareas manuales y con trazabilidad completa.",
        "Mantén tus repositorios de facturas al día para conciliaciones contables, devoluciones y fiscalización.",
    ],
    bullet_title="Incluye:",
    bullets=[
        "Filtros por periodo, emisor y tipo de comprobante.",
        "Control de usuarios con permisos diferenciados.",
        "Integración con procesos de validación y timbrado.",
    ],
    img_src=IMG_XML,
    button_key="btn_descarga_xml",
    page_target="pages/14_Riesgo_fiscal.py",
    reverse=False,
)
st.markdown("<div class=\"section-spacer\"></div>", unsafe_allow_html=True)

# -------- SECCIÓN: Convertidor de Estados de Cuenta --------
render_section(
    title="Convertidor de estados de cuenta listo para conciliaciones",
    paragraphs=[
        "Normaliza los formatos bancarios y genera archivos estructurados para conciliación contable y análisis de flujos.",
        "Integra las transacciones con tu modelo de costos y reportes financieros en cuestión de minutos.",
    ],
    bullet_title="Funciones destacadas:",
    bullets=[
        "Lectura de estados en PDF o XLSX.",
        "Identificación de depósitos y retiros recurrentes.",
        "Exportación a plantillas de conciliación.",
    ],
    img_src=IMG_ESTADOS_CTA,
    button_key="btn_convertidor_estados",
    page_target="pages/XX_Convertidor_estados.py",
    reverse=True,
)
st.markdown("<div class=\"section-spacer\"></div>", unsafe_allow_html=True)

# -------- SECCIÓN: Traslado Inteligente --------
render_section(
    title="Traslado inteligente con costos completos",
    paragraphs=[
        "Calcula en segundos el costo real de cada ruta combinando kilometraje, peajes, combustible, viáticos y mantenimientos proyectados.",
        "Genera escenarios comparativos entre rutas y planifica márgenes antes de aceptar un servicio de flete.",
    ],
    bullet_title="Ideal para:",
    bullets=[
        "Cotizaciones urgentes con clientes clave.",
        "Simular rutas alternas y tiempos estimados.",
        "Controlar el margen operativo por cliente o zona.",
    ],
    img_src=IMG_TRASLADO,
    button_key="btn_traslado_inteligente",
    page_target="pages/1_Calculadora.py",
    reverse=False,
)
st.markdown("<div class=\"section-spacer\"></div>", unsafe_allow_html=True)

# -------- SECCIÓN: Generador de Pólizas --------
render_section(
    title="Generador automático de pólizas contables",
    paragraphs=[
        "Convierte CFDI en pólizas contables listas para integrar a tu ERP o sistema contable con las cuentas que definiste.",
        "Reduce capturas manuales y asegura trazabilidad desde la factura hasta la póliza registrada.",
    ],
    bullet_title="Automatiza:",
    bullets=[
        "Clasificación contable por tipo de gasto o ingreso.",
        "Control de impuestos y retenciones aplicables.",
        "Exportación en formatos compatibles con tu sistema.",
    ],
    img_src=IMG_POLIZAS,
    button_key="btn_generador_polizas",
    page_target="pages/XX_Generador_polizas.py",
    reverse=True,
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
