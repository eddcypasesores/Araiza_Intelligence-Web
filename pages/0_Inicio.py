"""Portada pública de Araiza Intelligence, con diseño de dos columnas."""

from pathlib import Path
import base64
import streamlit as st

# Importaciones necesarias (mantener si existen en tu proyecto)
from core.auth import ensure_session_from_token
from core.navigation import render_nav

# --- 1. Configuración de la página ---
st.set_page_config(
    page_title="Inicio - Araiza Intelligence",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Autenticación (para garantizar que se carga la sesión) ---
ensure_session_from_token()

# --- 2. Carga de la imagen (logo.jpg) en Base64 ---
# RUTA: Costos Traslados App\assets\logo.jpg
def image_to_base64(image_path):
    """Convierte una imagen local a Base64."""
    try:
        path_obj = Path(image_path)
        with path_obj.open("rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        st.error(f"Error: No se encontró el archivo de imagen en la ruta: {image_path}. Por favor, verifica la ruta relativa.")
        return None

IMAGE_PATH = "assets/logo.jpg" 
img_base64 = image_to_base64(IMAGE_PATH)

# --- 3. CSS personalizado (Estilos) ---
st.markdown("""
    <style>
    /* VARIABLES DE MARCA */
    :root {
        --brand-red: #dc2626;
        --brand-red-dark: #b91c1c;
        --text-color: #333;
        --background-color: #f9f9f9;
        --dark-gray: #666;
    }

    /* Oculta el encabezado por defecto de Streamlit */
    .stApp > header {
        display: none;
    }
    
    /* Estilos de tipografía y listas */
    .hero-title {
        font-size: 2.8em;
        font-weight: 700;
        margin-bottom: 20px;
        color: var(--brand-red);
    }
    .hero-subtitle {
        font-size: 1.1em;
        line-height: 1.6;
        margin-bottom: 25px;
        color: var(--dark-gray);
    }
    .hero-features ul {
        list-style: none;
        padding-left: 0;
        margin-top: 20px;
    }
    .hero-features li {
        margin-bottom: 10px;
        font-size: 1em;
        color: var(--text-color);
        display: flex;
        align-items: center;
    }
    .hero-features li::before {
        content: '✓';
        color: var(--brand-red);
        font-weight: bold;
        margin-right: 10px;
        font-size: 1.2em;
    }

    /* Asegurar que la imagen dentro de la columna ocupe el espacio */
    .hero-image {
        max-width: 100%;
        height: auto;
        border-radius: 8px;
        object-fit: cover;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. Renderizar navegación ---
render_nav()

# --- 5. Contenido de la página de inicio (SIN contenedor principal) ---

# Crea las dos columnas de Streamlit.
col_img, col_content = st.columns([5, 5]) 

# ----------------- Columna de la Imagen -----------------
with col_img:
    if img_base64:
        st.markdown(
            f'<img class="hero-image" src="data:image/jpeg;base64,{img_base64}" alt="Araiza Intelligence Logo" />', 
            unsafe_allow_html=True
        )
    else:
        st.warning("No se pudo cargar la imagen. Verifique la ruta 'assets/logo.jpg'.")


# ----------------- Columna del Contenido (Texto y Características) -----------------
with col_content:
    st.markdown('<h1 class="hero-title">Araiza Intelligence: Precisión en movimiento.</h1>', unsafe_allow_html=True)

    st.markdown("""
        <p class="hero-subtitle">
            Con la Calculadora de Traslados, estima en segundos el costo real de cada ruta,
            alineando a tus equipos de logística con tarifas transparentes y actualizadas.
        </p>
        <p class="hero-subtitle">
            Complementa la operación con módulos especializados de riesgo fiscal y paneles administrativos,
            pensados para equipos directivos y operativos.
        </p>
        
        <h3 class="hero-features">¿Qué hacemos?</h3>
        <ul>
            <li>Modelamos escenarios logísticos con datos en tiempo real.</li>
            <li>Automatizamos cálculos de costos y presupuestos de traslados.</li>
            <li>Monitoreamos alertas de riesgo fiscal y cumplimiento.</li>
            <li>Conectamos a tus equipos con indicadores accionables.</li>
        </ul>
    """, unsafe_allow_html=True)

    # *** BOTÓN DE INICIAR SESIÓN / EXPLORAR MÓDULOS ELIMINADO ***


# --- Sección de pie de página opcional ---
st.markdown("---") 

st.markdown("""
    <div style="text-align: center; padding: 20px;">
        <p style="color: var(--dark-gray); font-size: 0.9em;">&copy; 2023 Araiza Intelligence. Todos los derechos reservados.</p>
    </div>
""", unsafe_allow_html=True)