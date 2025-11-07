from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, MutableMapping, Optional, Sequence

import pandas as pd

from .config import VERIFIED_ROUTES_XLSX
from .utils import normalize_name
from .maps import GoogleMapsClient, GoogleMapsError, haversine_km

def _load_routes_from_excel(path: Path) -> dict[str, list[str]]:
    """Read verified routes from the supplemental Excel workbook."""
    routes: dict[str, list[str]] = {}
    if not path.exists():
        return routes

    try:
        workbook = pd.ExcelFile(path)
    except Exception:
        return routes

    for sheet_name in workbook.sheet_names:
        try:
            df = pd.read_excel(workbook, sheet_name=sheet_name)
        except Exception:
            continue

        normalized_columns = {col: str(col).strip().upper() for col in df.columns}
        df = df.rename(columns=normalized_columns)
        if "CASETA" not in df.columns:
            continue

        plazas: list[str] = []
        for value in df["CASETA"].tolist():
            if isinstance(value, str):
                plaza = value.strip()
            elif pd.notna(value):
                plaza = str(value).strip()
            else:
                plaza = ""
            if plaza:
                plazas.append(plaza)

        if not plazas:
            continue

        route_name = " ".join(str(sheet_name).split()).upper()
        if route_name:
            routes[route_name] = plazas

    return routes


def load_routes() -> dict[str, list[str]]:
    """Lee únicamente las rutas verificadas del Excel."""
    routes = _load_routes_from_excel(Path(VERIFIED_ROUTES_XLSX))
    if not routes:
        routes = {
            "TOLUCA-NUEVO LAREDO": [
                "EL DORADO","ATLACOMULCO SUR","CHICHIMEQUILLAS",
                "LIB. OTE. S.L.P.","LIB. MATEHUALA","LOS CHORROS","LINCOLN","SABINAS","NVO LAREDO KM26",
            ],
            "NVO LAREDO-PANINDICUARO": [
                "NVO LAREDO PINFRA","SABINAS","LINCOLN","LOS CHORROS","LIB. MATEHUALA",
                "VENTURA - EL PEYOTE","LIB. OTE. S.L.P.","SAN FELIPE","MENDOZA","LA CINTA","PANINDICUARO",
            ]
        }
    return routes

def plazas_catalog(routes: dict[str, list[str]]) -> list[str]:
    return sorted({p for lista in routes.values() for p in lista})

def find_subsequence_between(routes: dict[str, list[str]], a: str, b: str):
    a_norm, b_norm = normalize_name(a), normalize_name(b)
    best = None
    for name, seq in routes.items():
        norm = [normalize_name(x) for x in seq]
        if a_norm in norm and b_norm in norm:
            ia, ib = norm.index(a_norm), norm.index(b_norm)
            sub = seq[ia:ib+1] if ia <= ib else list(reversed(seq[ib:ia+1]))
            if (best is None) or (len(sub) < len(best[1])):
                best = (name, sub)
    return best


# Palabras clave adicionales para mapear búsquedas de Google a nuestras casetas
PLAZA_KEYWORDS = {
    "LIBRAMIENTO MATEHUALA": "LIB. MATEHUALA",
    "LIB OTE SLP": "LIB. OTE. S.L.P.",
    "LIB OTE SAN LUIS POTOSI": "LIB. OTE. S.L.P.",
    "NUEVO LAREDO PINFRA": "NVO LAREDO PINFRA",
    "NVO LAREDO PINFRA": "NVO LAREDO PINFRA",
    "NUEVO LAREDO KM26": "NVO LAREDO KM26",
    "VENTURA EL PEYOTE": "VENTURA - EL PEYOTE",
    "LOS CHORROS COAHUILA": "LOS CHORROS",
}


def match_plaza_in_text(text: str, plazas: Iterable[str]) -> Optional[str]:
    """Intenta detectar una caseta conocida dentro de un texto libre."""

    normalized_text = normalize_name(text)
    for plaza in plazas:
        if normalize_name(plaza) in normalized_text:
            return plaza

    for keyword, target in PLAZA_KEYWORDS.items():
        if keyword and normalize_name(keyword) in normalized_text:
            return target
    return None


def _combine_segments(segments: list[tuple[str, list[str]]]) -> Optional[tuple[str, list[str]]]:
    if not segments:
        return None

    route_labels: list[str] = []
    combined: list[str] = []
    for idx, (route_name, seq) in enumerate(segments):
        if not seq:
            continue
        if route_name not in route_labels:
            route_labels.append(route_name)
        if not combined:
            combined.extend(seq)
            continue
        if normalize_name(combined[-1]) == normalize_name(seq[0]):
            combined.extend(seq[1:])
        else:
            combined.extend(seq)

    if not combined:
        return None

    title = "  →  ".join(route_labels) if route_labels else ""
    return title or segments[0][0], combined


