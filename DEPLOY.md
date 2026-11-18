# Despliegue de Liga Star Path

La app es Flask + SQLite, con avatares guardados en disco. Por eso necesita un host que ejecute Python
y tenga **almacenamiento persistente**. GitHub Pages no sirve para esto.

## Variables de entorno

| Variable | Para qué sirve |
|---|---|
| `SECRET_KEY` | **Obligatoria en producción.** Cadena larga y aleatoria. Genera una con `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `DATA_DIR` | Carpeta persistente donde se guardan `liga.db` y `avatars/`. |
| `DATABASE_URL` | Opcional. Si la defines (por ejemplo Postgres), se usa en vez de SQLite. |
| `COOKIE_SECURE` | `1` cuando el sitio va por HTTPS (todos los hosts de abajo). |

## Primer arranque (en cualquier host)

Cuando la app ya esté desplegada, ejecuta una sola vez estos comandos en una consola del servidor:

```bash
flask seed-badges
flask seed-pokemon     # descarga ~1025 Pokémon; tarda unos minutos
flask create-admin
```

`FLASK_APP=run.py` ya viene en `.flaskenv`. Si el host no lo lee, añade `--app run.py` (`flask --app run.py seed-badges`).

---

## Opción A: Render

Es la más sencilla, pero **el disco persistente solo existe en planes de pago** (Starter, unos 7 USD/mes).
En el plan Free el disco se borra en cada despliegue y perderías usuarios y avatares.

1. Sube el repositorio a GitHub (con `render.yaml`, `Procfile` y `requirements.txt`).
2. Entra a [render.com](https://render.com), crea una cuenta y elige **New → Blueprint**.
3. Conecta tu repositorio. Render lee `render.yaml`, crea el servicio web con un disco de 1 GB en `/var/data`
   y genera `SECRET_KEY` por ti.
4. Espera a que termine el build. Tu URL será `https://liga-star-path.onrender.com`.
5. En el servicio, abre la pestaña **Shell** y ejecuta los comandos del primer arranque.

Alternativa gratis: usa una base **Postgres** gratuita de Render (`DATABASE_URL`), pero los avatares seguirían
en disco efímero. Para eso habría que guardarlos en un almacenamiento externo (S3, Cloudinary), lo cual
requiere cambiar `app/services/avatars.py`.

## Opción B: PythonAnywhere

Tiene plan gratuito con disco persistente, ideal para empezar. Limitaciones del plan gratis: un solo
subdominio `tuusuario.pythonanywhere.com`, y las peticiones salientes solo van a sitios de una lista permitida
(`pokeapi.co` está incluido, así que `seed-pokemon` funciona).

1. Crea una cuenta en [pythonanywhere.com](https://www.pythonanywhere.com).
2. Abre una consola **Bash** y clona el repo:
   ```bash
   git clone https://github.com/TU_USUARIO/Liga-Star-Path.git
   cd Liga-Star-Path
   python3.12 -m venv .venv          # usa una versión que ofrezca tu cuenta
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Ejecuta los comandos del primer arranque (`flask seed-badges`, etc.). Sin `DATA_DIR`, la BD queda en
   `instance/` y los avatares en `app/static/uploads/`, que son persistentes en PythonAnywhere.
4. Pestaña **Web → Add a new web app → Manual configuration** (misma versión de Python).
5. En esa pestaña configura:
   - **Source code:** `/home/TU_USUARIO/Liga-Star-Path`
   - **Virtualenv:** `/home/TU_USUARIO/Liga-Star-Path/.venv`
   - **Static files:** URL `/static/` → directorio `/home/TU_USUARIO/Liga-Star-Path/app/static`
6. Abre el archivo WSGI (enlace en la misma pestaña), bórralo todo y deja:
   ```python
   import os, sys

   path = "/home/TU_USUARIO/Liga-Star-Path"
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ["SECRET_KEY"] = "PEGA_AQUI_TU_CLAVE_LARGA"
   os.environ["COOKIE_SECURE"] = "1"

   from run import app as application
   ```
7. Pulsa **Reload**. Tu sitio queda en `https://TU_USUARIO.pythonanywhere.com`.
8. Para actualizar: `git pull` en la consola Bash y **Reload**.

## Opción C: Fly.io

Usa el `Dockerfile` y `fly.toml` incluidos. Fly pide tarjeta de crédito. La máquina pequeña con volumen
cuesta pocos dólares al mes.

1. Instala la CLI: `iwr https://fly.io/install.ps1 -useb | iex` (PowerShell), y reinicia la terminal.
2. `fly auth signup` (o `fly auth login`).
3. Dentro del repo, crea la app sin desplegar. Si el nombre `liga-star-path` ya está tomado, elige otro y
   cámbialo en `fly.toml`:
   ```powershell
   fly launch --no-deploy --copy-config
   ```
4. Crea el volumen persistente en la misma región que `primary_region`:
   ```powershell
   fly volumes create liga_data --size 1 --region qro
   ```
5. Define la clave secreta:
   ```powershell
   fly secrets set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
   ```
6. Despliega:
   ```powershell
   fly deploy
   ```
7. Primer arranque dentro de la máquina:
   ```powershell
   fly ssh console -C "flask --app run.py seed-badges"
   fly ssh console -C "flask --app run.py seed-pokemon"
   fly ssh console -C "flask --app run.py create-admin"
   ```
   (`create-admin` pide datos de forma interactiva; si falla en `-C`, usa `fly ssh console` y ejecútalo dentro.)

Importante: un volumen de Fly pertenece a **una sola máquina**, así que no escales a varias. Para actualizar,
solo vuelve a correr `fly deploy`.

---

## Notas

- `instance/` y `app/static/uploads/` están en `.gitignore`: tu base de datos local **no** se sube. Si quieres
  llevarte los datos actuales, copia `instance/liga.db` al `DATA_DIR` del servidor (por ejemplo con `fly sftp`
  o la consola de PythonAnywhere) junto con la carpeta de avatares.
- Si ya tienes avatares guardados localmente y activas `DATA_DIR`, copia `app/static/uploads/avatars/*` a
  `$DATA_DIR/avatars/`.
- Haz copias de seguridad periódicas de `liga.db` y `avatars/`.
