"""Streamlit entry point that redirects to the public home page."""

import streamlit as st

st.set_page_config(page_title="Araiza Intelligence", layout="wide")

# Siempre mostramos la portada ubicada en ``pages/0_Inicio.py``.
st.switch_page("pages/0_Inicio.py")