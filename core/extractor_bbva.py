from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import pdfplumber
from dateutil import parser as dateparser

EXTRA_JOINER = "\n"
COLUMNS = [
    "Fecha_Operación",
    "Fecha_Liquidación",
    "Código",
    "Concepto",
    "Cuenta",
    "Cargos",
    "Abonos",
    "Descripción",
]
DEBUG = False


def _dbg(*args):
    if DEBUG:
        print(*args)


def _strip_accents_upper(value: Any) -> str:
    value = "" if value is None else str(value)
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return value.upper().strip()


def _clean_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_for_match(value: Any) -> str:
    up = _strip_accents_upper(value)
    up = re.sub(r"[^\w\s]", " ", up)
    up = re.sub(r"\s+", " ", up).strip()
    return up


_AMOUNT_RE = re.compile(r"^\s*\(?-?\$?\s*(?:\d{1,3}(?:[.,]\d{3})+|\d+)[.,]\d{2}\s*\)?\s*$")


def _is_amount(text: Any) -> bool:
    t = _clean_text(text).replace(" ", "")
    return bool(t) and bool(_AMOUNT_RE.match(t))


def _to_float(text: Optional[str]) -> Optional[float]:
    if text is None or _clean_text(text) == "":
        return None
    t = _clean_text(text)
    neg = "(" in t and ")" in t
    t = t.replace("$", "").replace(" ", "").replace("(", "").replace(")", "")
    last_dot, last_comma = t.rfind("."), t.rfind(",")
    if last_dot > last_comma:
        t = t.replace(",", "")
    elif last_comma > last_dot:
        t = t.replace(".", "").replace(",", ".")
    try:
        val = float(t)
        return -val if neg else val
    except Exception:
        return None


DATE_TOKEN = r"(\d{1,2}\s*[\/\-]\s*(?:[A-Z]{3}|\d{1,2})(?:[\/\-]\d{2,4})?)"


def _split_compound_dates(cell_text: str) -> Tuple[Optional[str], Optional[str], str]:
    s = _clean_text(cell_text)
    pos = 0
    f1 = f2 = None
    m1 = re.match(r"^\s*" + DATE_TOKEN, s, flags=re.IGNORECASE)
    if m1:
        f1 = m1.group(1)
        pos = m1.end()
        m2 = re.match(r"^\s*" + DATE_TOKEN, s[pos:], flags=re.IGNORECASE)
        if m2:
            f2 = m2.group(1)
            pos += m2.end()
    rest = s[pos:].lstrip()
    return f1, f2, rest


def _parse_date_token(token: Optional[str], year_hint: Optional[int]) -> Optional[str]:
    if not token:
        return None
    t = token.strip().upper()
    if not re.search(r"\d{4}", t or "") and year_hint:
        if re.match(r"^\d{1,2}\s*[\/\-]\s*[A-Z]{3}$", t) or re.match(r"^\d{1,2}\s*[\/\-]\s*\d{1,2}$", t):
            t = f"{t}/{year_hint}"
    try:
        dt = dateparser.parse(t, dayfirst=True, fuzzy=True)
        return dt.date().isoformat() if dt else None
    except Exception:
        return None


def _detect_columns_x(page, prev_meta: Optional[Dict[str, float]] = None) -> Dict[str, Optional[float]]:
    cargo_x = abono_x = None
    try:
        words = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=2, use_text_flow=False) or []
        for word in words:
            text = _strip_accents_upper(word.get("text", ""))
            if text == "CARGOS":
                cargo_x = (word["x0"] + word["x1"]) / 2.0
            elif text == "ABONOS":
                abono_x = (word["x0"] + word["x1"]) / 2.0
    except Exception:
        pass
    if cargo_x is None and prev_meta:
        cargo_x = prev_meta.get("cargo_x")
    if abono_x is None and prev_meta:
        abono_x = prev_meta.get("abono_x")
    return {"cargo_x": cargo_x, "abono_x": abono_x, "tol": 60.0}


