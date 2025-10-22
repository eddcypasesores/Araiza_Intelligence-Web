"""Utilities for working with the Google Maps Places and Directions APIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence, Tuple
import json
import math
import requests

from .config import GOOGLE_MAPS_API_KEY


class GoogleMapsError(RuntimeError):
    """Raised when the Google Maps API returns an error response."""


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


def _cache_get(cache: Optional[MutableMapping[str, Any]], key: str) -> Any:
    if cache is None:
        return None
    return cache.get(key)


def _cache_set(cache: Optional[MutableMapping[str, Any]], key: str, value: Any) -> None:
    if cache is None:
        return
    cache[key] = value


def _make_cache_key(endpoint: str, params: Dict[str, Any]) -> str:
    frozen = _freeze(params)
    return f"{endpoint}:{json.dumps(frozen, ensure_ascii=False)}"


def decode_polyline(polyline: str | None) -> List[Tuple[float, float]]:
    """Decodes a Google encoded polyline into a list of (lat, lng) tuples."""

    if not polyline:
        return []

    coordinates: List[Tuple[float, float]] = []
    index = lat = lng = 0

    while index < len(polyline):
        result = shift = 0
        while True:
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        delta_lat = ~(result >> 1) if result & 1 else (result >> 1)
        lat += delta_lat

        result = shift = 0
        while True:
            b = ord(polyline[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        delta_lng = ~(result >> 1) if result & 1 else (result >> 1)
        lng += delta_lng

        coordinates.append((lat / 1e5, lng / 1e5))

    return coordinates


def haversine_km(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Returns the distance in kilometres between two lat/lng pairs."""

    lat1, lon1 = p1
    lat2, lon2 = p2

    r = 6371.0  # earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


@dataclass
class RouteSummary:
    distance_m: float
    duration_s: float
    polyline: str | None
    polyline_points: List[Tuple[float, float]]
    legs: List[Dict[str, Any]]
    summary: str | None
    warnings: List[str]
    fare: Optional[Dict[str, Any]]
    raw: Dict[str, Any]


class GoogleMapsClient:
    base_url = "https://maps.googleapis.com/maps/api"

    def __init__(self, api_key: str | None = None, timeout: int = 10) -> None:
        self.api_key = (api_key or GOOGLE_MAPS_API_KEY or "").strip()
        if not self.api_key:
            raise GoogleMapsError("Google Maps API key is not configured. Define GOOGLE_MAPS_API_KEY in el entorno.")
        self.timeout = timeout
        self.session = requests.Session()

    def _request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        cache: Optional[MutableMapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        params = {k: v for k, v in params.items() if v is not None}
        params["key"] = self.api_key
        cache_key = _make_cache_key(endpoint, params)

        cached = _cache_get(cache, cache_key)
        if cached is not None:
            return cached

        url = f"{self.base_url}/{endpoint}"
        response = self.session.get(url, params=params, timeout=self.timeout)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise GoogleMapsError(f"HTTP error from Google Maps: {exc}") from exc

        data = response.json()
        status = data.get("status", "OK")

        if status not in {"OK", "ZERO_RESULTS"}:
            error_message = data.get("error_message") or status
            raise GoogleMapsError(f"Google Maps API error ({status}): {error_message}")

        _cache_set(cache, cache_key, data)
        return data

    def autocomplete(
        self,
        query: str,
        *,
        session_token: str | None = None,
        components: Optional[str] = None,
        types: Optional[str] = None,
        language: str = "es",
        cache: Optional[MutableMapping[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        params = {
            "input": query,
            "language": language,
            "sessiontoken": session_token,
            "types": types,
            "components": components,
        }
        data = self._request("place/autocomplete/json", params, cache=cache)
        return data.get("predictions", [])

    def place_details(
        self,
        place_id: str,
        *,
        fields: Iterable[str] | None = None,
        session_token: str | None = None,
        language: str = "es",
        cache: Optional[MutableMapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if fields is None:
            fields = ["geometry/location", "formatted_address", "name", "place_id"]
        if isinstance(fields, str):
            fields = [fields]
        field_list = list(fields)
        params = {
            "place_id": place_id,
            "fields": ",".join(field_list),
            "sessiontoken": session_token,
            "language": language,
        }
        data = self._request("place/details/json", params, cache=cache)
        if data.get("status") == "ZERO_RESULTS":
            raise GoogleMapsError("No se encontraron detalles para el lugar solicitado.")
        return data

    def directions(
        self,
        origin_place_id: str,
        destination_place_id: str,
        *,
        waypoints: Optional[Sequence[str]] = None,
        travel_mode: str = "driving",
        avoid: Optional[str] = None,
        alternatives: bool = False,
        language: str = "es",
        units: str = "metric",
        cache: Optional[MutableMapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        def _format_pid(pid: str) -> str:
            return pid if pid.startswith("place_id:") else f"place_id:{pid}"

        params = {
            "origin": _format_pid(origin_place_id),
            "destination": _format_pid(destination_place_id),
            "mode": travel_mode,
            "avoid": avoid,
            "alternatives": str(bool(alternatives)).lower(),
            "language": language,
            "units": units,
        }
        if waypoints:
            params["waypoints"] = "|".join(_format_pid(pid) for pid in waypoints)

        data = self._request("directions/json", params, cache=cache)
        if data.get("status") == "ZERO_RESULTS":
            raise GoogleMapsError("La API de direcciones no encontró una ruta para los parámetros indicados.")
        return data

    def route_summary(
        self,
        origin_place_id: str,
        destination_place_id: str,
        *,
        waypoints: Optional[Sequence[str]] = None,
        travel_mode: str = "driving",
        avoid: Optional[str] = None,
        cache: Optional[MutableMapping[str, Any]] = None,
    ) -> RouteSummary:
        data = self.directions(
            origin_place_id,
            destination_place_id,
            waypoints=waypoints,
            travel_mode=travel_mode,
            avoid=avoid,
            cache=cache,
        )
        routes = data.get("routes", [])
        if not routes:
            raise GoogleMapsError("La respuesta de Google Maps no contiene rutas disponibles.")

        chosen = routes[0]
        legs: List[Dict[str, Any]] = chosen.get("legs", [])
        distance_m = sum(float(leg.get("distance", {}).get("value", 0.0)) for leg in legs)
        duration_s = sum(float(leg.get("duration", {}).get("value", 0.0)) for leg in legs)
        overview_polyline = chosen.get("overview_polyline", {}).get("points")

        return RouteSummary(
            distance_m=distance_m,
            duration_s=duration_s,
            polyline=overview_polyline,
            polyline_points=decode_polyline(overview_polyline),
            legs=legs,
            summary=chosen.get("summary"),
            warnings=chosen.get("warnings", []),
            fare=chosen.get("fare"),
            raw=data,
        )


__all__ = [
    "GoogleMapsClient",
    "GoogleMapsError",
    "RouteSummary",
    "decode_polyline",
    "haversine_km",
]

