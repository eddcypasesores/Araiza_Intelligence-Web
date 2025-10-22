# Costo de traslados — configuración

Este proyecto utiliza Streamlit para calcular costos de traslado considerando peajes, combustible y gastos asociados.

## Variables de entorno

El archivo `core/config.py` lee distintas variables para localizar bases de datos y fuentes de datos. Para habilitar la capa de Google Maps es necesario definir la llave del API antes de ejecutar la aplicación:

```bash
export GOOGLE_MAPS_API_KEY="tu_api_key_de_google_maps"
```

También puedes declararla en `.streamlit/secrets.toml` cuando despliegas en Streamlit Cloud:

```toml
GOOGLE_MAPS_API_KEY = "tu_api_key_de_google_maps"
```

La clave debe generarse en [Google Cloud Console](https://console.cloud.google.com/) con los servicios **Maps JavaScript**, **Places**, **Directions** y **Geocoding** habilitados para que el autocompletado y las rutas funcionen correctamente.

## Dependencias

Instala los requisitos con:

```bash
pip install -r requirements.txt
```

Además de Streamlit, pandas y otras librerías originales, ahora se utiliza `requests` para comunicarse con la API de Google Maps.