# pages/0_Inicio.py - Tarjetas alternadas (zigzag) 100% clickeables con verificacion de paginas (imagenes 16:9)
from __future__ import annotations
from pathlib import Path
from urllib.parse import urlencode
import html

import streamlit as st

# --- dependencias del proyecto (ajusta si tu mdulo se llama distinto) ---
from core.auth import ensure_session_from_token
from core.navigation import PAGE_PARAM_NAMES, render_nav
from pages.components.hero import first_image_base64, inject_hero_css

# -------------------------------------------------------------------------
# Configuracin de p!gina
# -------------------------------------------------------------------------
st.set_page_config(
    page_title="Inicio - Araiza Intelligence",
    page_icon="AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Sesin / estilos base ---
ensure_session_from_token()
inject_hero_css()

ROOT = Path(__file__).resolve().parent.parent     # carpeta raz del proyecto (donde est! app.py)
PAGES_DIR = ROOT / "pages"

# -------------------------------------------------------------------------
# Helpers de im!genes y p!ginas
# -------------------------------------------------------------------------
def image_src_for(candidates: tuple[Path, ...]) -> str | None:
    """Devuelve una data URI base64 v!lida para <img src="..."> o None."""
    return first_image_base64(candidates)

def page_exists(rel_page: str) -> bool:
    """
    Verifica que el archivo exista respecto a la raz del proyecto.
    Acepta valores como 'app.py' o 'pages/1_Calculadora.py'.
    """
    p = (ROOT / rel_page).resolve()
    try:
        # Evita salirte del proyecto con rutas extraas
        p.relative_to(ROOT)
    except Exception:
        return False
    return p.is_file()

def _product_href(script_path: str, *, force_logout: bool = False, label_override: str | None = None) -> str:
    """Construye un href absoluto para el multipage actual."""
    label = label_override or PAGE_PARAM_NAMES.get(script_path)
    if label is None:
        label = script_path.replace("pages/", "").replace(".py", "").strip()
    params: dict[str, str] = {"page": label or script_path}
    if force_logout:
        params["logout"] = "1"
    return "/?" + urlencode(params)

# -------------------------------------------------------------------------
# Formateo seguro de descripciones largas (texto proveniente de Word)
# -------------------------------------------------------------------------
def as_html_desc(text: str) -> str:
    """
    Convierte texto 'plano' de Word a HTML simple:
    - Respeta p!rrafos (doble salto = <br><br>, salto simple = espacio)
    - Detecta vietas que empiezan con ' ' y arma un <ul><li>...</li></ul>
    - Escapa cualquier '<' '>' que viniera del clipboard
    """
    if not text:
        return ""
    # Normaliza saltos
    t = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    lines = [ln.strip() for ln in t.split("\n")]
    bullet_lines = [ln[2:].strip() for ln in lines if ln.startswith(" ")]
    non_bullet = [ln for ln in lines if not ln.startswith(" ") and ln != ""]

    parts = []
    if non_bullet:
        # Une lneas en p!rrafos simples
        para = html.escape("\n".join(non_bullet)).replace("\n\n", "<br><br>").replace("\n", " ")
        parts.append(f'<p class="card-desc">{para}</p>')
    if bullet_lines:
        lis = "".join(f"<li>{html.escape(x)}</li>" for x in bullet_lines)
        parts.append(f'<ul class="card-list">{lis}</ul>')
    return "".join(parts)

# -------------------------------------------------------------------------
# Im!genes (candidatos en /assets; ajusta nombres si usas otros)
# -------------------------------------------------------------------------
IMG_RIESGO = image_src_for((
    Path("assets/riesgo_cover.png"),
    Path(__file__).resolve().parent / "assets" / "riesgo_cover.png",
))
IMG_TRASLADO = image_src_for((
    Path("assets/traslado_inteligente_card.png"),
    Path(__file__).resolve().parent / "assets" / "traslado_inteligente_card.png",
))
IMG_DIOT = image_src_for((
    Path("assets/diot_card.png"),
    Path(__file__).resolve().parent / "assets" / "diot_card.png",
))
IMG_EFOS = image_src_for((
    Path("assets/efos_card.png"),
    Path(__file__).resolve().parent / "assets" / "efos_card.png",
))
IMG_XML = image_src_for((
    Path("assets/descarga_masiva_xml_card.png"),
    Path(__file__).resolve().parent / "assets" / "descarga_masiva_xml_card.png",
))
IMG_POLIZAS = image_src_for((
    Path("assets/generador_poliza_card.png"),
    Path(__file__).resolve().parent / "assets" / "generador_poliza_card.png",
))
IMG_ESTADOS_CTA = image_src_for((
    Path("assets/convertidor_estados_cuenta.png"),
    Path(__file__).resolve().parent / "assets" / "convertidor_estados_cuenta.png",
))
IMG_CEDULA = image_src_for((
    Path("assets/cedula_impuestos_card.png"),
    Path(__file__).resolve().parent / "assets" / "cedula_impuestos_card.png",
))

# -------------------------------------------------------------------------
# Navbar
# -------------------------------------------------------------------------
render_nav(active_top="inicio", show_inicio=False, show_cta=False)

# -------------------------------------------------------------------------
# CSS (misma estructura; + aire entre tarjetas; media 16:9)
# -------------------------------------------------------------------------
st.markdown("""
<style>
.block-container{
  padding-top:56px !important;
  padding-left:clamp(12px,2vw,20px) !important;
  padding-right:clamp(12px,2vw,20px) !important;
  max-width: 1200px !important; margin:0 auto !important;
}

/* Ttulo GRANDE */
.landing-title{
  font-weight:900; 
  font-size: clamp(32px, 3.6vw, 44px); 
  line-height:1.1; 
  text-align:center; 
  color:#0f172a; 
  margin: 0 0 18px;
}

/* GRID: m!s aire entre tarjetas */
.cards-grid{
  display:grid;
  grid-template-columns: repeat(2, minmax(0,1fr));
  gap: clamp(28px, 4vw, 40px);
}
@media (max-width:1000px){
  .cards-grid{ grid-template-columns: 1fr; gap: 22px; }
}

/* TARJETA ALTERNADA */
.card-split{
  position:relative;
  display:flex; height:100%;
  border:1px solid rgba(0,0,0,.06); border-radius:14px; background:#fff;
  box-shadow:0 8px 24px rgba(2,6,23,.06); overflow:hidden;
  transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease;
  cursor:pointer;
  isolation:isolate;
  margin: 6px 0 12px; /* aire vertical adicional */
}
.card-split:hover{ transform: translateY(-2px); box-shadow:0 14px 32px rgba(2,6,23,.1); border-color:rgba(0,0,0,.08); }

/* Hover: tinte y flecha */
.card-split::after{
  content:"";
  position:absolute; inset:0;
  background: rgba(15, 23, 42, 0);
  transition: background .12s ease;
  z-index:1;
}
.card-split:hover::after{ background: rgba(15, 23, 42, .04); }

.card-split::before{
  content:"";
  position:absolute; right:12px; top:12px;
  width:0; height:0; border-left:10px solid #0f172a; border-top:6px solid transparent; border-bottom:6px solid transparent;
  opacity:0; transform: translateX(-4px);
  transition: opacity .12s ease, transform .12s ease;
  z-index:2;
}
.card-split:hover::before{ opacity:0.7; transform: translateX(0); }

/* alternancia izquierda/derecha */
.card-split.rev{ flex-direction: row-reverse; }

/* MEDIA 16:9 */
.card-media{
  flex:0 0 42%;
  background:#f1f5f9;
  display:flex; align-items:center; justify-content:center;
  overflow:hidden; border-radius:14px;
  aspect-ratio: 16 / 9;      /* fuerza contenedor 16:9 */
  padding:12px;
}
.card-media img{
  width:100%;
  height:100%;
  object-fit: contain;          /* muestra la imagen completa */
}

/* Texto de la tarjeta */
.card-copy{ flex:1; display:flex; flex-direction:column; padding:16px; position:relative; z-index:3; }
.card-title{ margin:0 0 6px; font-weight:800; color:#0f172a; font-size:1.25rem; line-height:1.2; }
.card-desc{ margin:0 0 10px; color:#475569; font-size:.95rem; line-height:1.55rem; text-align:justify; }
.card-list{ margin:0; padding-left: 1.05rem; color:#475569; font-size:.92rem; line-height:1.25rem; }
.card-list li{ margin: 0 0 .28rem; }
.card-list li::marker{ color:#dc2626; }

/* Enlace invisible que cubre toda la tarjeta (st.page_link) */
.overlay-link{
  position:absolute; inset:0; z-index:6;
  margin:0 !important; padding:0 !important;
}
.overlay-link > div{               /* wrapper que genera Streamlit */
  position:absolute !important; inset:0 !important;
  margin:0 !important; padding:0 !important;
}
.overlay-link a{                   /* el <a> real de st.page_link */
  position:absolute; inset:0;
  display:block; width:100%; height:100%;
  opacity:0; text-indent:-9999px;
  overflow:hidden; border:0; outline:0;
  cursor:pointer;
}

/* Estado deshabilitado (p!gina no existe) */
.card-split.is-disabled{ cursor:not-allowed; }
.card-split.is-disabled:hover{ transform:none; box-shadow:0 8px 24px rgba(2,6,23,.06); }
.badge{
  position:absolute; top:10px; left:10px;
  background:#e2e8f0; color:#0f172a; border-radius:9999px;
  font-size:.75rem; font-weight:700; padding:.2rem .6rem; z-index:4;
}

/* Responsive */
@media (max-width: 720px){
  .card-split, .card-split.rev{ flex-direction:column; }
  .card-media{ flex: none; }  /* ancho = 100% => altura autom!tica segn 16:9 */
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------------
# Data (respetando tu orden y con los textos completos en desc)
# -------------------------------------------------------------------------
PRODUCTS = [
    {
        "title": "Cedula de impuestos para cierre anual",
        "desc": (
            "Optimiza la preparacion de la declaracion anual de tu empresa con nuestro Papel de Trabajo para Personas Morales en el Regimen General.\n\n"
            "Facilita el calculo y la conciliacion de ingresos, deducciones, coeficiente de utilidad, PTU y otros aspectos fiscales clave como:\n"
            "- Formatos estructurados en Excel.\n"
            "- Ahorrar tiempo\n"
            "- Minimiza errores\n"
            "- Y cumple con tus obligaciones fiscales de manera eficiente."
        ),
        "bullets": [],  # no pintamos <ul> vacio
        "img": IMG_CEDULA,
        "page": "pages/Cedula_Impuestos.py",
        "page_label": "Cedula de impuestos - Acceso",
        "key": "go_cedula",
        "force_logout": True,
    },
    {
        "title": "Monitoreo especializado de EFOS",
        "desc": (
            "?Sabes si la empresa con la que trabajas aparece como EFOS?\n\n"
            "!No pongas en riesgo tu negocio! Trabajar con una empresa incluida en la lista de EFOS puede generar sanciones y problemas fiscales. "
            "Consulta aqui el listado oficial del SAT y verifica a tus proveedores antes de realizar operaciones y evita:\n"
            "- Multas y recargos\n"
            "- Perdida de deducciones fiscales\n"
            "- Auditorias y revisiones fiscales\n"
            "- Problemas legales; en casos graves, pueden derivar en responsabilidades penales."
        ),
        "bullets": [],
        "img": IMG_EFOS,
        "page": "pages/14_Riesgo_fiscal.py",
        "key": "go_monitoreo",
        "force_logout": True,
    },
    {
        "title": "Riesgo fiscal sin sobresaltos",
        "desc": (
            "Ayudamos a identificar riesgos fiscales clave antes de que se conviertan en contingencias. "
            "Analisis automatizado de CFDI, conciliaciones y senales de alerta para ISR, PTU e impuestos trasladados."
        ),
        "bullets": [
            "Monitoreo continuo de inconsistencias",
            "Alertas preventivas para auditorias",
            "Panel ejecutivo con metricas fiscales"
        ],
        "img": IMG_RIESGO,
        "page": "pages/riesgo_fiscal_proximamente.py",
        "key": "go_riesgo_proximamente",
    },
    {
        "title": "Descarga masiva de XML",
        "desc": (
            "Asegura la veracidad y autenticidad de los comprobantes.\n\n"
            "Optimiza la gestin documental y el cumplimiento fiscal.\n\n"
            "Permite procesos automatizados de conciliacin y an!lisis financiero."
        ),
        "bullets": [],
        "img": IMG_XML,
        "page": "pages/Descarga_XML.py",
        "key": "go_xml",
        "force_logout": True,
    },
    {
        "title": "Convertidor de estados de cuenta",
        "desc": (
            "Convierte tus estados de cuenta en informacin clara y lista para analizar, automatiza la lectura y descarga de archivos bancarios "
            "en formato Excel, organizando cargos, abonos, fechas y saldos en segundos. !Ahorra tiempo y toma decisiones con datos precisos al instante!"
        ),
        "bullets": [],
        "img": IMG_ESTADOS_CTA,
        "page": "pages/Convertidor_Estados.py",
        "key": "go_estados",
    },
    {
        "title": "DIOT",
        "desc": (
            "Presenta tu Declaracion Informativa de Operaciones con Terceros en segundos. "
            "Administra tarifas, trabajadores y parametria desde un solo punto y genera el TXT oficial sin errores."
        ),
        "bullets": [],
        "img": IMG_DIOT,
        "page": "pages/22_DIOT_excel_txt.py",
        "key": "go_diot",
        "force_logout": True,
    },
    {
        "title": "Traslado inteligente",
        "desc": (
            "Potencia la eficiencia operativa con una solucin digital que transforma el c!lculo de los costos de traslado. "
            "Nuestra plataforma integra un monitoreo de consumo de disel y c!lculo automatizado de costos (casetas, gastos operativos y administrativos, "
            "mantenimiento, vi!ticos, sueldos, multas, seguros, estadas, etc.). Mediante inteligencia artificial y analtica avanzada, "
            "convierte la informacin en estrategias de innovacin, precisin y control en cada kilmetro."
        ),
        "bullets": [],
        "img": IMG_TRASLADO,
        "page": "pages/1_Calculadora.py",
        "key": "go_traslado",
        "force_logout": True,
    },
    {
        "title": "Generador de plizas contables",
        "desc": (
            "El Generador de Plizas es una herramienta diseada para optimizar el trabajo contable mediante la automatizacin del registro "
            "de movimientos financieros como ingresos, egresos y provisiones. Su principal funcin es convertir y subir archivos Excel (.xlsx) "
            "a programas contables como COI, entre otros sistemas, de manera masiva, r!pida y precisa."
        ),
        "bullets": [],
        "img": IMG_POLIZAS,
        "page": "pages/Generador_Polizas.py",
        "key": "go_polizas",
    },
]

# -------------------------------------------------------------------------
# Encabezado
# -------------------------------------------------------------------------
st.markdown('<div class="landing-title">Bienvenido a Araiza Intelligence</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------------
# Render (idntico layout, con formateo de desc + sin <ul> vaco)
# -------------------------------------------------------------------------
st.markdown('<div class="cards-grid">', unsafe_allow_html=True)
for i, p in enumerate(PRODUCTS):
    exists = page_exists(p["page"])
    alt_cls = "rev" if i % 2 else ""
    dis_cls = " is-disabled" if not exists else ""
    cls = f"card-split {alt_cls}{dis_cls}".strip()

    # Overlay clickeable solo si la p!gina existe
    overlay_html = ""
    if exists:
        href = _product_href(p["page"], force_logout=bool(p.get("force_logout")), label_override=p.get("page_label"))
        overlay_html = f'<div class="overlay-link"><a href="{href}" target="_self"></a></div>'

    badge_html = '<div class="badge">Prximamente</div>' if not exists else ""

    # Descripcin formateada (p!rrafos + vietas si las hay)
    desc_html = as_html_desc(p.get("desc", ""))

    # Bullets adicionales (opcional, si tu dict los trae)
    extra_bullets = p.get("bullets") or []
    extra_list_html = ""
    if extra_bullets:
        lis = "".join(f"<li>{html.escape(b)}</li>" for b in extra_bullets)
        extra_list_html = f'<ul class="card-list">{lis}</ul>'

    img_src = p.get("img") or ""
    media_html = f'<div class="card-media"><img src="{img_src}" alt="{html.escape(p["title"])}"/></div>' if img_src else ""

    st.markdown(
        f"""
        <div class="{cls}">
          {badge_html}
          {media_html}
          <div class="card-copy">
            <h3 class="card-title">{html.escape(p['title'])}</h3>
            {desc_html}
            {extra_list_html}
          </div>
          {overlay_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------------
# Footer
# -------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#64748b;font-size:.78rem;padding:8px 0 18px;">'
    '&copy; 2025 Araiza Intelligence. Todos los derechos reservados.'
    '</div>',
    unsafe_allow_html=True
)
