# pages/1_Calculadora.py  —  Costos de traslado (UI reorganizada + mejoras de tamaño/estilo)
import math
import pandas as pd
import streamlit as st
from pathlib import Path

# -------------------------------
# Configuración de página / estilo
# -------------------------------
if not st.session_state.get("_page_config_set", False):
    st.set_page_config(page_title="Costos de traslado", layout="wide", initial_sidebar_state="expanded")
    st.session_state["_page_config_set"] = True

st.markdown("""
<style>
/* Layout base */
.block-container {padding-top: 1.25rem; padding-bottom: 2rem;}
section[data-testid="stSidebar"] {visibility: visible !important;}
hr {margin: .8rem 0;}

/* Cards */
.card {border:1px solid #eaeaea; border-radius: 1rem; padding: 1.1rem 1.2rem;}
.logo-col {display:flex; align-items:flex-start; justify-content:center;}

/* Títulos y textos en mayúsculas (solo rótulos de UI) */
.title-upper, .section-title, .label-upper {text-transform: uppercase;}
.section-title{
  font-size:1.6rem; font-weight:800; letter-spacing:.6px; margin:.05rem 0 .35rem 0;
}

/* Logo grande */
.logo-box {display:flex; align-items:center; gap:.75rem}
.logo-box h3{margin:0}

/* Nota pequeña */
.small-note {font-size: 12px; opacity: .75;}

/* Subtotales y total (alineados a la derecha en una línea) */
.subtotal-row{
  width:100%;
  display:flex; justify-content:flex-end; align-items:center; gap:.6rem;
  margin-top:.35rem; margin-bottom:.2rem;
}
.subtotal-tag{
  font-weight:800; letter-spacing:.4px; padding:.45rem .65rem; border-radius:.55rem;
  border:1px solid rgba(0,0,0,.05);
}
.subtotal-val{
  font-weight:900; font-size:1.15rem; padding:.45rem .7rem; border-radius:.55rem;
}

/* Paletas por sección */
.peajes-tag{ background:#e3f2fd; color:#0d47a1; }
.peajes-val{ background:#bbdefb; color:#0b3c91; }

.comb-tag { background:#fff3e0; color:#e65100; }
.comb-val { background:#ffe0b2; color:#bf5d00; }

.cond-tag { background:#e8f5e9; color:#1b5e20; }
.cond-val { background:#c8e6c9; color:#124a17; }

/* Viáticos */
.via-tag  { background:#f3e5f5; color:#6a1b9a; }
.via-val  { background:#e1bee7; color:#54157a; }

/* Total general */
.total-row{
  width:100%;
  display:flex; justify-content:flex-end; align-items:center; gap:.8rem;
  margin-top:.6rem; margin-bottom:.2rem;
}
.total-tag{
  text-transform:uppercase; font-weight:900; letter-spacing:.6px;
  background:#e8f5e9; color:#1b5e20; padding:.55rem .8rem; border-radius:.6rem;
  border:1px solid rgba(27,94,32,.15);
}
.total-val{
  font-weight:1000; font-size:1.25rem; padding:.6rem .9rem; border-radius:.6rem;
  background:#c8e6c9; color:#0f3313; border:1px solid rgba(27,94,32,.15);
}

/* Ajustes menores */
.input-label{ font-weight:700; text-transform:uppercase; letter-spacing:.3px; }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# Helpers para logos (tamaño mayor)
# -------------------------------
APP_DIR = Path(__file__).resolve().parent
ASSET_DIRS = [APP_DIR, APP_DIR / "assets", APP_DIR.parent / "assets", APP_DIR.parent / "static"]

def resolve_asset(fname: str) -> str | None:
    for d in ASSET_DIRS:
        p = (d / fname).resolve()
        if p.exists():
            return str(p)
    return None

def safe_logo(fname: str, fallback_emoji: str, width: int = 120):
    path = resolve_asset(fname)
    if path:
        st.image(path, width=width)
    else:
        st.markdown(f"<div style='font-size:46px'>{fallback_emoji}</div>", unsafe_allow_html=True)

# -------------------------------
# Seguridad / sesión
# -------------------------------
if "usuario" not in st.session_state or "rol" not in st.session_state:
    st.warning("⚠️ Debes iniciar sesión primero.")
    try:
        st.switch_page("app.py")
    except Exception:
        st.stop()
    st.stop()

# -------------------------------
# Imports del proyecto
# -------------------------------
from core.db import get_conn, ensure_schema
from core.rutas import load_routes, plazas_catalog, find_subsequence_between
from core.tarifas import tarifa_por_plaza
from core.utils import is_excluded, set_excluded, normalize_name
from core.pdf import build_pdf_cotizacion
from core.driver_costs import read_trabajadores, costo_diario_trabajador_auto

# -------------------------------
# Conexión y datos base
# -------------------------------
conn = get_conn()
ensure_schema(conn)
ROUTES = load_routes()
PLAZAS = plazas_catalog(ROUTES)

# -------------------------------
# Encabezado
# -------------------------------
st.markdown("## <span class='title-upper'>Costos de traslado</span>", unsafe_allow_html=True)
st.caption(f"Conectado como **{st.session_state['usuario']}** · Rol: **{st.session_state['rol']}**")

# ===============================
# 1) PEAJES
# ===============================
st.markdown('<div class="card">', unsafe_allow_html=True)
col_logo, col_title = st.columns([0.12, 0.88])
with col_logo:
    st.markdown("<div class='logo-col'>", unsafe_allow_html=True)
    safe_logo("Logo_Caseta.png", "🛣️", width=120)
    st.markdown("</div>", unsafe_allow_html=True)
with col_title:
    st.markdown('<div class="section-title">Peajes</div>', unsafe_allow_html=True)

# Selectores: Origen, Destino y Clase (por defecto T5)
clases = ["MOTO","AUTOMOVIL","B2","B3","B4","T2","T3","T4","T5","T6","T7","T8","T9"]
default_idx = clases.index("T5")

c1, c2, c3 = st.columns([1.4, 1.4, 0.8])
with c1:
    origen = st.selectbox("ORIGEN", PLAZAS, key="plaza_origen")
with c2:
    destino = st.selectbox("DESTINO", PLAZAS, key="plaza_destino")
with c3:
    clase = st.selectbox("CLASE", clases, index=default_idx)

# Reset de exclusiones si cambian origen/destino/clase
sel = (origen, destino, clase)
if st.session_state.get("last_sel") != sel:
    for k in list(st.session_state.keys()):
        if str(k).startswith("cb_"):
            del st.session_state[k]
    st.session_state["last_sel"] = sel

def compute_route_df():
    found = find_subsequence_between(ROUTES, origen, destino)
    if not found:
        return None, None
    ruta_nombre, secuencia = found
    rows = [{"idx": i, "plaza": c, "tarifa": tarifa_por_plaza(conn, c, clase)} for i, c in enumerate(secuencia)]
    return ruta_nombre, pd.DataFrame(rows)

ruta_nombre, df = compute_route_df()
if not ruta_nombre:
    st.error("❌ No se encontró una ruta que contenga ambas casetas.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# Reset exclusiones si cambia la ruta
if st.session_state.get("route_name") != ruta_nombre:
    st.session_state["route_name"] = ruta_nombre
    st.session_state.setdefault("excluded_set", set())
    st.session_state["excluded_set"].clear()

st.caption(f"Ruta detectada: **{ruta_nombre}**")

# Detalle (excluir casetas)
with st.expander("DESGLOSE DE CASETAS Y EXCLUSIÓN", expanded=False):
    st.markdown("<span class='small-note'>Marca la caseta para excluirla del subtotal.</span>", unsafe_allow_html=True)
    COLS = [0.6, 7.0, 2.4]
    h1, h2, h3 = st.columns(COLS)
    h2.markdown("**PLAZA**")
    h3.markdown("**TARIFA (MXN)**")
    for _, row in df.iterrows():
        idx = int(row["idx"])
        c1x, c2x, c3x = st.columns(COLS)
        default_checked = bool(st.session_state.get(f"cb_{idx}", is_excluded(idx)))
        checked = c1x.checkbox("", key=f"cb_{idx}", value=default_checked, label_visibility="hidden")
        set_excluded(idx, bool(checked))
        c2x.markdown(row["plaza"])
        c3x.markdown(f"${float(row['tarifa']):,.2f}")

def total_ajustado_actual(df_):
    return sum(0 if is_excluded(int(r["idx"])) else float(r["tarifa"]) for _, r in df_.iterrows())

subtotal_peajes = total_ajustado_actual(df)

# Subtotal Peajes (alineado a la derecha, una línea, color azul)
st.markdown(
    f"""
    <div class="subtotal-row">
      <div class="subtotal-tag peajes-tag">Subtotal Peajes</div>
      <div class="subtotal-val peajes-val">${subtotal_peajes:,.2f}</div>
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown('</div>', unsafe_allow_html=True)

# ===============================
# 2) COMBUSTIBLE
# ===============================
st.markdown('<div class="card">', unsafe_allow_html=True)
cl, cr = st.columns([0.12, 0.88])
with cl:
    st.markdown("<div class='logo-col'>", unsafe_allow_html=True)
    safe_logo("Logo_Diesel.png", "⛽", width=120)
    st.markdown("</div>", unsafe_allow_html=True)
with cr:
    st.markdown('<div class="section-title">Combustible</div>', unsafe_allow_html=True)

cc1, cc2, cc3, cc4 = st.columns([1.0, 1.0, 1.0, 1.0])
with cc1:
    distancia_km = st.number_input("DISTANCIA (KM)", min_value=0.0, value=0.0, step=1.0)
with cc2:
    rendimiento = st.number_input("RENDIMIENTO (KM/L)", min_value=0.1, value=30.0, step=0.1)
with cc3:
    precio_litro = st.number_input("PRECIO POR LITRO ($/L)", min_value=0.0, value=26.5, step=0.1)
with cc4:
    viaje_redondo = st.checkbox("VIAJE REDONDO", value=False)

km_totales = float(distancia_km or 0.0) * (2 if viaje_redondo else 1)
litros_estimados = (km_totales / float(rendimiento or 1.0)) if float(rendimiento or 0) > 0 else 0.0
subtotal_combustible = float(litros_estimados) * float(precio_litro or 0.0)

with st.expander("DESGLOSE (SOLO LITROS ESTIMADOS)", expanded=False):
    st.write(f"**Litros estimados:** {litros_estimados:,.2f} L")

st.markdown(
    f"""
    <div class="subtotal-row">
      <div class="subtotal-tag comb-tag">Subtotal Combustible</div>
      <div class="subtotal-val comb-val">${subtotal_combustible:,.2f}</div>
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown('</div>', unsafe_allow_html=True)

# ===============================
# 3) CONDUCTOR (método Edwin)
# ===============================
st.markdown('<div class="card">', unsafe_allow_html=True)
dl, dr = st.columns([0.12, 0.88])
with dl:
    st.markdown("<div class='logo-col'>", unsafe_allow_html=True)
    safe_logo("logo_Trabajador.png", "👷‍♂️", width=120)
    st.markdown("</div>", unsafe_allow_html=True)
with dr:
    st.markdown('<div class="section-title">Conductor</div>', unsafe_allow_html=True)

trab_df = read_trabajadores(conn)
trab_opc = ["(Sin conductor)"] + [f"{r['nombre_completo']} — {r['numero_economico']}" for _, r in trab_df.iterrows()]

cT1, cT2 = st.columns([1.6, .8])
with cT1:
    trab_show = st.selectbox("SELECCIONAR CONDUCTOR", trab_opc, index=0)
with cT2:
    dias_sugeridos = max(1.0, round((km_totales or 0.0)/600.0, 1))
    dias_est = st.number_input("DÍAS ESTIMADOS", min_value=1.0, step=0.5, value=dias_sugeridos)

trabajador_sel = None
if trab_show != "(Sin conductor)":
    for _, r in trab_df.iterrows():
        if f"{r['nombre_completo']} — {r['numero_economico']}" == trab_show:
            trabajador_sel = r.to_dict()
            break

subtotal_conductor = 0.0
costo_diario_total = 0.0
anios = 1
if trabajador_sel:
    mano_obra_dia, impuestos_dia, costo_diario_total, anios = costo_diario_trabajador_auto(trabajador_sel)
    subtotal_conductor = float(dias_est) * float(costo_diario_total)

with st.expander("COSTO DIARIO TOTAL (MÉTODO EDWIN)", expanded=False):
    if trabajador_sel:
        st.write(f"**Costo diario total para la empresa:** ${costo_diario_total:,.2f}")
        st.caption(f"Antigüedad estimada: {anios} año(s) · Salario diario base: ${float(trabajador_sel.get('salario_diario',0)):,.2f}")
    else:
        st.caption("Selecciona un conductor para calcular el costo diario total.")

st.markdown(
    f"""
    <div class="subtotal-row">
      <div class="subtotal-tag cond-tag">Subtotal Conductor</div>
      <div class="subtotal-val cond-val">${subtotal_conductor:,.2f}</div>
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown('</div>', unsafe_allow_html=True)

# ===============================
# 4) VIÁTICOS
# ===============================
st.markdown('<div class="card">', unsafe_allow_html=True)
vl, vr = st.columns([0.12, 0.88])
with vl:
    st.markdown("<div class='logo-col'>", unsafe_allow_html=True)
    safe_logo("Logo_Viaticos.png", "💵", width=120)
    st.markdown("</div>", unsafe_allow_html=True)
with vr:
    st.markdown('<div class="section-title">Viáticos</div>', unsafe_allow_html=True)

viaticos_mxn = st.number_input("VIÁTICOS (MXN)", min_value=0.0, value=0.0, step=50.0, format="%.2f")
st.caption("Este monto no tiene desglose y se suma directamente al total.")

st.markdown(
    f"""
    <div class="subtotal-row">
      <div class="subtotal-tag via-tag">Viáticos</div>
      <div class="subtotal-val via-val">${viaticos_mxn:,.2f}</div>
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown('</div>', unsafe_allow_html=True)

# ===============================
# 5) PARÁMETROS VERSIONADOS + CARGOS ADICIONALES
# ===============================
from core.db import get_active_version_id
from core.params import read_params

vid = get_active_version_id(conn)
PARAMS = read_params(conn, vid)

# Apoyos
peajes_ajustados = float(subtotal_peajes or 0.0)
km_totales = float(km_totales or 0.0)
rendimiento = float(rendimiento or 1.0)
precio_litro = float(precio_litro or 0.0)
litros_estimados = (km_totales / rendimiento) if rendimiento > 0 else 0.0

# Comisión TAG
pct_tag = float(PARAMS["tag"]["pct_comision_tag"] or 0.0)
sub_tag = peajes_ajustados * pct_tag

# DEF
pct_def = float(PARAMS["def"]["pct_def"] or 0.0)
precio_def = float(PARAMS["def"]["precio_def_litro"] or 0.0)
litros_def = litros_estimados * pct_def
sub_def = litros_def * precio_def

# Llantas / Mantto (por km)
sub_llantas = km_totales * float(PARAMS["costos_km"]["costo_llantas_km"] or 0.0)
sub_mantto  = km_totales * float(PARAMS["costos_km"]["costo_mantto_km"] or 0.0)

# Depreciación (por km)
dep = PARAMS["depreciacion"]
dep_anual = (float(dep["costo_adq"]) - float(dep["valor_residual"])) / max(int(dep["vida_anios"]),1)
dep_km = dep_anual / max(int(dep["km_anuales"]),1)
sub_dep = dep_km * km_totales

# Seguros (por km)
seg = PARAMS["seguros"]
seg_km = float(seg["prima_anual"]) / max(int(seg["km_anuales"]),1)
sub_seg = seg_km * km_totales

# Permisos / Custodia
otros = PARAMS["otros"]
sub_permiso  = float(otros["permiso_viaje"] or 0.0)
sub_custodia = km_totales * float(otros["custodia_km"] or 0.0)
# (si quisieras viático parametrizado por día, podrías hacer: viaticos_mxn = viaticos_mxn + dias_est*otros["viatico_dia"])

# Base para financiamiento/overhead/utilidad (según política)
base_conceptos = set(PARAMS["politicas"]["incluye_en_base"])
base_val = 0.0
if "peajes" in base_conceptos:       base_val += peajes_ajustados
if "diesel" in base_conceptos:       base_val += float(subtotal_combustible or 0.0)
if "llantas" in base_conceptos:      base_val += sub_llantas
if "mantto" in base_conceptos:       base_val += sub_mantto
if "depreciacion" in base_conceptos: base_val += sub_dep
if "seguros" in base_conceptos:      base_val += sub_seg
if "viaticos" in base_conceptos:     base_val += float(viaticos_mxn or 0.0)
if "permisos" in base_conceptos:     base_val += sub_permiso
if "def" in base_conceptos:          base_val += sub_def
if "custodia" in base_conceptos:     base_val += sub_custodia
if "tag" in base_conceptos:          base_val += sub_tag
if trabajador_sel and "conductor" in base_conceptos:
    base_val += float(subtotal_conductor or 0.0)

# Financiamiento / Overhead / Utilidad
tasa = float(PARAMS["financiamiento"]["tasa_anual"] or 0.0)
dias_cobro = int(PARAMS["financiamiento"]["dias_cobro"] or 30)
sub_fin = base_val * tasa * (dias_cobro / 360.0)

pct_ov = float(PARAMS["overhead"]["pct_overhead"] or 0.0)
sub_ov = base_val * pct_ov

pct_ut = float(PARAMS["utilidad"]["pct_utilidad"] or 0.0)
sub_ut = (base_val + sub_ov) * pct_ut

with st.expander("CARGOS ADICIONALES (TAG / DEF / LLANTAS / ...)", expanded=False):
    st.write(f"Comisión TAG: ${sub_tag:,.2f}")
    st.write(f"DEF: ${sub_def:,.2f}  (Litros DEF: {litros_def:,.2f})")
    st.write(f"Llantas: ${sub_llantas:,.2f}")
    st.write(f"Mantenimiento: ${sub_mantto:,.2f}")
    st.write(f"Depreciación: ${sub_dep:,.2f}")
    st.write(f"Seguros: ${sub_seg:,.2f}")
    st.write(f"Permisos: ${sub_permiso:,.2f}")
    st.write(f"Custodia: ${sub_custodia:,.2f}")
    st.write(f"Base para financiamiento/overhead/utilidad: ${base_val:,.2f}")
    st.write(f"Financiamiento: ${sub_fin:,.2f}")
    st.write(f"Overhead: ${sub_ov:,.2f}")
    st.write(f"Utilidad: ${sub_ut:,.2f}")

# ===============================
# 6) TOTAL GENERAL (EXTENDIDO) + PDF
# ===============================
total_general = (
    float(subtotal_peajes or 0.0)
    + float(subtotal_combustible or 0.0)
    + float(subtotal_conductor or 0.0)
    + float(viaticos_mxn or 0.0)
    + sub_tag + sub_def + sub_llantas + sub_mantto + sub_dep + sub_seg + sub_permiso + sub_custodia
    + sub_fin + sub_ov + sub_ut
)

st.markdown(
    f"""
    <div class="total-row">
      <div class="total-tag">Total General</div>
      <div class="total-val">${total_general:,.2f}</div>
    </div>
    """,
    unsafe_allow_html=True
)

# Generación de PDF (plantilla actual: peajes + combustible + conductor + viáticos)
try:
    df_pdf = df.copy()
    df_pdf["excluir"] = df_pdf["idx"].apply(lambda i: is_excluded(int(i)))

    trabajador_sel_row = trabajador_sel  # dict o None
    costo_diario_total = 0.0
    anios = 1
    if trabajador_sel_row:
        _, _, costo_diario_total, anios = costo_diario_trabajador_auto(trabajador_sel_row)

    dias_est = float(dias_est or 1.0)
    km_totales_pdf = float(km_totales or 0.0)
    rendimiento_pdf = float(rendimiento or 1.0)
    precio_litro_pdf = float(precio_litro or 0.0)
    litros_estimados_pdf = float(litros_estimados if rendimiento_pdf > 0 else 0.0)

    subtotal_peajes_pdf = float(subtotal_peajes or 0.0)
    subtotal_combustible_pdf = float(subtotal_combustible or 0.0)
    subtotal_conductor_pdf = float(dias_est * costo_diario_total) if trabajador_sel_row else 0.0
    viaticos_mxn_pdf = float(viaticos_mxn or 0.0)

    horas_totales = dias_est * 9.0
    total_pdf = subtotal_peajes_pdf + subtotal_combustible_pdf + subtotal_conductor_pdf + viaticos_mxn_pdf

    pdf_bytes = build_pdf_cotizacion(
        ruta_nombre=ruta_nombre, origen=origen, destino=destino, clase=clase,
        df_peajes=df_pdf[["plaza", "tarifa", "excluir"]],
        total_original=float(df["tarifa"].sum()),
        total_ajustado=subtotal_peajes_pdf,
        km_totales=km_totales_pdf, rendimiento=rendimiento_pdf, precio_litro=precio_litro_pdf,
        litros=litros_estimados_pdf, costo_combustible=subtotal_combustible_pdf,
        total_general=total_pdf,
        trabajador_sel=trabajador_sel_row,
        esquema_conductor="Por día (método Edwin)" if trabajador_sel_row else "Sin conductor",
        horas_estimadas=horas_totales,
        costo_conductor=subtotal_conductor_pdf,
        tarifa_dia=float(costo_diario_total) if trabajador_sel_row else None,
        horas_por_dia=None,
        tarifa_hora=None, tarifa_km=None,
        viaticos_mxn=viaticos_mxn_pdf
    )

    st.download_button(
        "📄 DESCARGAR COTIZACIÓN (PDF)",
        data=pdf_bytes,
        file_name=f"cotizacion_{normalize_name(origen)}_{normalize_name(destino)}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
except Exception as e:
    st.warning(f"No se pudo generar PDF: {e}")
