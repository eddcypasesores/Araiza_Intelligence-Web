"""Utilities for managing authentication-related session state."""

from __future__ import annotations

from typing import Iterable

import streamlit as st

# Keys that should be removed from ``st.session_state`` when logging out.
_LOGOUT_SESSION_KEYS: tuple[str, ...] = (
    "usuario",
    "rol",
    "excluded_set",
    "route",
    "show_detail",
    "tarifas_view",
    "usuarios_view",
    "parametros_view",
)


def clear_session_state(keys: Iterable[str] = _LOGOUT_SESSION_KEYS) -> None:
    """Remove the provided keys from ``st.session_state`` if they exist."""

    for key in keys:
        st.session_state.pop(key, None)


def _normalize_flag(value: str | list[str] | None) -> str:
    """Return the logout flag as a single string value."""

    if isinstance(value, list):
        return value[-1] if value else "0"
    return value or "0"


def process_logout_flag() -> bool:
    """Clear the session if the ``logout`` query parameter is present.

    Returns ``True`` when the logout flag was detected and handled.
    """

    params = st.query_params
    logout_flag = _normalize_flag(params.get("logout"))
    if logout_flag != "1":
        return False

    clear_session_state()

    try:
        params.clear()
    except Exception:
        # ``st.query_params`` may not support ``clear`` on older Streamlit versions.
        pass

    return True
