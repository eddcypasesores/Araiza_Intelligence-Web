"""Helpers para autenticar usuarios y persistir la sesión entre páginas."""

from __future__ import annotations

import secrets
from typing import MutableMapping, Sequence

import streamlit as st


AuthRecord = MutableMapping[str, str]


@st.cache_resource(show_spinner=False)
def _auth_store() -> dict[str, AuthRecord]:
    """Devuelve el almacén en memoria que guarda los tokens activos."""

    return {}


def _normalize_param(value) -> str | None:
    """Normaliza los parámetros obtenidos desde ``st.query_params``."""

    if isinstance(value, list):
        return value[-1] if value else None
    if isinstance(value, str):
        return value or None
    return None


def _current_token() -> str | None:
    """Obtiene el token actual desde la sesión o los parámetros de URL."""

    token = st.session_state.get("auth_token")
    if token:
        return str(token)

    params = st.query_params
    raw_token = _normalize_param(params.get("auth"))
    if raw_token:
        st.session_state["auth_token"] = raw_token
    return raw_token


def ensure_session_from_token() -> None:
    """Restaura ``usuario`` y ``rol`` usando el token persistido si hace falta."""

    token = _current_token()
    if not token:
        return

    store = _auth_store()
    record = store.get(token)
    if not record:
        # El token ya no es válido: limpiar cualquier rastro en la sesión.
        st.session_state.pop("auth_token", None)
        try:
            st.query_params.pop("auth", None)
        except Exception:
            pass
        return

    for key in ("usuario", "rol", "permisos", "must_change_password", "portal_user_id"):
        value = record.get(key)
        if value is not None and st.session_state.get(key) != value:
            st.session_state[key] = value

    # Asegura que el parámetro "auth" esté presente para navegación HTML.
    params = st.query_params
    if _normalize_param(params.get("auth")) != token:
        try:
            params.update({"auth": token})
        except Exception:
            pass


def persist_login(
    username: str,
    permisos_or_rol: Sequence[str] | str,
    *,
    must_change_password: bool = False,
    user_id: int | None = None,
) -> str:
    """Genera o renueva el token de autenticacion para un usuario valido."""

    store = _auth_store()
    old_token = st.session_state.pop("auth_token", None)
    if old_token:
        store.pop(str(old_token), None)

    if isinstance(permisos_or_rol, str):
        rol = permisos_or_rol
        permisos = ["traslados", "riesgos", "admin"] if rol == "admin" else ["traslados"]
    else:
        permisos = sorted({p.strip().lower() for p in permisos_or_rol if p})
        rol = "admin" if "admin" in permisos else "operador"

    token = secrets.token_urlsafe(32)
    store[token] = {
        "usuario": username,
        "rol": rol,
        "permisos": permisos,
        "must_change_password": bool(must_change_password),
        "portal_user_id": user_id,
    }

    st.session_state["auth_token"] = token
    st.session_state["usuario"] = username
    st.session_state["rol"] = rol
    st.session_state["permisos"] = permisos
    st.session_state["must_change_password"] = bool(must_change_password)
    if user_id is not None:
        st.session_state["portal_user_id"] = user_id

    return token


def forget_session() -> None:
    """Elimina el token y las llaves principales de la sesión actual."""

    store = _auth_store()
    token = st.session_state.pop("auth_token", None)
    if token:
        store.pop(str(token), None)

    for key in ("usuario", "rol", "permisos", "must_change_password", "portal_user_id"):
        st.session_state.pop(key, None)

    try:
        st.query_params.pop("auth", None)
    except Exception:
        pass


def auth_query_params() -> dict[str, str]:
    """Devuelve un diccionario con el token actual para agregarlo a enlaces."""

    token = _current_token()
    if not token:
        return {}
    return {"auth": token}
