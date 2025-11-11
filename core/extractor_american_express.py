"""Extractor de estados de cuenta American Express."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import pandas as pd
import pdfplumber

AMOUNT_RX = re.compile(r"\(?-?\d{1,3}(?:,\d{3})*(?:\.\d{2})\)?")
YEAR_RX = re.compile(r"\b(20\d{2})\b")
REF_RX = re.compile(r"\b\d{6,}\b")
DATE_PATTERNS = [
    re.compile(r"^(?P<dia>\d{1,2})/(?P<mes>\d{1,2})/(?P<anio>\d{2,4})"),
    re.compile(r"^(?P<dia>\d{1,2})-(?P<mes>\d{1,2})-(?P<anio>\d{2,4})"),
    re.compile(r"^(?P<dia>\d{1,2})\s+(?P<mes_txt>[A-Z]{3})\s*(?P<anio>\d{2,4})?", re.IGNORECASE),
    re.compile(r"^(?P<mes_txt>[A-Z]{3})\.?\s+(?P<dia>\d{1,2}),?\s*(?P<anio>\d{2,4})?", re.IGNORECASE),
]

MONTHS = {
    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12,
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

ABONO_KEYWORDS = (
    "ABONO",
    "DEPOSITO",
    "PAYMENT",
    "PAGO",
    "CREDIT",
    "DEVOLUCION",
    "REVERSO",
    "ADJUSTMENT",
)
CARGO_KEYWORDS = (
    "CARGO",
    "CHARGE",
    "PURCHASE",
    "COMPRA",
    "INTERES",
    "INTEREST",
    "FEE",
    "COMISION",
    "SPEI ENVIADO",
)

HEADER_TOKENS = ("FECHA", "DATE", "DESCRIPCION", "DESCRIPTION", "DETALLE")
FOOTER_PREFIXES = (
    "PAGINA",
    "PAGINA:",
    "AMERICAN EXPRESS",
    "CONSULTAS",
    "RECLAMACION",
    "RECLAMACION",
    "CONTACTO",
    "ATENCION",
    "UNE",
    "LLAMANOS",
    "CALL",
)


def _norm_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _clean_amount(value: str) -> float:
    val = value.strip()
    neg = val.startswith("(") and val.endswith(")")
    val = val.strip("()")
    val = val.replace("$", "").replace(",", "")
    val = re.sub(r"\b(?:MXN|USD|US|MN)\b", "", val)
    if not val:
        return 0.0
    number = float(val)
    return -number if neg else number


def _match_date(line: str):
    for pattern in DATE_PATTERNS:
        match = pattern.match(line)
        if match:
            return match
    return None


def _format_date(match, year_hint: Optional[int]) -> str:
    info = match.groupdict()
    dia = info.get("dia")
    mes = info.get("mes")
    mes_txt = info.get("mes_txt")
    anio = info.get("anio")

    if mes_txt and not mes:
        mes = str(MONTHS.get(mes_txt.upper(), 1)).zfill(2)
    elif mes:
        mes = mes.zfill(2)
    else:
        mes = "01"

    if dia:
        dia = dia.zfill(2)
    else:
        dia = "01"

    if anio:
        anio = anio.zfill(4) if len(anio) == 4 else f"20{anio[-2:]}"
    elif year_hint:
        anio = f"{year_hint:04d}"
    else:
        anio = "0000"

    return f"{anio}-{mes}-{dia}"


def _strip_amounts(text: str) -> str:
    return _norm_spaces(AMOUNT_RX.sub(" ", text))


def _extract_reference(text: str) -> str:
    match = REF_RX.search(text)
    return match.group(0) if match else ""


def _classify_by_keywords(text: str, amount: float) -> tuple[float, float]:
    upper = text.upper()
    if any(token in upper for token in ABONO_KEYWORDS):
        return 0.0, amount
    if any(token in upper for token in CARGO_KEYWORDS):
        return amount, 0.0
    if amount < 0:
        return abs(amount), 0.0
    return 0.0, amount


def _finalize_entry(entry: Dict[str, str], prev_saldo: Optional[float]) -> Optional[Dict[str, float]]:
    text = entry.get("text", "")
    if not text:
        return None

    amounts = AMOUNT_RX.findall(text)
    cargo = 0.0
    abono = 0.0
    saldo = prev_saldo if prev_saldo is not None else 0.0

    if amounts:
        saldo = _clean_amount(amounts[-1])
        if len(amounts) >= 3:
            cargo = abs(_clean_amount(amounts[-3]))
            abono = abs(_clean_amount(amounts[-2]))
        elif len(amounts) == 2:
            movimiento = abs(_clean_amount(amounts[0]))
            if prev_saldo is not None:
                if saldo >= prev_saldo:
                    delta = saldo - prev_saldo
                    abono = abs(delta) if delta else movimiento
                else:
                    delta = prev_saldo - saldo
                    cargo = abs(delta) if delta else movimiento
            else:
                cargo, abono = _classify_by_keywords(text, movimiento)
        elif len(amounts) == 1 and entry.get("is_balance") and prev_saldo is None:
            saldo = abs(_clean_amount(amounts[0]))

    concepto = _strip_amounts(text)
    referencia = _extract_reference(concepto)
    if referencia:
        concepto = _norm_spaces(concepto.replace(referencia, ""))

    if not concepto:
        concepto = "MOVIMIENTO"

    return {
        "Fecha": entry["fecha"],
        "Referencia": referencia,
        "Concepto": concepto,
        "Cargo": cargo,
        "Abono": abono,
        "Saldo": saldo,
    }


def extraer_american_express(pdf_file) -> pd.DataFrame:
    movimientos: List[Dict[str, object]] = []
    pending: Optional[Dict[str, str]] = None
    prev_saldo: Optional[float] = None
    year_hint: Optional[int] = None

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.splitlines():
                line = _norm_spaces(raw_line)
                if not line:
                    continue

                upper = line.upper()
                if any(token in upper for token in HEADER_TOKENS):
                    continue

                if year_hint is None:
                    match_year = YEAR_RX.search(line)
                    if match_year:
                        year_hint = int(match_year.group(1))

                match = _match_date(line)
                if match:
                    if pending:
                        row = _finalize_entry(pending, prev_saldo)
                        if row:
                            movimientos.append(row)
                            prev_saldo = row["Saldo"]
                    fecha = _format_date(match, year_hint)
                    rest = _norm_spaces(line[match.end():])
                    pending = {
                        "fecha": fecha,
                        "text": rest,
                        "is_balance": "SALDO" in rest.upper() or "BALANCE" in rest.upper(),
                    }
                elif pending:
                    if any(upper.startswith(prefix) for prefix in FOOTER_PREFIXES):
                        continue
                    pending["text"] = _norm_spaces(f"{pending['text']} {line}")
                    if "SALDO" in upper or "BALANCE" in upper:
                        pending["is_balance"] = True
                else:
                    continue

                if pending:
                    amount_count = len(AMOUNT_RX.findall(pending["text"]))
                    should_finalize = amount_count >= 2 or (pending.get("is_balance") and amount_count >= 1)
                    if should_finalize:
                        row = _finalize_entry(pending, prev_saldo)
                        if row:
                            movimientos.append(row)
                            prev_saldo = row["Saldo"]
                        pending = None

    if pending:
        row = _finalize_entry(pending, prev_saldo)
        if row:
            movimientos.append(row)

    df = pd.DataFrame(movimientos, columns=["Fecha", "Referencia", "Concepto", "Cargo", "Abono", "Saldo"])
    if df.empty:
        return df
    df["Cargo"] = pd.to_numeric(df["Cargo"], errors="coerce").fillna(0.0)
    df["Abono"] = pd.to_numeric(df["Abono"], errors="coerce").fillna(0.0)
    df["Saldo"] = pd.to_numeric(df["Saldo"], errors="coerce")
    df["Concepto"] = df["Concepto"].str.replace(r"\s+", " ", regex=True).str.strip()
    return df
