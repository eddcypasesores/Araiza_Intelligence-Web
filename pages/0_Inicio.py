# pages/0_Inicio.py — Héroe más bajo, tarjetas angostas, texto pequeño/legible y “hover-ready”
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode
from textwrap import dedent
import html
import streamlit as st

# --- Proyecto
from core.auth import ensure_session_from_token
from core.navigation import render_nav
from pages.components.hero import first_image_base64, inject_hero_css

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Inicio - Araiza Intelligence",
    page_icon="AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ensure_session_from_token()
inject_hero_css()

ROOT = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------------
# Redirección por query param ?goto=pages/Algo.py  (+ limpia sesión si logout=1)
# -----------------------------------------------------------------------------
try:
    qp = dict(st.query_params)  # Streamlit >= 1.32
except Exception:
    qp = st.experimental_get_query_params()

dest = qp.get("goto")
if isinstance(dest, list):
    dest = dest[-1] if dest else None

if dest:
    if qp.get("logout") in (["1"], "1", 1, True):
        st.session_state.clear()
    try:
        st.switch_page(dest)  # ej: "pages/Descarga_masiva_xml.py"
    except Exception:
        pass
    st.stop()

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def image_src_for(candidates: tuple[Path, ...]) -> str | None:
    return first_image_base64(candidates)

def page_exists(rel_page: str) -> bool:
    p = (ROOT / rel_page).resolve()
    try:
        p.relative_to(ROOT)
    except Exception:
        return False
    return p.is_file()

def _normalize_page_path(p: str) -> str | None:
    if not isinstance(p, str):
        return None
    p = p.strip()
    if not p:
        return None
    if not p.startswith("pages/"):
        p = f"pages/{p}"
    if not p.endswith(".py"):
        p += ".py"
    return p

def _product_href(script_path: str, *, force_logout: bool = False) -> str:
    page = _normalize_page_path(script_path)
    if not page:
        return "#"
    params: dict[str, str] = {"goto": page}
    if force_logout:
        params["logout"] = "1"
    return "?" + urlencode(params)

