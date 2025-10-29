# pages/0_Inicio.py — Tarjetas alternadas (zigzag) 100% clickeables con verificación de páginas
from __future__ import annotations
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st

from core.auth import ensure_session_from_token
from core.navigation import PAGE_PARAM_NAMES, render_nav
from pages.components.hero import first_image_base64, inject_hero_css

st.set_page_config(
    page_title="Inicio - Araiza Intelligence",
    page_icon="AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Sesión / estilos base ---
ensure_session_from_token()
inject_hero_css()

ROOT = Path(__file__).resolve().parent.parent     # carpeta raíz del proyecto (donde está app.py)
PAGES_DIR = ROOT / "pages"

# -------- helpers de imagen --------
def image_src_for(candidates: tuple[Path, ...]) -> str | None:
    return first_image_base64(candidates)

def page_exists(rel_page: str) -> bool:
    """
    Verifica que el archivo exista respecto a la raíz del proyecto.
    Acepta valores como 'app.py' o 'pages/1_Calculadora.py'.
    """
    p = (ROOT / rel_page).resolve()
    try:
        # Evita salirte del proyecto con rutas extrañas
        p.relative_to(ROOT)
    except Exception:
        return False
    return p.is_file()


def _product_href(script_path: str, *, force_logout: bool = False) -> str:
    """Construye un href absoluto para el multipage actual."""

    label = PAGE_PARAM_NAMES.get(script_path)
    if label is None:
        label = (
            script_path.replace("pages/", "")
            .replace(".py", "")
            .strip()
        )
    params: dict[str, str] = {"page": label or script_path}
    if force_logout:
        params["logout"] = "1"
    return "/?" + urlencode(params)
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

# -------- navbar --------
render_nav(active_top="inicio", show_inicio=False, show_cta=False)

# -------- CSS --------
st.markdown("""
<style>
.block-container{
  padding-top:56px !important;
  padding-left:clamp(12px,2vw,20px) !important;
  padding-right:clamp(12px,2vw,20px) !important;
  max-width: 1200px !important; margin:0 auto !important;
}

/* Título GRANDE */
.landing-title{
  font-weight:900; 
  font-size: clamp(32px, 3.6vw, 44px); 
  line-height:1.1; 
  text-align:center; 
  color:#0f172a; 
  margin: 0 0 18px;
}

/* GRID */
.cards-grid{ display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:22px; }
@media (max-width:1000px){ .cards-grid{ grid-template-columns: 1fr; } }

/* TARJETA ALTERNADA */
.card-split{
  position:relative;
  display:flex; height:100%;
  border:1px solid rgba(0,0,0,.06); border-radius:14px; background:#fff;
  box-shadow:0 8px 24px rgba(2,6,23,.06); overflow:hidden;
  transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease;
  cursor:pointer;
  isolation:isolate;
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

.card-media{ flex:0 0 42%; background:#f1f5f9; display:flex; align-items:center; justify-content:center; }
.card-media img{ width:100%; height:100%; max-height: 260px; object-fit:cover; }

.card-copy{ flex:1; display:flex; flex-direction:column; padding:16px; position:relative; z-index:3; }
.card-title{ margin:0 0 6px; font-weight:800; color:#0f172a; font-size:1.25rem; line-height:1.2; }
.card-desc{ margin:0 0 10px; color:#475569; font-size:.95rem; line-height:1.45rem; text-align:justify; }
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

/* Estado deshabilitado (página no existe) */
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
  .card-media{ flex: none; }
  .card-media img{ height: 200px; }
}
</style>
""", unsafe_allow_html=True)

# -------- data --------
PRODUCTS = [
    {"title": "Cédula de impuestos para cierre anual",
     "desc": "Calcula coeficiente de utilidad, integra PTU y cruza deducciones con formatos listos para revisión fiscal.",
     "bullets": ["Simula escenarios antes del envío", "Control por entidad/razón social", "Reportes ejecutivos para dirección"],
     "img": IMG_CEDULA, "page": "pages/XX_Cedula_impuestos.py", "key": "go_cedula"},

    {"title": "Riesgo fiscal sin sobresaltos",
     "desc": "Cruza CFDI contra listas 69/69-B/69-Bis y documenta acciones preventivas ante cambios del SAT.",
     "bullets": ["Detecta EFOS publicados", "Monitoreo de cambios del SAT", "Alertas a finanzas y cumplimiento"],
     "img": IMG_RIESGO, "page": "pages/14_Riesgo_fiscal.py", "key": "go_riesgo", "force_logout": True},

    {"title": "Monitoreo especializado de EFOS",
     "desc": "Identifica proveedores EFOS, conserva historial y evidencia para auditorías internas y externas.",
     "bullets": ["Alertas por cambio de estatus", "Historial por periodo", "Bitácora para legal y fiscal"],
     "img": IMG_EFOS, "page": "pages/XX_Monitoreo_EFOS.py", "key": "go_efos"},

    {"title": "Descarga masiva de XML",
     "desc": "Automatiza la descarga de CFDI con filtros y trazabilidad completa para conciliaciones y fiscalización.",
     "bullets": ["Filtros por periodo/emisor/tipo", "Permisos por usuario", "Integración con validación/timbrado"],
     "img": IMG_XML, "page": "pages/XX_Descarga_XML.py", "key": "go_xml"},

    {"title": "Convertidor de estados de cuenta",
     "desc": "Normaliza bancos y genera archivos para conciliación contable y análisis de flujos.",
     "bullets": ["Lee PDF/XLSX", "Detecta patrones de depósitos/retiros", "Exporta a plantillas de conciliación"],
     "img": IMG_ESTADOS_CTA, "page": "pages/XX_Convertidor_estados.py", "key": "go_estados"},

    {"title": "Traslado inteligente",
     "desc": "Calcula el costo real por ruta: km, peajes, combustible, viáticos y mantenimiento con escenarios comparativos.",
     "bullets": ["Costeo urgente con clientes", "Simulación de rutas y tiempos", "Control de margen operativo"],
     "img": IMG_TRASLADO, "page": "pages/1_Calculadora.py", "key": "go_traslado", "force_logout": True},

    {"title": "Generador de pólizas contables",
     "desc": "Convierte CFDI en pólizas listas para tu ERP, trazables desde factura a registro.",
     "bullets": ["Clasificación contable", "Impuestos y retenciones", "Exportación compatible con tu sistema"],
     "img": IMG_POLIZAS, "page": "pages/XX_Generador_polizas.py", "key": "go_polizas"},
]
# -------- encabezado --------
st.markdown('<div class="landing-title">Bienvenido a Araiza Intelligence</div>', unsafe_allow_html=True)

# -------- render --------
st.markdown('<div class="cards-grid">', unsafe_allow_html=True)
for i, p in enumerate(PRODUCTS):
    exists = page_exists(p["page"])
    alt_cls = "rev" if i % 2 else ""
    dis_cls = " is-disabled" if not exists else ""
    cls = f"card-split {alt_cls}{dis_cls}".strip()

    # Tarjeta
    st.markdown(
        f"""
        <div class="{cls}">
          {'<div class="badge">Próximamente</div>' if not exists else ''}
          <div class="card-media">
            <img src="{p.get('img') or ''}" alt="{p['title']}"/>
          </div>
          <div class="card-copy">
            <h3 class="card-title">{p['title']}</h3>
            <p class="card-desc">{p['desc']}</p>
            <ul class="card-list">
              {''.join(f"<li>{b}</li>" for b in p['bullets'])}
            </ul>
          </div>
        """,
        unsafe_allow_html=True
    )

    # Enlace invisible SOLO si la página existe (no genera error ni “fantasma”)
    if exists:
        href = _product_href(p["page"], force_logout=bool(p.get("force_logout")))
        st.markdown(f'<div class="overlay-link"><a href="{href}" target="_self"></a></div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)  # cierra card-split

st.markdown('</div>', unsafe_allow_html=True)

# -------- footer --------
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#64748b;font-size:.78rem;padding:8px 0 18px;">'
    '&copy; 2025 Araiza Intelligence. Todos los derechos reservados.'
    '</div>',
    unsafe_allow_html=True
)
