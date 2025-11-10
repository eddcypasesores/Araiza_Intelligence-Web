"""Extractor de estados de cuenta Banorte."""

from __future__ import annotations

import os
import re
from typing import List, Tuple

import pandas as pd
import pdfplumber


def _patron_fecha() -> re.Pattern[str]:
    return re.compile(r"\d{2}[-\s][A-Z]{3}[-\s]\d{2}")


def _patron_exclusion() -> re.Pattern[str]:
    return re.compile(
        r"(BANORTE$|INFORMACIÓN DEL PERIODO$|^RESUMEN|^SALDO|DIRECCIÓN:|PRODUCTO$|PÁGINA\s+\d+|^TOTAL\b"
        r"|Línea Directa|Enlace Negocios Avanzada"
        r"|FECHA DESCRIPCIÓN / ESTABLECIMIENTO MONTO DEL DEPOSITO MONTO DEL RETIRO SALDO)",
        re.IGNORECASE,
    )


def _extraer_anio_periodo(pdf: pdfplumber.PDF) -> str:
    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue
        match = re.search(r"\b20\d{2}\b", text)
        if match:
            return match.group(0)[-2:]
    return ""


def _guardar_excel(df: pd.DataFrame, path_pdf: str) -> str:
    nombre_excel = os.path.splitext(os.path.basename(path_pdf))[0] + ".xlsx"
    path_excel = os.path.join("output", nombre_excel)
    os.makedirs("output", exist_ok=True)
    df.to_excel(path_excel, index=False)
    return path_excel


def _extraer_campos(texto: str, anio_periodo: str) -> dict[str, str]:
    fecha_match = re.search(r"\d{2}[-\s][A-Z]{3}[-\s](\d{2})", texto)
    fecha = ""
    if fecha_match:
        anio_mov = fecha_match.group(1)
        if anio_mov == anio_periodo:
            fecha = fecha_match.group(0)

    montos = re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}", texto)
    monto_unico = montos[0] if montos else ""

    clabe = re.search(r"\b\d{18}\b", texto)

    descripcion = " ".join(texto.splitlines())
    descripcion = re.sub(r"^\d{2}[-\s][A-Z]{3}[-\s]\d{2}\s*", "", descripcion)
    descripcion_lower = descripcion.lower()

    match_registro = re.search(r"RFC[:\s]+([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})", descripcion, re.IGNORECASE)
    registro = match_registro.group(1).strip() if match_registro else ""

    match_benef = re.search(r"BENEF:\s*(.+?)(?:\(|$|\n|\r|\-)", descripcion, re.IGNORECASE)
    if match_benef:
        beneficiario = match_benef.group(1).strip()
    elif registro == "MCL2306166R8" or "traspaso entre cuentas" in descripcion_lower:
        beneficiario = "Traspaso entre cuentas"
    elif "intereses exento" in descripcion_lower:
        beneficiario = "INTERESES EXENTO"
    elif "pago de capital" in descripcion_lower:
        beneficiario = "PAGO DE CAPITAL"
    elif "pago de iva" in descripcion_lower or "pago de comisiones" in descripcion_lower:
        beneficiario = "COMISIONES"
    elif any(token in descripcion_lower for token in ["comision orden de pago", "i.v.a. orden de pago"]):
        beneficiario = "COMISION"
    elif any(token in descripcion_lower for token in ["ret otros 96531", "retiro dep. electronico"]):
        beneficiario = "POR COMPROBAR"
    elif any(token in descripcion_lower for token in ["depositos de nomina bonif comision", "bonif iva bonif comision"]):
        beneficiario = "COMISION"
    elif any(token in descripcion_lower for token in ["com memb p.m.", "iva memb p.m."]):
        beneficiario = "COMISION"
    else:
        beneficiario = ""

    cargo = ""
    abono = ""
    texto_upper = texto.upper()
    if "RETIRO" in texto_upper:
        abono = monto_unico
    elif "SPEI RECIBIDO" in texto_upper or "ABONO" in texto_upper:
        cargo = monto_unico
    else:
        abono = monto_unico

    return {
        "Fecha": fecha,
        "Descripción": descripcion,
        "CLABE": clabe.group(0) if clabe else "",
        "Beneficiario": beneficiario,
        "Cargo": cargo,
        "Abono": abono,
        "Registro": registro,
    }


def procesar_pdf(path_pdf: str) -> Tuple[str, pd.DataFrame]:
    movimientos: List[str] = []
    movimiento_actual: List[str] = []

    fecha_pat = _patron_fecha()
    exclusion_pat = _patron_exclusion()

    with pdfplumber.open(path_pdf) as pdf:
        anio_periodo = _extraer_anio_periodo(pdf)

    with pdfplumber.open(path_pdf) as pdf:
        capturando = False
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto:
                continue
            lineas = texto.split("\n")
            for linea in lineas:
                if "DETALLE DE MOVIMIENTOS (PESOS)" in linea:
                    capturando = True
                    continue
                if any(fin in linea for fin in ["INVERSION ENLACE", "COMPROBANTE FISCAL", "OTROS▼", "GAT", "Cadena original", "Versión CFDI"]):
                    capturando = False
                    continue
                if not capturando or exclusion_pat.search(linea):
                    continue

                if fecha_pat.match(linea.strip()[:9]):
                    if movimiento_actual:
                        movimientos.append("\n".join(movimiento_actual))
                        movimiento_actual = []
                movimiento_actual.append(linea.strip())

        if movimiento_actual:
            movimientos.append("\n".join(movimiento_actual))

    datos = [_extraer_campos(mov, anio_periodo) for mov in movimientos]
    df = pd.DataFrame(datos)

    for col in ["Cargo", "Abono"]:
        df[col] = pd.to_numeric(df[col].replace("", "0").str.replace(",", "", regex=True), errors="coerce").fillna(0.0)

    df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d-%b-%y", errors="coerce").dt.strftime("%d/%m/%Y")

    columnas = ["Fecha", "Beneficiario", "CLABE", "Registro", "Cargo", "Abono", "Descripción"]
    df = df[columnas]

    path_excel = _guardar_excel(df, path_pdf)
    return path_excel, df
