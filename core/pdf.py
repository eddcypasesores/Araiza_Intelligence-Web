from io import BytesIO
from datetime import datetime
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

COL_PEAJES_TAG = colors.HexColor("#e3f2fd")
COL_PEAJES_VAL = colors.HexColor("#bbdefb")
COL_PEAJES_TXT = colors.HexColor("#0d47a1")

COL_COMB_TAG = colors.HexColor("#fff3e0")
COL_COMB_VAL = colors.HexColor("#ffe0b2")
COL_COMB_TXT = colors.HexColor("#e65100")

COL_COND_TAG = colors.HexColor("#e8f5e9")
COL_COND_VAL = colors.HexColor("#c8e6c9")
COL_COND_TXT = colors.HexColor("#1b5e20")

COL_VIA_TAG = colors.HexColor("#f3e5f5")
COL_VIA_VAL = colors.HexColor("#e1bee7")
COL_VIA_TXT = colors.HexColor("#6a1b9a")

COL_TOTAL_TAG = colors.HexColor("#d1fae5")
COL_TOTAL_VAL = colors.HexColor("#a7f3d0")
COL_TOTAL_TXT = colors.HexColor("#065f46")

SECTION_COLOR_MAP = {
    "PEAJE": (COL_PEAJES_TAG, COL_PEAJES_VAL, COL_PEAJES_TXT),
    "DIESEL": (COL_COMB_TAG, COL_COMB_VAL, COL_COMB_TXT),
    "MANO DE OBRA": (COL_COND_TAG, COL_COND_VAL, COL_COND_TXT),
    "VIÁTICOS": (COL_VIA_TAG, COL_VIA_VAL, COL_VIA_TXT),
}

DEFAULT_SECTION_COLORS = (COL_TOTAL_TAG, COL_TOTAL_VAL, COL_TOTAL_TXT)


def _pill(label: str, value: str, bg_tag, bg_val, fg_txt):
    table = Table(
        [[label.upper(), value]],
        colWidths=[7.8 * cm, 7.2 * cm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), bg_tag),
                ("BACKGROUND", (1, 0), (1, 0), bg_val),
                ("TEXTCOLOR", (0, 0), (1, 0), fg_txt),
                ("ALIGN", (0, 0), (0, 0), "RIGHT"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("VALIGN", (0, 0), (1, 0), "MIDDLE"),
                ("BOX", (0, 0), (1, 0), 0.6, colors.Color(0, 0, 0, alpha=0.06)),
                ("LEFTPADDING", (0, 0), (1, 0), 8),
                ("RIGHTPADDING", (0, 0), (1, 0), 8),
                ("TOPPADDING", (0, 0), (1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (1, 0), 6),
            ]
        ),
    )
    return table


def _section_table(rows: Iterable[tuple[str, str]]):
    data = [["Detalle", "Valor"]]
    for label, value in rows:
        data.append([str(label), str(value)])
    table = Table(
        data,
        colWidths=[9.0 * cm, 6.0 * cm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        ),
    )
    return table