def plazas_from_polyline(
    routes: dict[str, list[str]],
    points: Sequence[tuple[float, float]],
    *,
    maps_client: Optional[GoogleMapsClient] = None,
    cache: Optional[MutableMapping[str, Any]] = None,
    session_token: Optional[str] = None,
    threshold_km: float = 15.0,
) -> Optional[tuple[str, list[str]]]:
    """Detecta la ruta más probable cruzando puntos intermedios con nuestras casetas."""

    if not points or maps_client is None:
        return None

    plaza_lookup = cache.setdefault("plaza_lookup", {}) if isinstance(cache, MutableMapping) else {}
    geometry_cache = cache.setdefault("plaza_geometry", {}) if isinstance(cache, MutableMapping) else {}
    autocomplete_cache = cache.setdefault("autocomplete", {}) if isinstance(cache, MutableMapping) else None
    details_cache = cache.setdefault("place_details", {}) if isinstance(cache, MutableMapping) else None

    def ensure_geometry(plaza: str) -> Optional[tuple[float, float]]:
        if plaza in geometry_cache:
            return geometry_cache[plaza]

        place_id = plaza_lookup.get(plaza)
        if not place_id:
            query = f"Caseta {plaza}" if "caseta" not in normalize_name(plaza) else plaza
            try:
                predictions = maps_client.autocomplete(
                    query,
                    session_token=session_token,
                    cache=autocomplete_cache,
                )
            except GoogleMapsError:
                predictions = []
            normalized_plaza = normalize_name(plaza)
            for pred in predictions:
                if normalize_name(pred.get("description", "")) and normalized_plaza in normalize_name(pred.get("description", "")):
                    place_id = pred.get("place_id")
                    break
            if not place_id and predictions:
                place_id = predictions[0].get("place_id")
            if place_id:
                plaza_lookup[plaza] = place_id

        if not place_id:
            return None

        try:
            details = maps_client.place_details(
                place_id,
                cache=details_cache,
                session_token=session_token,
            )
        except GoogleMapsError:
            return None

        location = details.get("result", {}).get("geometry", {}).get("location")
        if not location:
            return None
        coords = (float(location.get("lat")), float(location.get("lng")))
        geometry_cache[plaza] = coords
        return coords

    best_match: Optional[tuple[str, list[str], int]] = None

    for route_name, plazas in routes.items():
        if not plazas:
            continue
        nearby: list[str] = []
        for plaza in plazas:
            coords = ensure_geometry(plaza)
            if not coords:
                continue
            distance = min(haversine_km(coords, p) for p in points)
            if distance <= threshold_km:
                nearby.append(plaza)

        if not nearby:
            continue

        first, last = nearby[0], nearby[-1]
        candidate = find_subsequence_between(routes, first, last)
        sequence = candidate[1] if candidate else nearby
        score = len(sequence)
        if best_match is None or score > best_match[2]:
            best_match = (route_name, sequence, score)

    if best_match:
        return best_match[0], best_match[1]
    return None


def match_plazas_for_route(
    routes: dict[str, list[str]],
    selections: Sequence[dict[str, Any]],
    polyline_points: Sequence[tuple[float, float]],
    *,
    maps_client: Optional[GoogleMapsClient] = None,
    cache: Optional[MutableMapping[str, Any]] = None,
    session_token: Optional[str] = None,
) -> Optional[tuple[str, list[str]]]:
    """Determina la secuencia de casetas más probable para una ruta calculada."""

    matched = [sel.get("matched_plaza") for sel in selections if sel and sel.get("matched_plaza")]

    segments: list[tuple[str, list[str]]] = []
    if len(matched) >= 2:
        for start, end in zip(matched, matched[1:]):
            found = find_subsequence_between(routes, start, end)
            if not found:
                segments = []
                break
            segments.append(found)

    combined = _combine_segments(segments)
    if combined:
        return combined

    return plazas_from_polyline(
        routes,
        polyline_points,
        maps_client=maps_client,
        cache=cache,
        session_token=session_token,
    )


__all__ = [
    "load_routes",
    "plazas_catalog",
    "find_subsequence_between",
    "match_plaza_in_text",
    "plazas_from_polyline",
    "match_plazas_for_route",
]
