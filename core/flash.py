"""Flash-style notifications rendered as toasts across pages."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

_FLASH_KEY = "_flash_message"
_DEFAULT_ICONS: Mapping[str, str] = {
    "success": "✅",
    "info": "ℹ️",
    "warning": "⚠️",
    "error": "❌",
}


def set_flash(message: str, kind: str = "success", *, icon: str | None = None) -> None:
    """Store a one-time message to be shown on the next render."""

    cleaned = (message or "").strip()
    if not cleaned:
        return

    st.session_state[_FLASH_KEY] = {
        "message": cleaned,
        "kind": (kind or "success").lower(),
        "icon": icon,
    }


def consume_flash() -> None:
    """Render and discard the pending flash notification if present."""

    payload: Mapping[str, Any] | None = st.session_state.pop(_FLASH_KEY, None)
    if not payload:
        return

    message = (payload.get("message") or "").strip()
    if not message:
        return

    kind = str(payload.get("kind") or "success").lower()
    icon = payload.get("icon") or _DEFAULT_ICONS.get(kind, "✅")

    try:
        st.toast(message, icon=icon)
        return
    except Exception:
        pass

    renderer = {
        "success": st.success,
        "info": st.info,
        "warning": st.warning,
        "error": st.error,
    }.get(kind, st.success)
    renderer(message)