def build_pdf_costeo(
    ruta_nombre,
    origen,
    destino,
    clase,
    df_peajes,
    total_original,
    total_ajustado,
    km_totales,
    rendimiento,
    precio_litro,
    litros,
    costo_combustible,
    total_general,
    trabajador_sel,
    esquema_conductor,
    horas_estimadas,
    costo_conductor,
    tarifa_dia=None,
    horas_por_dia=None,
    tarifa_hora=None,
    tarifa_km=None,
    viaticos_mxn: float = 0.0,
    section_breakdowns: list[tuple[str, float, list[tuple[str, str]]]] | None = None,
) -> bytes:
    section_breakdowns = section_breakdowns or []

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], alignment=1, fontSize=18, leading=22)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], alignment=0, fontSize=14, leading=18)
    SMALL = ParagraphStyle("SMALL", parent=styles["BodyText"], fontSize=9, leading=12)

    story = [Paragraph("COSTEO DE TRASLADO", H1), Spacer(1, 10)]

    meta = [
        ["Fecha/Hora", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Ruta", ruta_nombre],
        ["Origen", origen],
        ["Destino", destino],
        ["Clase de vehículo", clase],
        ["Esquema conductor", esquema_conductor],
    ]
    meta_table = Table(
        meta,
        colWidths=[4.0 * cm, 12.0 * cm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5f5")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        ),
    )
    story.extend([meta_table, Spacer(1, 12)])

    story.append(Paragraph("PEAJE", H2))
    if df_peajes is not None and len(df_peajes) > 0:
        table_data = [["Plaza", "Tarifa (MXN)", "Estado"]]
        row_styles = []
        for idx, row in df_peajes.reset_index(drop=True).iterrows():
            estado = "Excluida" if bool(row.get("excluir")) else "Incluida"
            table_data.append([
                str(row.get("plaza", "")),
                f"${float(row.get('tarifa', 0.0)):,.2f}",
                estado,
            ])
            if estado == "Excluida":
                row_styles.append(("TEXTCOLOR", (0, idx + 1), (-1, idx + 1), colors.HexColor("#6b7280")))

        peajes_table = Table(
            table_data,
            colWidths=[8.2 * cm, 3.6 * cm, 3.2 * cm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("ALIGN", (2, 1), (2, -1), "CENTER"),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ] + row_styles
            ),
        )
        story.extend([peajes_table, Spacer(1, 4), Paragraph(f"Total detectado (sin exclusiones): ${total_original:,.2f}", SMALL), Spacer(1, 2)])
    else:
        story.extend([Paragraph("Sin registros de casetas para la ruta seleccionada.", SMALL), Spacer(1, 6)])

    story.extend(
        [
            _pill("Subtotal Peajes", f"${total_ajustado:,.2f} MXN", *SECTION_COLOR_MAP["PEAJE"]),
            Spacer(1, 12),
        ]
    )

    comb_rows = [
        ("KM totales", f"{km_totales:,.2f} km"),
        ("Rendimiento", f"{rendimiento:,.2f} km/L"),
        ("Litros estimados", f"{litros:,.2f} L"),
        ("Precio por litro", f"${precio_litro:,.2f}"),
    ]
    story.append(Paragraph("DIESEL", H2))
    story.extend([_section_table(comb_rows), Spacer(1, 4)])
    story.extend(
        [
            _pill("Subtotal Diésel", f"${costo_combustible:,.2f} MXN", *SECTION_COLOR_MAP["DIESEL"]),
            Spacer(1, 12),
        ]
    )

    conductor_rows = [
        ("Conductor", trabajador_sel.get("nombre_completo", "Sin asignar") if isinstance(trabajador_sel, dict) else "Sin asignar"),
        ("Horas estimadas", f"{horas_estimadas:,.2f}"),
    ]
    if tarifa_dia is not None:
        conductor_rows.append(("Tarifa diaria", f"${float(tarifa_dia):,.2f}"))
    conductor_rows.append(("Costo total", f"${costo_conductor:,.2f}"))
    story.append(Paragraph("MANO DE OBRA", H2))
    story.extend([_section_table(conductor_rows), Spacer(1, 4)])
    story.extend(
        [
            _pill("Subtotal Mano de Obra", f"${costo_conductor:,.2f} MXN", *SECTION_COLOR_MAP["MANO DE OBRA"]),
            Spacer(1, 12),
        ]
    )

    story.append(Paragraph("VIÁTICOS", H2))
    story.extend([_section_table([("Monto ingresado", f"${viaticos_mxn:,.2f}")]), Spacer(1, 4)])
    story.extend(
        [
            _pill("Subtotal Viáticos", f"${viaticos_mxn:,.2f} MXN", *SECTION_COLOR_MAP["VIÁTICOS"]),
            Spacer(1, 12),
        ]
    )

    for title, total, rows in section_breakdowns:
        title_upper = title.upper()
        if title_upper in {"PEAJE", "DIESEL", "MANO DE OBRA", "VIÁTICOS"}:
            continue
        story.append(Paragraph(title, H2))
        if rows:
            story.extend([_section_table(rows), Spacer(1, 4)])
        else:
            story.extend([Paragraph("Sin desglose disponible.", SMALL), Spacer(1, 4)])
        tag, val, txt = SECTION_COLOR_MAP.get(title_upper, DEFAULT_SECTION_COLORS)
        story.extend([_pill(f"Subtotal {title}", f"${float(total or 0.0):,.2f} MXN", tag, val, txt), Spacer(1, 12)])

    story.append(Spacer(1, 6))
    story.append(_pill("TOTAL GENERAL", f"${total_general:,.2f} MXN", COL_TOTAL_TAG, COL_TOTAL_VAL, COL_TOTAL_TXT))

    doc.build(story)
    return buf.getvalue()