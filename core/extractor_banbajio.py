"""Extractor de movimientos para estados de cuenta BanBajio."""

from __future__ import annotations

import re
from typing import List, Optional

import pandas as pd
import pdfplumber

MESES = {
    "ENE": "01",
    "FEB": "02",
    "MAR": "03",
    "ABR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AGO": "08",
    "SEP": "09",
    "OCT": "10",
    "NOV": "11",
    "DIC": "12",
}

FECHA_RE = re.compile(r"^\d{1,2}\s+[A-Z]{3}", flags=re.IGNORECASE)
AMOUNT_RE = re.compile(r"\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+\.\d{2}")

DEPOSIT_KEYWORDS = ["DEP", "DEPOSITO", "DEPOS", "ABONO", "INGRESO"]
WITHDRAW_KEYWORDS = ["ENVIO", "ENVIO", "ENVI", "TRANSFER", "TRASP", "RETIRO", "COMPRA", "PAGO", "CHEQUE", "CHEQUES", "NOMINA", "NOMIN"]


def _normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    cleaned = text.replace("¢", "O")
    cleaned = re.sub(r"\s+", " ", cleaned.upper()).strip()
    return cleaned


def _contains_any(text: str, keywords: List[str]) -> bool:
    norm = _normalize_text(text)
    return any(keyword in norm for keyword in keywords)


def _is_comision(texto: str) -> bool:
    norm = _normalize_text(texto)
    tokens = [
        "COMISION ADMINISTRACION",
        "IVA COMISION",
        "C O MISION ADMINISTRACION",
        "C O MISION CHEQUES",
        "I V A COMISION CHEQUES",
        "COMISION CHEQUES",
    ]
    return any(token in norm for token in tokens)


def _is_nomina(texto: str) -> bool:
    norm = _normalize_text(texto)
    tokens = [
        "DEPOSITO DE NOMINA",
        "DEPOSITO DE NOMINA",
        "SITO DE N",
        "NOMINA",
    ]
    return any(token in norm for token in tokens)


def _clean_amount(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"[^0-9\.\-]", "", text)


def _parse_amount_to_float(text: Optional[str]) -> Optional[float]:
    cleaned = _clean_amount(text)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except Exception:
        return None


def _extract_year(pdf: pdfplumber.PDF) -> str:
    text = pdf.pages[0].extract_text() or ""
    for line in text.splitlines():
        if line.strip().upper().startswith("PERIODO:"):
            match = re.search(r"\b(\d{4})\b", line)
            if match:
                return match.group(1)
    return ""


def extraer_movimientos(pdf_path: str) -> pd.DataFrame:
    movimientos = []

    with pdfplumber.open(pdf_path) as pdf:
        anio = _extract_year(pdf)
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            lines = page_text.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].rstrip()
                if not line.strip():
                    i += 1
                    continue

                tokens = line.split()
                if len(tokens) >= 2 and FECHA_RE.match(" ".join(tokens[:2])):
                    prefix = f"{tokens[0]} {tokens[1]}"
                    rest_idx = line.find(prefix) + len(prefix)
                    rest = line[rest_idx:].lstrip()

                    next_token = tokens[2] if len(tokens) > 2 else ""
                    if next_token.isdigit() and rest.startswith(next_token):
                        rest = rest[len(next_token):].lstrip()

                    matches = [m.replace("$", "").strip() for m in AMOUNT_RE.findall(rest)]
                    first_amount_match = AMOUNT_RE.search(rest)
                    descripcion = rest[: first_amount_match.start()].strip() if first_amount_match else rest.strip()

                    deposito_str = retiro_str = saldo_str = ""
                    if len(matches) >= 3:
                        deposito_str, retiro_str, saldo_str = matches[-3:]
                    elif len(matches) == 2:
                        first, second = matches
                        if _contains_any(descripcion, DEPOSIT_KEYWORDS):
                            deposito_str, saldo_str = first, second
                        else:
                            retiro_str, saldo_str = first, second
                    elif len(matches) == 1:
                        saldo_str = matches[0]

                    deposito_val = _parse_amount_to_float(deposito_str)
                    retiro_val = _parse_amount_to_float(retiro_str)
                    saldo_val = _parse_amount_to_float(saldo_str)

                    registro = {
                        "Fecha": None,
                        "Descripción": descripcion,
                        "Depósitos": deposito_val,
                        "Retiros": retiro_val,
                        "Saldo": saldo_val,
                        "Detalle": "",
                    }

                    dia = tokens[0].zfill(2)
                    mes_abrev = tokens[1].upper()
                    mes = MESES.get(mes_abrev, "01")
                    registro["Fecha"] = f"{dia}/{mes}/{anio}" if anio else f"{dia}/{mes}"

                    detalle_lines = []
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if not next_line:
                            j += 1
                            continue
                        next_tokens = next_line.split()
                        if len(next_tokens) >= 2 and FECHA_RE.match(" ".join(next_tokens[:2])):
                            break
                        detalle_lines.append(next_line)
                        j += 1

                    detalle_texto = " ".join(detalle_lines).strip()
                    if detalle_texto:
                        registro["Detalle"] = detalle_texto
                        match_benef = re.search(r"BENEFICIARIO:(.*?)\(", detalle_texto, flags=re.IGNORECASE)
                        if match_benef:
                            registro["Descripción"] = match_benef.group(1).strip()
                        else:
                            match_ord = re.search(r"ORDENANTE:(.*?)CUENTA ORDENANTE:", detalle_texto, flags=re.IGNORECASE)
                            if match_ord:
                                registro["Descripción"] = match_ord.group(1).strip()
                        if _is_comision(detalle_texto):
                            registro["Descripción"] = "COMISION"
                        if _is_nomina(detalle_texto):
                            registro["Descripción"] = "NOMINA"

                    if _is_comision(registro["Descripción"]):
                        registro["Descripción"] = "COMISION"
                    if _is_nomina(registro["Descripción"]):
                        registro["Descripción"] = "NOMINA"

                    movimientos.append(registro)
                    i = j
                else:
                    i += 1

    df = pd.DataFrame(movimientos, columns=["Fecha", "Descripción", "Depósitos", "Retiros", "Saldo", "Detalle"])
    for col in ["Depósitos", "Retiros", "Saldo"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