def _find_table_top_y(words: List[Dict[str, Any]]) -> float:
    header_tokens = {
        "FECHA",
        "OPER",
        "LIQ",
        "COD.",
        "DESCRIPCIÓN",
        "DESCRIPCION",
        "REFERENCIA",
        "CARGOS",
        "ABONOS",
        "SALDO",
        "OPERACIÓN",
        "OPERACION",
        "LIQUIDACIÓN",
        "LIQUIDACION",
        "DETALLE",
        "MOVIMIENTOS",
        "REALIZADOS",
    }
    header_bottoms = [w.get("bottom", 0.0) for w in words if _strip_accents_upper(w.get("text", "")) in header_tokens]
    date_tops: List[float] = []
    for word in words:
        txt = _clean_text(word.get("text", "")).upper()
        if re.match(r"^\d{1,2}[\/\-](?:[A-Z]{3}|\d{1,2})(?:[\/\-]\d{2,4})?$", txt):
            date_tops.append(word.get("top", 0.0))
    if header_bottoms:
        base = max(header_bottoms) + 6
        if date_tops:
            base = min(base, min(date_tops) - 4)
        return base
    return (min(date_tops) - 4) if date_tops else 0.0


def _words_to_rows(page, prev_meta: Optional[Dict[str, float]], gap_x: float = 22.0, row_tol: float = 3.0) -> List[Dict[str, Any]]:
    meta = _detect_columns_x(page, prev_meta=prev_meta)
    try:
        words = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=2, use_text_flow=False) or []
    except Exception:
        words = []
    if not words:
        return []
    table_top_y = _find_table_top_y(words)
    content = [w for w in words if w.get("top", 0.0) >= table_top_y]
    if not content:
        return []
    content.sort(key=lambda w: (round(w.get("top", 0.0), 1), w.get("x0", 0.0)))

    rows: List[Dict[str, Any]] = []
    current_y: Optional[float] = None
    current_words: List[Dict[str, Any]] = []

    def flush_row():
        nonlocal current_words
        if not current_words:
            return
        current_words.sort(key=lambda w: w.get("x0", 0.0))
        cells: List[str] = []
        buf = ""
        prev_x1: Optional[float] = None
        amount_texts: List[str] = []
        amount_centers: List[float] = []
        for w in current_words:
            wt = _clean_text(w.get("text", ""))
            if _is_amount(wt):
                amount_texts.append(wt)
                amount_centers.append((w.get("x0", 0.0) + w.get("x1", 0.0)) / 2.0)
            if prev_x1 is None:
                buf = wt
            else:
                gap = w.get("x0", 0.0) - prev_x1
                if gap > gap_x:
                    cells.append(_clean_text(buf))
                    buf = wt
                else:
                    buf += " " + wt
            prev_x1 = w.get("x1", 0.0)
        if buf:
            cells.append(_clean_text(buf))

        joined = _strip_accents_upper(" ".join(cells))
        if any(
            token in joined
            for token in [
                "PAGINA",
                "TOTAL DE MOVIMIENTOS",
                "TOTAL IMPORTE CARGOS",
                "TOTAL IMPORTE ABONOS",
                "CUADRO RESUMEN",
                "GRAFICO",
            ]
        ):
            current_words = []
            return

        if any(c.strip() for c in cells):
            rows.append(
                {
                    "cells": cells,
                    "amount_texts": amount_texts,
                    "amount_centers": amount_centers,
                    "meta": meta,
                }
            )
        current_words = []

    for word in content:
        if current_y is None:
            current_y = word.get("top", 0.0)
            current_words = [word]
            continue
        if abs(word.get("top", 0.0) - current_y) <= row_tol:
            current_words.append(word)
        else:
            flush_row()
            current_y = word.get("top", 0.0)
            current_words = [word]
    flush_row()
    return rows


def _extract_rows_by_lines(page, prev_meta: Optional[Dict[str, float]]) -> List[Dict[str, Any]]:
    meta = _detect_columns_x(page, prev_meta=prev_meta)
    rows: List[Dict[str, Any]] = []
    try:
        tables = page.extract_tables(
            {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "intersection_tolerance": 5,
                "snap_tolerance": 3,
                "min_words_vertical": 1,
                "min_words_horizontal": 1,
                "keep_blank_chars": False,
                "text_tolerance": 2,
            }
        )
    except Exception:
        tables = None
    if not tables:
        return rows
    table = max(tables, key=lambda t: len(t) if t else 0)
    for raw in table or []:
        if not raw:
            continue
        cells = [(_clean_text(c) if c is not None else "") for c in raw]
        if not any(c.strip() for c in cells):
            continue
        amount_texts = [c for c in cells if _is_amount(c)]
        rows.append({"cells": cells, "amount_texts": amount_texts, "amount_centers": [], "meta": meta})
    return rows


