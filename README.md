# Costo de traslados - configuracion

Aplicacion Streamlit para estimar costos de traslado considerando peajes, combustible y otros gastos operativos.

## Variables de entorno

`core/config.py` busca distintas variables para localizar bases de datos y claves de terceros. Para habilitar Google Maps define la llave del API antes de ejecutar la aplicacion:

```bash
export GOOGLE_MAPS_API_KEY="tu_api_key_de_google_maps"
```

En despliegues de Streamlit Cloud puedes declararla dentro de `.streamlit/secrets.toml`:

```toml
GOOGLE_MAPS_API_KEY = "tu_api_key_de_google_maps"
```

La clave debe habilitar **Maps JavaScript**, **Places**, **Directions** y **Geocoding** para que el autocompletado y las rutas funcionen.

- Para persistir los usuarios del portal en un servicio administrado, define `PORTAL_DATABASE_URL` (o `DATABASE_URL`) con una cadena de conexión PostgreSQL, por ejemplo:

  ```bash
  export PORTAL_DATABASE_URL="postgresql://usuario:contraseña@host:5432/nombre_db"
  ```

  Si la variable no está presente, el portal seguirá utilizando el archivo SQLite local indicado por `DB_PATH`, lo que significa que Render u otros contenedores efímeros perderán las cuentas en cada reinicio.

### Migrar los usuarios existentes a PostgreSQL

1. Provisiona la base de datos (Render PostgreSQL, Neon, Supabase, etc.) y toma la URL de conexión.
2. Define `PORTAL_DATABASE_URL` (o `DATABASE_URL`) en tu entorno local y en Render.
3. Instala los requisitos (`pip install -r requirements.txt`), que ahora incluyen `psycopg[binary]`.
4. Ejecuta una primera vez la aplicación o corre `python tools/migrate_portal_users.py` para copiar los usuarios registrados en `db/tolls.db` hacia la nueva instancia de PostgreSQL.
5. Despliega; el seed del superusuario se ejecuta automáticamente solo si no encuentra el RFC configurado.

> El resto de la información (rutas, tarifas, parámetros, etc.) continúa almacenándose en SQLite dentro de `db/tolls.db`. Solo las tablas `portal_users` y `portal_user_resets` se mueven a PostgreSQL.

## Dependencias

Instala los requisitos con:

```bash
pip install -r requirements.txt
```

## Gestion de usuarios y trabajadores

- El acceso de super administradores parte de `pages/16_Acerca_de_nosotros.py`. Tras autenticarse con privilegio **admin** se redirige al panel `pages/19_Admin_portal.py`, donde se crean, consultan, modifican y eliminan cuentas del portal con sus permisos por módulo.
- El login inicial usa el RFC como contrasena temporal y obliga a cambiarla en el primer acceso.
- El menu **Trabajadores** dentro del modulo de Traslados conserva la informacion operativa del personal (nombre, apellidos, rol, salario, numero economico), sin asignar roles ni contrasenas.

## Recuperacion de contrasenas

- Desde `pages/19_Admin_portal.py` (pestaña **Recuperacion**) un super administrador puede generar enlaces temporales (token) y revocar los que sigan activos.
- El formulario publico `pages/18_Restablecer_contrasena.py` permite capturar el token y definir una nueva contrasena valida.
- Las pantallas de ingreso de Traslados y Monitoreo EFOS ofrecen un acceso directo a dicho formulario y un restablecimiento rapido al RFC como alternativa de emergencia.