def as_html_desc(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\r\n","\n").replace("\r","\n").strip()
    lines = [ln.rstrip() for ln in t.split("\n")]
    bullets = [ln[2:].strip() for ln in lines if ln.startswith("- ")]
    body = [ln for ln in lines if not ln.startswith("- ") and ln != ""]
    parts = []
    if body:
        para = html.escape("\n".join(body)).replace("\n\n","<br><br>").replace("\n"," ")
        parts.append(f'<p class="card-desc">{para}</p>')
    if bullets:
        lis = "".join(f"<li>{html.escape(x)}</li>" for x in bullets)
        parts.append(f'<ul class="card-list">{lis}</ul>')
    return "".join(parts)

# -----------------------------------------------------------------------------
# Imágenes
# -----------------------------------------------------------------------------
IMG_LOGO        = image_src_for((Path("assets/logo.jpg"), Path(__file__).resolve().parent/"assets"/"logo.jpg"))
IMG_RIESGO      = image_src_for((Path("assets/riesgo_cover.png"), Path(__file__).resolve().parent/"assets"/"riesgo_cover.png"))
IMG_TRASLADO    = image_src_for((Path("assets/traslado_inteligente_card.png"), Path(__file__).resolve().parent/"assets"/"traslado_inteligente_card.png"))
IMG_DIOT        = image_src_for((Path("assets/diot_card.png"), Path(__file__).resolve().parent/"assets"/"diot_card.png"))
IMG_EFOS        = image_src_for((Path("assets/efos_card.png"), Path(__file__).resolve().parent/"assets"/"efos_card.png"))
IMG_XML         = image_src_for((Path("assets/descarga_masiva_xml_card.png"), Path(__file__).resolve().parent/"assets"/"descarga_masiva_xml_card.png"))
IMG_POLIZAS     = image_src_for((Path("assets/generador_poliza_card.png"), Path(__file__).resolve().parent/"assets"/"generador_poliza_card.png"))
IMG_ESTADOS_CTA = image_src_for((Path("assets/convertidor_estados_cuenta.png"), Path(__file__).resolve().parent/"assets"/"convertidor_estados_cuenta.png"))
IMG_CEDULA      = image_src_for((Path("assets/cedula_impuestos_card.png"), Path(__file__).resolve().parent/"assets"/"cedula_impuestos_card.png"))

# -----------------------------------------------------------------------------
# Navbar
# -----------------------------------------------------------------------------
render_nav(active_top="inicio", show_inicio=False, show_cta=False)

# -----------------------------------------------------------------------------
# CSS — héroe bajo + tarjetas angostas/bajas + texto pequeño/legible
# -----------------------------------------------------------------------------
st.markdown(dedent("""
<style>
:root{
  --azul:#2563EB; --azul-600:#1D4ED8; --azul-50:#EFF6FF;
  --ink:#0F172A; --muted:#475569; --line:#E2E8F0; --card:#FFFFFF;
}
.block-container{
  padding-top:40px!important;
  padding-left:clamp(12px,2vw,20px)!important;
  padding-right:clamp(12px,2vw,20px)!important;
  max-width:1280px!important;
  margin:0 auto!important;
}

/* ===== HERO (más bajo) ===== */
.hero-wrap{
  position:relative; border-radius:20px; 
  padding: clamp(16px, 4vw, 32px);
  background:
    radial-gradient(1200px 600px at 15% 10%, rgba(37,99,235,.08), transparent 60%),
    radial-gradient(1000px 500px at 85% 30%, rgba(37,99,235,.10), transparent 70%),
    linear-gradient(#FFF,#FFF);
  border:1px solid var(--line); box-shadow:0 10px 30px rgba(2,6,23,.06);
}
.hero-grid{ 
  display:grid; 
  gap: clamp(12px, 2.5vw, 22px);
  grid-template-columns:1.2fr .8fr; 
  align-items:center;
}
@media (max-width:900px){ .hero-grid{ grid-template-columns:1fr; } }
/* Tamaños de texto del héroe — pequeños pero visibles */
.hero-title-main{ margin:0; color:var(--ink); font-weight:900; line-height:1.05; font-size:clamp(34px, 4.6vw, 50px); letter-spacing:-.01em; }
.hero-subtitle{ margin:4px 0 0; color:var(--muted); font-size:clamp(14px, 1.25vw, 17px); line-height:1.32; }
.hero-logo{ display:flex; align-items:center; justify-content:center; }
.hero-logo .logo{
  width: min(120px, 45%);
  aspect-ratio: 1 / 1;
  object-fit: contain;
  border-radius: 20px;
  filter: drop-shadow(0 6px 12px rgba(29,78,216,.15));
}
@media (max-width: 900px){
  .hero-logo .logo{ width: min(95px, 40%); border-radius: 18px; }
}

/* ===== CONTENEDOR AZUL ===== */
.modules-wrap{
  margin-top: clamp(12px, 2.5vw, 20px);
  border-radius:20px;
  padding: clamp(12px, 2.2vw, 18px);
  background: linear-gradient(180deg, color-mix(in srgb, var(--azul) 16%, #fff) 0%, #fff 60%);
  border:1px solid color-mix(in srgb, var(--azul) 25%, var(--line));
  box-shadow: 0 10px 28px rgba(2,6,23,.07) inset, 0 8px 22px rgba(2,6,23,.06);
}

/* ===== GRID — TARJETAS MÁS ANGOSTAS (solo ancho) ===== */
.cards-grid{
  display:grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 260px));
  justify-content: center;
  gap: clamp(14px, 2.2vw, 18px);
}

/* ===== Tarjeta vertical COMPACTA Y BAJA ===== */
.card-vertical{
  position:relative; display:flex; flex-direction:column;
  border:1px solid var(--line); border-radius:14px; background:var(--card);
  box-shadow:0 6px 18px rgba(2,6,23,.06); overflow:hidden; isolation:isolate;
  transition:transform .12s ease, box-shadow .12s ease, border-color .12s ease; cursor:pointer;
  min-height:auto;
}
/* Hover real se activa con .ai-ready (ver abajo) */
.card-vertical:hover{ transform:none; box-shadow:0 6px 18px rgba(2,6,23,.06); }

/* Imagen baja */
.card-media{
  width:100%; background:#F8FAFC; display:flex; align-items:center; justify-content:center;
  overflow:hidden; aspect-ratio:16/9; max-height: 90px;
}
@media (max-width: 1400px){ .card-media{ max-height: 96px; } }
@media (max-width: 980px){ .card-media{ max-height: 100px; } }
@media (max-width: 640px){ .card-media{ max-height: 96px; } }
.card-media img{ width:100%; height:100%; object-fit:contain; }

/* ===== Texto pequeño pero visible en tarjetas ===== */
.card-copy{ padding:8px 10px 10px; }
.card-title{ margin:0 0 2px; font-weight:800; color:var(--ink); font-size:.84rem; line-height:1.12; letter-spacing:.005em; }
.card-desc{
  margin:0; color:var(--muted); font-size:.76rem; line-height:1.12rem; text-align:justify;
  display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;
}
.card-list{ margin:6px 0 0; padding-left:1rem; color:var(--muted); font-size:.76rem; line-height:1.10rem; }
.card-list li{ margin:0 0 .16rem; }
.card-list li::marker{ color: var(--azul-600); }

/* Enlace overlay (solo activas) */
.overlay-link{ position:absolute; inset:0; z-index:4; }
.overlay-link a{ position:absolute; inset:0; display:block; width:100%; height:100%; opacity:0; text-indent:-9999px; }

/* Ribbon Próximamente */
.ribbon{ position:absolute; top:10px; left:-8px; z-index:5; background: var(--azul-600); color:#fff; font-weight:800; font-size:.72rem; padding:.3rem .65rem .3rem .9rem; border-radius:10px; box-shadow:0 6px 14px rgba(29,78,216,.35); letter-spacing:.01em; }
.ribbon::after{ content:""; position:absolute; left:0; top:100%; border-width:8px; border-style:solid; border-color: color-mix(in srgb, var(--azul-600) 80%), transparent transparent transparent; }

/* Deshabilitadas */
.card-vertical.is-disabled, .card-vertical.is-disabled *{ cursor: not-allowed !important; }
.card-vertical.is-disabled .overlay-link{ display:none !important; }
.card-vertical.is-disabled .card-media, .card-vertical.is-disabled .card-copy{ opacity:.88; }

/* Footer */
hr{ border:0; border-top:1px solid var(--line); margin:20px 0 10px; }
.footer{ text-align:center; color:#64748b; font-size:.78rem; padding:6px 0 16px; }
</style>
"""), unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Hover solo cuando la página está lista (evita “hover” inicial)
# -----------------------------------------------------------------------------
st.markdown("""
<script>
window.addEventListener('load', () => {
  document.documentElement.classList.add('ai-ready');
});
</script>
<style>
.ai-ready .card-vertical:hover{
  transform: translateY(-2px);
  box-shadow: 0 12px 26px rgba(2,6,23,.10);
  border-color: color-mix(in srgb, var(--azul) 18%, var(--line));
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# DATA
# -----------------------------------------------------------------------------
PRODUCTS = [
    {
        "title": "Cédula de impuestos para cierre anual",
        "desc": (
            "Prepara tu cierre anual sin estrés. Calcula y concilia ingresos, deducciones, coeficiente y PTU en plantillas Excel listas, reduciendo tiempo y errores."
        ),
        "img": IMG_CEDULA,
        "page": "pages/Cedula_Impuestos.py",
        "key": "go_cedula",
        "force_logout": True,
    },
    {
        "title": "Monitoreo especializado de EFOS",
        "desc": (
            "Verifica en segundos si un RFC es EFOS en el SAT. Evita multas, pérdida de deducciones y auditorías con alertas claras y oportunas."
        ),
        "img": IMG_EFOS,
        "page": "pages/14_Riesgo_fiscal.py",
        "key": "go_monitoreo",
        "force_logout": True,
    },
    {
        "title": "Riesgo fiscal sin sobresaltos",
        "desc": (
            "Detecta riesgos antes de que cuesten: análisis de CFDI, conciliaciones y señales de alerta en ISR, PTU e impuestos trasladados."
        ),
        "img": IMG_RIESGO,
        "page": "pages/Riesgos_fiscales.py",
        "key": "go_riesgo",
        "force_logout": True,
    },
    {
        "title": "Descarga masiva de XML",
        "desc": (
            "Descarga y organiza CFDI de forma masiva. Garantiza autenticidad y acelera la conciliación y el análisis financiero."
        ),
        "img": IMG_XML,
        "page": "pages/Descarga_masiva_xml.py",
        "key": "go_xml",
        "force_logout": True,
    },
    {
        "title": "Convertidor de estados de cuenta",
        "desc": (
            "Convierte estados bancarios a Excel limpio en segundos: cargos, abonos, fechas y saldos listos para analizar."
        ),
        "img": IMG_ESTADOS_CTA,
        "page": "pages/convertidor_estados_cuenta.py",
        "key": "go_estados",
    },
    {
        "title": "DIOT",
        "desc": (
            "Genera el TXT oficial de la DIOT sin errores. Carga tus datos y presenta en minutos, con validaciones automáticas."
        ),
        "img": IMG_DIOT,
        "page": "pages/22_DIOT_excel_txt.py",
        "key": "go_diot",
        "force_logout": True,
    },
    {
        "title": "Traslado inteligente",
        "desc": (
            "Calcula el costo real de cada ruta: casetas, diésel, mantenimiento, viáticos y más, con analítica para decidir con precisión."
        ),
        "img": IMG_TRASLADO,
        "page": "pages/1_Calculadora.py",
        "key": "go_traslado",
        "force_logout": True,
    },
    {
        "title": "Generador de Pólizas contables",
        "desc": (
            "Automatiza pólizas de ingresos, egresos y provisiones. Convierte Excel a sistemas contables en lote, rápido y exacto."
        ),
        "img": IMG_POLIZAS,
        "page": "pages/generador_polizas.py",
        "key": "go_polizas",
    },
]

# -----------------------------------------------------------------------------
# Héroe
# -----------------------------------------------------------------------------
st.markdown(dedent(f"""
<section class="hero-wrap">
  <div class="hero-grid">
    <div>
      <h1 class="hero-title-main">Bienvenido a Araiza Intelligence</h1>
      <p class="hero-subtitle">Contabilidad precisa, impulsada por tecnología</p>
    </div>
    <div class="hero-logo">
      {'<img class="logo" src="'+IMG_LOGO+'" alt="Logo Araiza Intelligence"/>' if IMG_LOGO else '<div style="font-weight:800;font-size:44px;color:#1D4ED8;">AI</div>'}
    </div>
  </div>
</section>
"""), unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Tarjetas
# -----------------------------------------------------------------------------
cards_html_parts = ['<section class="modules-wrap"><div class="cards-grid">']
for p in PRODUCTS:
    exists = page_exists(p["page"]) if p.get("page") else False
    dis_cls = " is-disabled" if not exists else ""
    cls = f"card-vertical{dis_cls}"
    href = _product_href(p["page"], force_logout=bool(p.get("force_logout"))) if exists else None
    overlay_html = f'<div class="overlay-link"><a href="{href}" target="_self"></a></div>' if href else ""
    ribbon_html = '' if exists else '<div class="ribbon">Próximamente</div>'
    desc_html = as_html_desc(p.get("desc", ""))
    img_src = p.get("img") or ""
    media_html = f'<div class="card-media"><img src="{img_src}" alt="{html.escape(p["title"])}"/></div>' if img_src else ""
    cards_html_parts.append(
        f'<article class="{cls}">'
        f'{ribbon_html}'
        f'{media_html}'
        f'<div class="card-copy"><h3 class="card-title">{html.escape(p["title"])}</h3>{desc_html}</div>'
        f'{overlay_html}'
        f'</article>'
    )
cards_html_parts.append("</div></section>")
st.markdown(dedent("".join(cards_html_parts)), unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Footer
# -----------------------------------------------------------------------------
st.markdown("<hr/>", unsafe_allow_html=True)
st.markdown('<div class="footer">&copy; 2025 Araiza Intelligence. Todos los derechos reservados.</div>', unsafe_allow_html=True)