def _extract_rows_from_page(page, prev_meta: Optional[Dict[str, float]]):
    rows = _words_to_rows(page, prev_meta=prev_meta)
    if rows:
        return rows, rows[0].get("meta", prev_meta or {"cargo_x": None, "abono_x": None, "tol": 60.0})
    fallback = _extract_rows_by_lines(page, prev_meta=prev_meta)
    return fallback, (fallback[0].get("meta") if fallback else (prev_meta or {"cargo_x": None, "abono_x": None, "tol": 60.0}))


def _row_is_header_like(cells: List[str]) -> bool:
    header_join = _strip_accents_upper(" ".join(cells))
    return any(
        key in header_join for key in ["FECHA", "COD", "DESCRIPCION", "REFERENCIA", "CARGOS", "ABONOS", "SALDO", "OPERACION", "LIQUIDACION"]
    )


def _split_text_and_amounts(cells: List[str]) -> Tuple[str, List[str]]:
    text = " ".join(_clean_text(c) for c in cells if not _is_amount(c)).strip()
    amounts = [c for c in cells if _is_amount(c)]
    return text, amounts


def _group_rows_with_continuations(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    combined: List[Dict[str, Any]] = []
    base_text: Optional[str] = None
    base_amount_texts: List[str] = []
    base_amount_centers: List[float] = []
    base_meta: Dict[str, Any] = {}

    def flush():
        nonlocal base_text, base_amount_texts, base_amount_centers, base_meta
        if base_text is None:
            return
        combined.append(
            {
                "text": base_text,
                "amount_texts": base_amount_texts,
                "amount_centers": base_amount_centers,
                "meta": base_meta,
            }
        )
        base_text, base_amount_texts, base_amount_centers, base_meta = None, [], [], {}

    for row in rows:
        cells = row.get("cells", [])
        if _row_is_header_like(cells):
            continue
        row_text, _ = _split_text_and_amounts(cells)
        if row.get("amount_texts"):
            flush()
            base_text = row_text
            base_amount_texts = row.get("amount_texts", [])
            base_amount_centers = row.get("amount_centers", [])
            base_meta = row.get("meta", {})
        else:
            if base_text is not None and row_text:
                base_text = f"{base_text}{EXTRA_JOINER}{row_text}"
    flush()
    return combined


ABONO_CODES = {"T20", "T22", "N17"}
CARGO_CODES = {"T17", "N02", "P14", "S39", "S40", "X01", "G00", "G30", "P31"}


def _classify_by_code_or_text(codigo: Optional[str], descripcion: str, concepto: Optional[str] = None) -> Optional[str]:
    up = _strip_accents_upper(descripcion)
    norm = _normalize_for_match(descripcion)
    code = (codigo or "").upper().strip()

    if code in ABONO_CODES:
        return "abono"
    if code in CARGO_CODES:
        return "cargo"
    if concepto and _strip_accents_upper(concepto) == "INTERESES":
        return "abono"
    if "INTERESES GANADOS" in up or "INT GANADOS" in norm:
        return "abono"
    if any(token in up for token in ["RECIBID", "DEVUELT", "DEVOLUCION"]):
        return "abono"
    if any(token in up for token in ["ENVIADO", "PAGO", "SERV", "TELCEL", "IMSS", "SAT", "SEGUROS", "COBRO"]):
        return "cargo"
    return None


def _compute_concepto(block_no_dates: str, lineas: List[str]) -> Optional[str]:
    up = _strip_accents_upper(block_no_dates)
    norm = _normalize_for_match(block_no_dates)

    if any(token in up for token in ["IVA PENALIZ", "PENALIZ", "IVA COM", "SERV BANCA"]):
        return "Comisión"
    if "SAT" in up or "IMPUEST" in up:
        return "Impuestos SAT"
    if "DEVUELT" in up or "DEPOSITO ERR" in up:
        return "Pago devuelto"
    if "DISP T NEGOCIOS" in norm or "PAGO TARJETA DE CREDITO" in up or "PAGO TARJETA CREDITO" in up:
        return "Entre Cuentas"
    if any(token in up for token in ["IMSS", "INFONAVIT", "SIPARE"]):
        return "IMSS"
    if "PAGO DE NOMINA" in up or "PAGO NOMINA" in up:
        return "Pago Nomina"
    if "PASE" in up:
        return "Pase Servicios Electrónicos"
    if "AXA" in up:
        return "AXA Seguros"
    if "INTERESES GANADOS" in up:
        return "Intereses"
    if "I.S.R. RETENIDO" in up or "ISR RETENIDO" in up or "I S R RETENIDO" in norm:
        return "ISR Retenido por Intereses"
    if "PREST." in up:
        return "Préstamo"
    if "TELCEL" in up:
        return "Radio Móvil Dipsa"
    if "BANCO FINTERRA" in up:
        return "Crédito Covalto"
    if "RECIBO NO." in up or "RECIBO NO " in up or "RECIBO NO" in up:
        return "BBVA Seguros México"
    if len(lineas) >= 5:
        return lineas[4] or None
    return None


def _extract_credit_account(desc: str) -> Optional[str]:
    if not desc:
        return None
    best = None
    best_len = 0
    patterns = [
        r"(?:CUENTA|CTA)\s*[:#\-]?\s*([0-9A-Za-z\-\s]{4,})",
        r"(?:TARJETA(?:\s+DE\s+CR[EI]DITO)?)\s*[:#\-]?\s*([0-9A-Za-z\-\s]{4,})",
    ]
    for pat in patterns:
        for match in re.finditer(pat, desc, flags=re.IGNORECASE):
            raw = match.group(1).strip()
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 4 and len(digits) > best_len:
                best = digits
                best_len = len(digits)
    return best


def _extract_bnet_account(desc: str) -> Optional[str]:
    if not desc:
        return None
    candidates: List[str] = []
    for match in re.finditer(r"\bBNET[\s:]*([A-Za-z0-9\-]+)", desc, flags=re.IGNORECASE):
        candidates.append(match.group(1))
    return max(candidates, key=len) if candidates else None


def _extract_prestamo_number(desc: str) -> Optional[str]:
    if not desc:
        return None
    match = re.search(r"\bPREST\.?\s*([0-9][0-9\-\s]{2,})", desc, flags=re.IGNORECASE)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return digits if len(digits) >= 3 else None


def _extract_generic_account(desc: str) -> Optional[str]:
    """Detecta cuentas largas (p. ej. CLABE) aun si no vienen precedidas de etiquetas."""
    if not desc:
        return None
    matches = re.findall(r"\b\d{6,}\b", desc)
    if not matches:
        spaced = re.findall(r"(?:\d[\s\-]?){6,}", desc)
        for raw in spaced:
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 6:
                matches.append(digits)
    if not matches:
        return None
    return max(matches, key=len)


def _row_to_record(row: Dict[str, Any], year_hint: Optional[int]) -> Optional[Dict[str, Any]]:
    texto_total = _clean_text(row.get("text", ""))
    amounts_texts = row.get("amount_texts", []) or []
    amounts_centers = row.get("amount_centers", []) or []
    meta = row.get("meta", {}) or {}

    if not amounts_texts:
        return None

    amounts_core = amounts_texts[:]
    centers_core = amounts_centers[:]
    if len(amounts_texts) >= 3:
        amounts_core = amounts_texts[:-2]
        centers_core = amounts_centers[:-2] if amounts_centers else []

    f1, f2, rest = _split_compound_dates(texto_total)
    fecha_op = _parse_date_token(f1, year_hint)
    fecha_liq = _parse_date_token(f2, year_hint)
    block_no_dates = rest if (f1 or f2) else texto_total

    lineas = [ln.strip() for ln in block_no_dates.split(EXTRA_JOINER)]
    concepto: Optional[str] = _compute_concepto(block_no_dates, lineas)

    codigo = None
    txt = block_no_dates
    if lineas:
        first = lineas[0]
        mcode = re.match(r"^\s*([A-Z]\d{2})\s+(.*)$", first or "")
        if mcode:
            codigo = mcode.group(1).upper()
            lineas[0] = mcode.group(2)
            txt = EXTRA_JOINER.join(lineas)

    descripcion = txt

    up_block = _strip_accents_upper(block_no_dates)
    if "PREST." in up_block:
        cuenta = _extract_prestamo_number(descripcion) or _extract_bnet_account(descripcion)
    elif "PAGO TARJETA DE CREDITO" in up_block or "PAGO TARJETA CREDITO" in up_block:
        cuenta = _extract_credit_account(descripcion) or _extract_bnet_account(descripcion)
    else:
        cuenta = _extract_bnet_account(descripcion)
    if not cuenta:
        cuenta = _extract_generic_account(descripcion)

    cargos = abonos = None
    if amounts_core:
        if len(amounts_core) == 1:
            val = _to_float(amounts_core[0])
            decided = None
            cx = meta.get("cargo_x")
            ax = meta.get("abono_x")
            if val is not None and centers_core:
                ac = centers_core[0]
                if cx is not None and ax is not None:
                    decided = "abono" if abs(ac - ax) <= abs(ac - cx) else "cargo"
            if decided is None:
                decided = _classify_by_code_or_text(codigo, descripcion, concepto)
            if decided is None and any(
                token in _strip_accents_upper(descripcion) for token in ["RECIBID", "DEVUELT", "DEVOLUCION", "INTERESES GANADOS"]
            ):
                decided = "abono"
            if decided == "abono":
                cargos, abonos = 0.0, (val or 0.0)
            else:
                cargos, abonos = (val or 0.0), 0.0
        else:
            v1 = _to_float(amounts_core[0])
            v2 = _to_float(amounts_core[1]) if len(amounts_core) > 1 else None
            cargos = v1 if v1 is not None else 0.0
            abonos = v2 if v2 is not None else 0.0

    record = {
        "Fecha_Operación": fecha_op,
        "Fecha_Liquidación": fecha_liq,
        "Código": codigo,
        "Concepto": concepto,
        "Cuenta": cuenta,
        "Cargos": cargos,
        "Abonos": abonos,
        "Descripción": descripcion,
    }
    if not any(
        [
            record["Descripción"],
            (record["Cargos"] is not None and record["Cargos"] != 0),
            (record["Abonos"] is not None and record["Abonos"] != 0),
        ]
    ):
        return None
    return record


def _post_clean(df: pd.DataFrame) -> pd.DataFrame:
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None

    extra_cols = [c for c in df.columns if c not in COLUMNS and c != "_order"]
    if extra_cols:
        df = df.drop(columns=extra_cols)

    if "_order" in df.columns:
        df = df.sort_values("_order").drop(columns=["_order"])

    for col in ["Cargos", "Abonos"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "Fecha_Operación" in df.columns:
        idx = df["Fecha_Operación"].first_valid_index()
        if idx is not None:
            df = df.loc[idx:]

    df = df[
        ~(
            df["Fecha_Operación"].isna()
            & (df["Cargos"].fillna(0) == 0)
            & (df["Abonos"].fillna(0) == 0)
        )
    ]

    df["Cargos"] = df["Cargos"].fillna(0.0)
    df["Abonos"] = df["Abonos"].fillna(0.0)
    for col in ["Código", "Concepto", "Cuenta", "Descripción"]:
        df[col] = df[col].fillna("").astype(str).map(str.strip)

    df = df[COLUMNS].reset_index(drop=True)
    return df


def _as_filelike(pdf_input: Union[str, bytes, io.BytesIO, Any]) -> io.BytesIO:
    if isinstance(pdf_input, io.BytesIO):
        return pdf_input
    if isinstance(pdf_input, bytes):
        return io.BytesIO(pdf_input)
    if isinstance(pdf_input, str):
        return None
    if hasattr(pdf_input, "read"):
        return io.BytesIO(pdf_input.read())
    raise TypeError("Tipo de entrada no soportado para el PDF.")


def _detect_period_year(pdf: pdfplumber.PDF) -> Optional[int]:
    year = None
    for page in pdf.pages[:3]:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        match = re.search(
            r"(?:Periodo\s+DEL.*?(\d{4}))|(?:Fecha\s+de\s+Corte\s+.*?(\d{4}))",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            for group in match.groups():
                if group and group.isdigit():
                    year = int(group)
                    break
        if year:
            break
    return year


def extract_bbva_pdf_to_df(pdf_input: Union[str, bytes, io.BytesIO, Any]) -> pd.DataFrame:
    filelike = _as_filelike(pdf_input)
    try:
        if filelike is None and isinstance(pdf_input, str):
            pdf_obj = pdfplumber.open(pdf_input)
        else:
            pdf_obj = pdfplumber.open(filelike)
    except Exception as exc:
        raise RuntimeError(f"No se pudo abrir el PDF: {exc}")

    records: List[Dict[str, Any]] = []
    with pdf_obj as pdf:
        year_hint = _detect_period_year(pdf) or datetime.now().year
        order = 0
        last_meta: Optional[Dict[str, float]] = None
        for page in pdf.pages:
            try:
                rows, last_meta = _extract_rows_from_page(page, prev_meta=last_meta)
            except Exception as exc:
                _dbg("Error en extracción de página:", exc)
                rows = []
            if not rows:
                continue
            grouped_rows = _group_rows_with_continuations(rows)
            for row in grouped_rows:
                rec = _row_to_record(row, year_hint=year_hint)
                if rec:
                    rec["_order"] = order
                    order += 1
                    records.append(rec)
    df = pd.DataFrame.from_records(records) if records else pd.DataFrame(columns=COLUMNS)
    return _post_clean(df)
