# core/pdf.py
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

# Paleta (alineada con la UI)
COL_PEAJES_TAG = colors.HexColor("#e3f2fd")
COL_PEAJES_VAL = colors.HexColor("#bbdefb")
COL_PEAJES_TXT = colors.HexColor("#0d47a1")

COL_COMB_TAG   = colors.HexColor("#fff3e0")
COL_COMB_VAL   = colors.HexColor("#ffe0b2")
COL_COMB_TXT   = colors.HexColor("#e65100")

COL_COND_TAG   = colors.HexColor("#e8f5e9")
COL_COND_VAL   = colors.HexColor("#c8e6c9")
COL_COND_TXT   = colors.HexColor("#1b5e20")

COL_VIA_TAG    = colors.HexColor("#f3e5f5")
COL_VIA_VAL    = colors.HexColor("#e1bee7")
COL_VIA_TXT    = colors.HexColor("#6a1b9a")

COL_TOTAL_TAG  = COL_COND_TAG
COL_TOTAL_VAL  = COL_COND_VAL
COL_TOTAL_TXT  = COL_COND_TXT

def _pill(label: str, value: str, bg_tag, bg_val, fg_txt):
    """Devuelve dos celdas estilo 'pill' (etiqueta + valor)."""
    t = Table(
        [[label.upper(), value]],
        colWidths=[7.8*cm, 7.2*cm],
        style=TableStyle([
            ("BACKGROUND", (0,0), (0,0), bg_tag),
            ("BACKGROUND", (1,0), (1,0), bg_val),
            ("TEXTCOLOR",  (0,0), (1,0), fg_txt),
            ("ALIGN",      (0,0), (0,0), "RIGHT"),
            ("ALIGN",      (1,0), (1,0), "RIGHT"),
            ("VALIGN",     (0,0), (1,0), "MIDDLE"),
            ("BOX",        (0,0), (1,0), 0.6, colors.Color(0,0,0,alpha=0.06)),
            ("LEFTPADDING",(0,0), (1,0), 8),
            ("RIGHTPADDING",(0,0),(1,0), 8),
            ("TOPPADDING", (0,0), (1,0), 6),
            ("BOTTOMPADDING",(0,0),(1,0), 6),
        ])
    )
    return t

# core/pdf.py
# ... imports y colores iguales ...

def build_pdf_cotizacion(
    ruta_nombre, origen, destino, clase,
    df_peajes, total_original, total_ajustado,
    km_totales, rendimiento, precio_litro, litros, costo_combustible,
    total_general,
    trabajador_sel, esquema_conductor, horas_estimadas, costo_conductor,
    tarifa_dia=None, horas_por_dia=None, tarifa_hora=None, tarifa_km=None,
    viaticos_mxn: float = 0.0,
    otros_conceptos: list[tuple[str, float]] | None = None,   # <— NUEVO
) -> bytes:
    """
    Genera PDF con:
      - Peajes (tabla + SUBTOTAL PEAJES)
      - Combustible (datos + SUBTOTAL COMBUSTIBLE)
      - Conductor (datos + SUBTOTAL CONDUCTOR)
      - Viáticos (SUBTOTAL VIÁTICOS)
      - Otros conceptos (tabla simple con rubro + monto)     # <— NUEVO
      - TOTAL GENERAL (coincidente con el mostrado en la app)
    """
    otros_conceptos = otros_conceptos or []

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], alignment=1, fontSize=18, leading=22)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], alignment=0, fontSize=14, leading=18)
    SMALL = ParagraphStyle("SMALL", parent=styles["BodyText"], fontSize=9, leading=12)

    story = []
    story += [Paragraph("COTIZACIÓN DE COSTOS DE TRASLADO", H1), Spacer(1, 10)]

    meta = [
        ["Fecha/Hora", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Ruta", ruta_nombre],
        ["Origen", origen],
        ["Destino", destino],
        ["Clase de vehículo", clase],
    ]
    t_meta = Table(meta, colWidths=[4.0*cm, 12.0*cm])
    t_meta.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("BOX",(0,0),(-1,-1),0.25,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.25,colors.grey),
    ]))
    story += [t_meta, Spacer(1, 12)]

    # ---------- PEAJES ----------
    # (idéntico a tu versión actual)
    # ... (código igual que ya tienes) ...

    # Subtotal peajes (ajustado)
    story += [_pill("Subtotal Peajes", f"${total_ajustado:,.2f} MXN", COL_PEAJES_TAG, COL_PEAJES_VAL, COL_PEAJES_TXT)]
    story += [Spacer(1, 12)]

    # ---------- COMBUSTIBLE ----------
    # ... (código igual que ya tienes) ...
    story += [_pill("Subtotal Combustible", f"${costo_combustible:,.2f} MXN", COL_COMB_TAG, COL_COMB_VAL, COL_COMB_TXT)]
    story += [Spacer(1, 12)]

    # ---------- CONDUCTOR ----------
    # ... (código igual que ya tienes) ...
    story += [_pill("Subtotal Conductor", f"${costo_conductor:,.2f} MXN", COL_COND_TAG, COL_COND_VAL, COL_COND_TXT)]
    story += [Spacer(1, 12)]

    # ---------- VIÁTICOS ----------
    story += [Paragraph("VIÁTICOS", H2)]
    story += [_pill("Subtotal Viáticos", f"${viaticos_mxn:,.2f} MXN", COL_VIA_TAG, COL_VIA_VAL, COL_VIA_TXT)]
    story += [Spacer(1, 14)]

    # ---------- OTROS CONCEPTOS (llantas, mantto, depreciación, etc.) ----------
    if otros_conceptos:
        story += [Paragraph("OTROS CONCEPTOS", H2)]
        data = [["Concepto", "Monto (MXN)"]]
        for titulo, monto in otros_conceptos:
            data.append([str(titulo), f"${float(monto):,.2f}"])
        t_otros = Table(data, colWidths=[10.7*cm, 5.3*cm])
        t_otros.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f0f0f0")),
            ("BOX",(0,0),(-1,-1),0.25,colors.grey),
            ("INNERGRID",(0,0),(-1,-1),0.25,colors.grey),
            ("ALIGN",(1,1),(1,-1),"RIGHT"),
        ]))
        story += [t_otros, Spacer(1, 14)]

    # ---------- TOTAL GENERAL (el MISMO que en la pantalla) ----------
    total_table = Table(
        [[ "TOTAL GENERAL", f"${total_general:,.2f} MXN" ]],
        colWidths=[10.7*cm, 5.3*cm],
        style=TableStyle([
            ("BACKGROUND",(0,0),(0,0), COL_TOTAL_TAG),
            ("BACKGROUND",(1,0),(1,0), COL_TOTAL_VAL),
            ("TEXTCOLOR",(0,0),(1,0), COL_TOTAL_TXT),
            ("ALIGN",(1,0),(1,0),"RIGHT"),
            ("BOX",(0,0),(1,0),0.8, COL_TOTAL_TXT),
            ("TOPPADDING",(0,0),(1,0),8),
            ("BOTTOMPADDING",(0,0),(1,0),8),
        ])
    )
    story += [total_table]

    doc.build(story)
    return buf.getvalue()
