from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests

from .config import INEGI_ROUTING_BASE_URL, INEGI_ROUTING_TOKEN


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
    toll_cost: float = 0.0
    axes_cost: float = 0.0
    route_type: str = ""


class InegiRoutingClient:
    """Cliente mínimo para la API SAKBÉ (INEGI)."""

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: int = 20,
        user_agent: str | None = None,
    ) -> None:
        raw_base = (base_url or INEGI_ROUTING_BASE_URL or "").strip()
        legacy_suffix = "/api/ruteo/route/v1"
        if raw_base.endswith(legacy_suffix):
            raw_base = raw_base[: -len(legacy_suffix)]
        self.base_url = raw_base.rstrip("/")
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
        parsed = urlparse(self.base_url)
        origin = f"{parsed.scheme or 'https'}://{parsed.netloc or 'gaia.inegi.org.mx'}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
            "User-Agent": user_agent
            or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
            "Referer": origin + "/",
            "Origin": origin,
        }
        self.session.headers.update(headers)

    # ------------ utilidades internas ------------
    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.post(url, data=payload, timeout=self.timeout)
        if response.status_code >= 400:
            raise InegiRoutingError(
                f"SAKBÉ respondió {response.status_code}: {response.text[:200]}"
            )
        try:
            data = response.json()
        except ValueError:
            snippet = (response.text or "").strip().replace("\n", " ")
            snippet = snippet[:280]
            raise InegiRoutingError(
                f"La respuesta de {endpoint} no es JSON válido. {snippet}"
            )
        resp_meta = data.get("response")
        if resp_meta and not resp_meta.get("success", True):
            raise InegiRoutingError(resp_meta.get("message") or "La API reportó un error.")
        return data

    @staticmethod
    def _extract_point(geojson_payload: Any) -> Optional[Tuple[float, float]]:
        if not geojson_payload:
            return None
        payload = geojson_payload
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                return None
        if isinstance(payload, dict):
            coords = payload.get("coordinates")
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                lon, lat = coords[0], coords[1]
                try:
                    return (float(lat), float(lon))
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _extract_line_coords(geojson_payload: Any) -> List[Tuple[float, float]]:
        payload = geojson_payload
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                return []
        if isinstance(payload, dict):
            coords = payload.get("coordinates") or []
            out: List[Tuple[float, float]] = []
            for entry in coords:
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    lon, lat = entry[0], entry[1]
                    try:
                        out.append((float(lat), float(lon)))
                    except (TypeError, ValueError):
                        continue
            return out
        return []

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371000.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c

    # ------------ búsquedas y utilidades públicas ------------
    def search_destinations(
        self,
        query: str,
        *,
        limit: int = 15,
        projection: str = "GRS80",
        output: str = "json",
    ) -> List[Dict[str, Any]]:
        payload = {
            "buscar": query,
            "type": output,
            "num": int(limit),
            "proj": projection,
            "key": self.token,
        }
        data = self._post("buscadestino", payload)
        results = data.get("data")
        if isinstance(results, list):
            return results
        return []

    def resolve_destination(
        self,
        query: str,
        *,
        lat: float | None = None,
        lng: float | None = None,
        limit: int = 15,
    ) -> Tuple[int, Dict[str, Any]]:
        results = self.search_destinations(query, limit=limit)
        if not results:
            raise InegiRoutingError(f"No se encontraron destinos para '{query}'.")
        if lat is not None and lng is not None:

            def distance(entry: Dict[str, Any]) -> float:
                point = self._extract_point(entry.get("geojson"))
                if point is None:
                    return float("inf")
                plat, plon = point
                return self._haversine(lat, lng, plat, plon)

            results = sorted(results, key=distance)
        best = results[0]
        try:
            dest_id = int(best.get("id_dest"))
        except Exception as exc:  # pragma: no cover
            raise InegiRoutingError("La respuesta de destinos no contiene 'id_dest'.") from exc
        return dest_id, best

    # ------------ rutas destino a destino ------------
    def route_destinos(
        self,
        *,
        tipo: str,
        dest_i: int,
        dest_f: int,
        vehicle: int = 1,
        axes: int = 0,
        projection: str = "GRS80",
        output: str = "json",
    ) -> InegiRouteSummary:
        endpoint = (tipo or "cuota").strip().lower()
        if endpoint not in {"cuota", "libre", "optima"}:
            raise InegiRoutingError("Tipo de ruta no soportado. Usa 'cuota', 'libre' u 'optima'.")

        payload = {
            "dest_i": int(dest_i),
            "dest_f": int(dest_f),
            "v": int(vehicle),
            "e": int(max(0, axes)),
            "proj": projection,
            "type": output,
            "key": self.token,
        }
        data = self._post(endpoint, payload)
        raw_data = data.get("data")
        if isinstance(raw_data, list):
            route_data = raw_data[0] if raw_data else {}
        elif isinstance(raw_data, dict):
            route_data = raw_data
        else:
            route_data = {}
        if not route_data:
            raise InegiRoutingError("La respuesta de INEGI no incluye datos de ruta.")

        distance_km = float(route_data.get("long_km") or route_data.get("longitud_km") or 0.0)
        duration_min = float(route_data.get("tiempo_min") or 0.0)
        toll_cost = float(route_data.get("costo_caseta") or 0.0)
        axes_cost = float(route_data.get("eje_excedente") or 0.0)
        geometry = route_data.get("geojson")

        return InegiRouteSummary(
            distance_m=distance_km * 1000.0,
            duration_s=duration_min * 60.0,
            coordinates=self._extract_line_coords(geometry),
            geometry=geometry,
            legs=[],
            raw=route_data,
            toll_cost=toll_cost,
            axes_cost=axes_cost,
            route_type=endpoint,
        )

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "InegiRoutingClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        self.close()


__all__ = ["InegiRoutingClient", "InegiRoutingError", "InegiRouteSummary"]
