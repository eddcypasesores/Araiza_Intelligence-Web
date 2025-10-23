"""Reusable Streamlit component wrappers for the project."""

from __future__ import annotations
from pathlib import Path
from typing import Any
import streamlit.components.v1 as components


# === Base directory for custom components ===
_COMPONENT_BASE = Path(__file__).resolve().parent.parent / "pages" / "components"


# ===============================================================
# 1️⃣ Componente existente: Autocomplete (campo individual)
# ===============================================================
_GMAPS_COMPONENT_DIR = _COMPONENT_BASE / "gmaps_autocomplete"

if _GMAPS_COMPONENT_DIR.exists():
    _gmaps_autocomplete_component = components.declare_component(
        "gmaps_autocomplete",
        path=str(_GMAPS_COMPONENT_DIR.resolve())
    )
else:
    _gmaps_autocomplete_component = None


def gmaps_autocomplete_component(**kwargs: Any) -> Any:
    """
    Devuelve el componente de autocompletado de Google Maps (campo individual).

    Argumentos:
        label (str): etiqueta del campo.
        value (str): texto inicial.
        placeholder (str): texto de sugerencia.
        apiKey (str): clave API de Google Maps.
        elementId (str): identificador único del componente.
        key (str): clave Streamlit para persistencia de estado.
        default (dict): valores guardados previos.

    Retorna:
        dict con la estructura:
        {
          "place_id": str,
          "description": str,
          "address": str,
          "lat": float,
          "lng": float
        }
    """
    if _gmaps_autocomplete_component is None:
        raise RuntimeError(
            f"Google Maps autocomplete component assets were not found at {_GMAPS_COMPONENT_DIR}"
        )
    return _gmaps_autocomplete_component(**kwargs)


# ===============================================================
# 2️⃣ Nuevo componente: Multi-Autocomplete con drag & drop
# ===============================================================
_GMAPS_MULTI_DIR = _COMPONENT_BASE / "gmaps_multi_autocomplete"

if _GMAPS_MULTI_DIR.exists():
    _gmaps_multi_component = components.declare_component(
        "gmaps_multi_autocomplete",
        path=str(_GMAPS_MULTI_DIR.resolve())
    )
else:
    _gmaps_multi_component = None


def gmaps_multi_autocomplete(**kwargs: Any) -> Any:
    """
    Componente mejorado que permite ingresar múltiples puntos (origen, paradas, destino)
    con autocompletado y reordenamiento tipo Google Maps.

    Argumentos esperados:
        apiKey (str): clave de API de Google Maps.
        value (dict): estado inicial, ej. {"items": [...]}
        stored (dict): estado guardado previo (opcional).
        countryRestriction (str): restringe autocompletado a país, ej. "mx".
        key (str): clave Streamlit.

    Devuelve:
        dict con estructura:
        {
          "items": [
              {"role": "origin", "description": "Toluca", "place_id": "...", ...},
              {"role": "waypoint", "description": "Querétaro", "place_id": "...", ...},
              {"role": "destination", "description": "Monterrey", "place_id": "...", ...}
          ]
        }
    """
    if _gmaps_multi_component is None:
        raise RuntimeError(
            f"Google Maps multi component assets were not found at {_GMAPS_MULTI_DIR}"
        )
    return _gmaps_multi_component(**kwargs)
