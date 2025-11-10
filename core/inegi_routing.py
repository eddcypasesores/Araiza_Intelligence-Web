from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import re

import requests

from .config import INEGI_ROUTING_BASE_URL, INEGI_ROUTING_TOKEN
from .maps import decode_polyline


class InegiRoutingError(RuntimeError):
    """Raised when the INEGI routing API returns an error response."""


@dataclass
class InegiRouteSummary:
    distance_m: float
    duration_s: float
    coordinates: List[Tuple[float, float]]
    geometry: Any
    legs: List[Dict[str, Any]]
    raw: Dict[str, Any]


class InegiRoutingClient:
    """Minimal client for the INEGI routing (MXSIG) API."""

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: int = 15,
        user_agent: str | None = None,
    ) -> None:
        self.base_url = (base_url or INEGI_ROUTING_BASE_URL or "").rstrip("/")
        if not self.base_url:
            raise InegiRoutingError(
                "Configura INEGI_ROUTING_BASE_URL para consumir la API de ruteo."
            )

        self.token = (token or INEGI_ROUTING_TOKEN or "").strip()
        if not self.token:
            raise InegiRoutingError(
                "Configura INEGI_ROUTING_TOKEN en tus secretos o pásalo al cliente."
            )

        self.timeout = timeout
        self.session = requests.Session()
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
            "User-Agent": user_agent
            or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
            "Referer": "https://gaia.inegi.org.mx/",
            "Origin": "https://gaia.inegi.org.mx",
        }
        self.session.headers.update(headers)

    @staticmethod
    def _normalize_coordinates(
        coordinates: Sequence[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        if len(coordinates) < 2:
            raise InegiRoutingError("Proporciona al menos origen y destino para ruteo.")

        normalized: List[Tuple[float, float]] = []
        for lat, lng in coordinates:
            try:
                norm_lat = float(lat)
                norm_lng = float(lng)
            except (TypeError, ValueError) as exc:
                raise InegiRoutingError("Coordenadas inválidas para la API de ruteo.") from exc
            normalized.append((norm_lat, norm_lng))
        return normalized

    @staticmethod
    def _format_coordinate_string(coords: Sequence[Tuple[float, float]]) -> str:
        return ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in coords)

    def _build_route_url(self, profile: str, coords: Sequence[Tuple[float, float]]) -> str:
        profile = (profile or "driving").strip().lower()
        return f"{self.base_url}/{profile}/{self._format_coordinate_string(coords)}"

    @staticmethod
    def _extract_coordinates(geometry: Any) -> List[Tuple[float, float]]:
        if not geometry:
            return []
        if isinstance(geometry, dict):
            coords = geometry.get("coordinates") or []
            out: List[Tuple[float, float]] = []
            for entry in coords:
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    lng, lat = entry[0], entry[1]
                    try:
                        out.append((float(lat), float(lng)))
                    except (TypeError, ValueError):
                        continue
            return out
        if isinstance(geometry, str):
            return decode_polyline(geometry)
        return []

    def route(
        self,
        coordinates: Sequence[Tuple[float, float]],
        *,
        profile: str = "driving",
        alternatives: int = 0,
        steps: bool = True,
        annotations: bool = False,
        overview: str = "full",
        geometries: str = "geojson",
        continue_straight: Optional[bool] = None,
    ) -> InegiRouteSummary:
        normalized = self._normalize_coordinates(coordinates)
        url = self._build_route_url(profile, normalized)

        params: Dict[str, Any] = {
            "token": self.token,
            "alternatives": int(max(0, alternatives)),
            "steps": str(bool(steps)).lower(),
            "annotations": str(bool(annotations)).lower(),
            "overview": overview,
            "geometries": geometries,
        }
        if continue_straight is not None:
            params["continue_straight"] = str(bool(continue_straight)).lower()

        response = self.session.get(url, params=params, timeout=self.timeout)
        if response.status_code >= 400:
            raise InegiRoutingError(
                f"INEGI API respondió {response.status_code}: {response.text[:200]}"
            )

        raw_text = ""
        status = response.status_code
        try:
            data = response.json()
        except ValueError:
            raw_text = (response.text or "").strip()
            snippet = raw_text.replace("\n", " ").replace("\r", " ")
            snippet = re.sub(r"\s+", " ", snippet) if " " in snippet else snippet  # type: ignore[name-defined]
            if snippet:
                snippet = snippet[:280]
            message = f"La respuesta de ruteo no es JSON válido (HTTP {status})."
            if snippet:
                message += f" Contenido devuelto: {snippet}"
            raise InegiRoutingError(message)

        code = str(data.get("code", "")).lower()
        if code and code not in {"ok", "200", "0"}:
            message = data.get("message") or data.get("error") or "Respuesta inválida de ruteo."
            raise InegiRoutingError(str(message))

        routes = data.get("routes") or []
        if not routes:
            raise InegiRoutingError("La respuesta de INEGI no contiene rutas.")

        chosen = routes[0]
        distance_m = float(chosen.get("distance", 0.0))
        duration_s = float(chosen.get("duration", 0.0))
        geometry = chosen.get("geometry")
        legs = chosen.get("legs", [])

        return InegiRouteSummary(
            distance_m=distance_m,
            duration_s=duration_s,
            coordinates=self._extract_coordinates(geometry),
            geometry=geometry,
            legs=legs,
            raw=data,
        )

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "InegiRoutingClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()


__all__ = ["InegiRoutingClient", "InegiRoutingError", "InegiRouteSummary"]
