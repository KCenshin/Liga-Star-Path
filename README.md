# Liga Star Path

Plataforma web para una liga Pokémon: Fichas de Entrenador, constructor de equipos conectado a PokéAPI,
medallas otorgadas por Líderes de Gimnasio y Salón de la Fama con instantáneas históricas.

## Puesta en marcha (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

flask seed-pokemon      # precarga 1025 Pokémon (nombre, tipos, sprite) en pokemon_cache
flask seed-badges       # crea las 8 medallas base
flask create-admin      # crea tu usuario Administrador
flask run               # http://127.0.0.1:5000
```

`flask seed-pokemon` se puede volver a ejecutar sin problema: sólo descarga lo que falte (útil si la red falla a medias).

## Estructura

| Archivo | Contenido |
|---|---|
| `config.py` | Configuración (BD, límites de avatar, PokéAPI, medallas requeridas) |
| `app/models.py` | users, badges, user_badges, teams, team_members, pokemon_cache, hall_of_fame |
| `app/decorators.py` | `@role_required('leader', 'admin')` |
| `app/auth.py` | Registro, login, logout |
| `app/main.py` | Inicio, listado de entrenadores, Ficha pública, edición de perfil, Salón de la Fama |
| `app/teams.py` | Constructor de equipos (6 ranuras) |
| `app/leader.py` | Panel del Líder: otorgar y revocar medallas |
| `app/admin.py` | Roles, medallas/gimnasios, ingreso al Salón de la Fama |
| `app/api.py` | `/api/pokemon/search`, `/api/pokemon/<id>`, `/api/users/search` |
| `app/services/pokeapi.py` | Seed y detalles bajo demanda (con caché en memoria y reintentos) |
| `app/services/avatars.py` | Validación de la firma binaria, recorte 1:1, 300×300, WebP < 300 KB |

## Matriz de permisos aplicada

- **Retador**: perfil, equipos y Fichas públicas.
- **Líder**: lo anterior, más el panel de líder para otorgar o revocar **sólo su medalla**.
- **Alto Mando**: igual que el Retador; su equipo se muestra como "equipo oficial".
- **Administrador**: todo, incluye otorgar o revocar cualquier medalla, cambiar roles y gestionar el Salón de la Fama.

## Notas

- El seed incluye **formas alternativas** (regionales, Mega, Ursaluna Luna Carmesí, Floette Flor Eterna,
  Rotom, Urshifu...), que PokéAPI expone con ID ≥ 10000. Se excluyen Gigamax, Totem, las variantes de
  Pikachu y las formas de batalla de Koraidon y Miraidon (lista en `app/services/pokeapi.py`, `is_excluded`).
  Si cambias la lista, vuelve a correr `flask seed-pokemon`: agrega lo nuevo y quita lo excluido que ningún equipo use.
- Los nombres legibles ("Raichu (Alola)") se guardan en `pokemon_cache.display_name`. Las etiquetas de forma
  traducidas al español están en `_FORM_LABELS`; las que no aparecen ahí se muestran en inglés.
- El seed hace una petición por Pokémon (8 en paralelo) para obtener los tipos. Esto ocurre una sola vez.
- El Salón de la Fama guarda una copia JSON del equipo y una copia física del avatar, así que
  borrar el equipo o cambiar el avatar no altera el registro.
- Para producción (Render, PythonAnywhere o Fly.io) consulta [DEPLOY.md](DEPLOY.md). Define `SECRET_KEY` y `DATA_DIR`
  y usa gunicorn.
