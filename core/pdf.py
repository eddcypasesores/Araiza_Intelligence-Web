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

def build_pdf_cotizacion(
    ruta_nombre, origen, destino, clase,
    df_peajes, total_original, total_ajustado,
    km_totales, rendimiento, precio_litro, litros, costo_combustible,
    total_general,
    trabajador_sel, esquema_conductor, horas_estimadas, costo_conductor,
    tarifa_dia=None, horas_por_dia=None, tarifa_hora=None, tarifa_km=None,
    viaticos_mxn: float = 0.0
) -> bytes:
    """
    Genera PDF con:
      - Peajes (tabla + SUBTOTAL PEAJES)
      - Combustible (datos + SUBTOTAL COMBUSTIBLE)
      - Conductor (datos + SUBTOTAL CONDUCTOR)
      - Viáticos (SUBTOTAL VIÁTICOS)
      - TOTAL GENERAL = suma de los 4
    Nota: total_original queda solo para referencia interna; el PDF muestra únicamente 'Subtotal peajes'.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle(
        "H1", parent=styles["Heading1"], alignment=1,
        fontSize=18, leading=22
    )
    H2 = ParagraphStyle(
        "H2", parent=styles["Heading2"], alignment=0,
        fontSize=14, leading=18
    )
    SMALL = ParagraphStyle("SMALL", parent=styles["BodyText"], fontSize=9, leading=12)

    story = []

    # Título general
    story += [Paragraph("COTIZACIÓN DE COSTOS DE TRASLADO", H1), Spacer(1, 10)]

    # Meta
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

    # ======================
    # PEAJES
    # ======================
    story += [Paragraph("PEAJES (CASETAS)", H2)]
    data = [["#", "Plaza", "Tarifa (MXN)", "Excluida"]]
    for i, r in df_peajes.reset_index(drop=True).iterrows():
        data.append([
            str(i+1),
            r["plaza"],
            f"${float(r['tarifa']):,.2f}",
            "Sí" if r.get("excluir", False) else "No"
        ])
    t_peajes = Table(data, colWidths=[1.2*cm, 9.0*cm, 3.5*cm, 2.3*cm])
    t_peajes.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f0f0f0")),
        ("BOX",(0,0),(-1,-1),0.25,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.25,colors.grey),
        ("ALIGN",(2,1),(2,-1),"RIGHT"),
        ("ALIGN",(3,1),(3,-1),"CENTER"),
    ]))
    story += [t_peajes, Spacer(1, 6)]

    # SUBTOTAL PEAJES (solo el ajustado)
    story += [_pill("Subtotal Peajes", f"${total_ajustado:,.2f} MXN", COL_PEAJES_TAG, COL_PEAJES_VAL, COL_PEAJES_TXT)]
    story += [Spacer(1, 12)]

    # ======================
    # COMBUSTIBLE
    # ======================
    story += [Paragraph("COMBUSTIBLE", H2)]
    t_comb = Table([
        ["Distancia considerada (km)", f"{km_totales:,.1f}"],
        ["Rendimiento (km/L)", f"{rendimiento:,.2f}"],
        ["Precio por litro ($/L)", f"{precio_litro:,.2f}"],
        ["Litros estimados (L)", f"{litros:,.2f}"],
    ], colWidths=[10.7*cm, 5.3*cm])
    t_comb.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("ALIGN",(1,0),(1,-1),"RIGHT"),
        ("BOX",(0,0),(-1,-1),0.25,colors.grey),
    ]))
    story += [t_comb, Spacer(1, 6)]

    story += [_pill("Subtotal Combustible", f"${costo_combustible:,.2f} MXN", COL_COMB_TAG, COL_COMB_VAL, COL_COMB_TXT)]
    story += [Spacer(1, 12)]

    # ======================
    # CONDUCTOR
    # ======================
    story += [Paragraph("CONDUCTOR", H2)]
    filas_drv = []
    if trabajador_sel:
        filas_drv += [
            ["Nombre", trabajador_sel.get("nombre","")],
            ["Número económico", trabajador_sel.get("numero_economico","")],
        ]
    filas_drv += [
        ["Esquema", esquema_conductor],
        ["Horas estimadas (h)", f"{horas_estimadas:,.1f}"],
    ]
    if tarifa_dia is not None: filas_drv.insert(2, ["Tarifa por día (cálculo)", f"${tarifa_dia:,.2f}"])
    if horas_por_dia is not None: filas_drv.insert(3, ["Horas por día (ref.)", f"{horas_por_dia:,.1f}"])
    if tarifa_hora is not None: filas_drv.insert(2, ["Tarifa por hora", f"${tarifa_hora:,.2f}"])
    if tarifa_km is not None: filas_drv.insert(2, ["Tarifa por km", f"${tarifa_km:,.2f}"])

    t_drv = Table(filas_drv, colWidths=[10.7*cm, 5.3*cm])
    t_drv.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("ALIGN",(1,0),(1,-1),"RIGHT"),
        ("BOX",(0,0),(-1,-1),0.25,colors.grey),
    ]))
    story += [t_drv, Spacer(1, 6)]

    story += [_pill("Subtotal Conductor", f"${costo_conductor:,.2f} MXN", COL_COND_TAG, COL_COND_VAL, COL_COND_TXT)]
    story += [Spacer(1, 12)]

    # ======================
    # VIÁTICOS
    # ======================
    story += [Paragraph("VIÁTICOS", H2)]
    story += [_pill("Subtotal Viáticos", f"${viaticos_mxn:,.2f} MXN", COL_VIA_TAG, COL_VIA_VAL, COL_VIA_TXT)]
    story += [Spacer(1, 14)]

    # ======================
    # TOTAL GENERAL
    # ======================
    # NOTA: total_general debe incluir los 4 componentes (peajes ajustados + combustible + conductor + viáticos)
    total_table = Table(
        [[ "TOTAL GENERAL (Peajes + Combustible + Conductor + Viáticos)", f"${total_general:,.2f} MXN" ]],
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
