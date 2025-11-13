"""Shared light/dark theme helpers for all Streamlit pages."""

from __future__ import annotations

import streamlit as st


THEME_CSS = """
<style>
:root {
  color-scheme: light dark;
  --ai-page-bg:#f8fafc;
  --ai-page-text:#0f172a;
  --ai-surface-bg:#ffffff;
  --ai-surface-text:#0f172a;
  --ai-border-color:rgba(15,23,42,0.1);
  --ai-muted-text:rgba(15,23,42,0.65);
  --ai-card-shadow:0 25px 60px rgba(15,23,42,0.15);
  --ai-accent:#0f172a;
  --ai-accent-contrast:#ffffff;
  --ai-input-bg:rgba(255,255,255,0.9);
}
@media (prefers-color-scheme: dark) {
  :root {
    --ai-page-bg:#020617;
    --ai-page-text:#e2e8f0;
    --ai-surface-bg:#0f172a;
    --ai-surface-text:#e2e8f0;
    --ai-border-color:rgba(226,232,240,0.15);
    --ai-muted-text:rgba(226,232,240,0.7);
    --ai-card-shadow:0 35px 70px rgba(0,0,0,0.7);
    --ai-accent:#38bdf8;
    --ai-accent-contrast:#020617;
    --ai-input-bg:rgba(15,23,42,0.65);
  }
}
html, body, .stApp, [data-testid="stAppViewContainer"] {
  background:var(--ai-page-bg) !important;
  color:var(--ai-page-text) !important;
}
.stApp *:not(svg):not(path) {
  color:inherit;
}
.block-container {
  color:var(--ai-page-text) !important;
}
section[data-testid="stSidebar"] {
  background:var(--ai-surface-bg);
  color:var(--ai-surface-text);
}
.stButton>button,
.stDownloadButton>button,
.stFormSubmitButton>button {
  background:var(--ai-accent);
  color:var(--ai-accent-contrast) !important;
  border:none;
  border-radius:999px;
  font-weight:600;
  transition:filter 120ms ease;
}
.stButton>button:hover,
.stDownloadButton>button:hover,
.stFormSubmitButton>button:hover {
  filter:brightness(1.05);
}
.stTextInput input,
.stNumberInput input,
.stSelectbox div[data-baseweb="select"]>div,
.stTextArea textarea,
.stDateInput input {
  background:var(--ai-input-bg);
  color:var(--ai-page-text);
  border:1px solid var(--ai-border-color);
  border-radius:12px;
}
</style>
"""


def apply_theme(extra_css: str | None = None) -> None:
    """Inject the shared theme CSS in the current Streamlit page."""

    st.markdown(THEME_CSS, unsafe_allow_html=True)
    if extra_css:
        st.markdown(f"<style>{extra_css}</style>", unsafe_allow_html=True)
