import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# En producción define DATA_DIR apuntando a un disco/volumen persistente
# (Render Disk, volumen de Fly, carpeta de PythonAnywhere...). Ahí se guardan
# la base de datos SQLite y los avatares. Sin DATA_DIR se usa el layout local.
DATA_DIR = os.environ.get("DATA_DIR")


def _database_uri():
    url = os.environ.get("DATABASE_URL")
    if url:
        # Render/Heroku entregan "postgres://", SQLAlchemy exige "postgresql://"
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    if DATA_DIR:
        return "sqlite:///" + os.path.join(DATA_DIR, "liga.db")
    return "sqlite:///" + os.path.join(BASE_DIR, "instance", "liga.db")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cookies de sesión seguras cuando corre detrás de HTTPS (producción)
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Avatares
    AVATAR_FOLDER = (
        os.path.join(DATA_DIR, "avatars") if DATA_DIR
        else os.path.join(BASE_DIR, "app", "static", "uploads", "avatars")
    )
    AVATAR_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
    AVATAR_SIZE = 300  # px (1:1)
    AVATAR_MAX_BYTES = 300 * 1024  # peso final máximo
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # tamaño máximo de subida (8 MB)

    # PokéAPI
    POKEAPI_BASE = "https://pokeapi.co/api/v2"
    POKEAPI_TIMEOUT = 10

    # Reglas de la liga
    BADGES_FOR_ELITE_FOUR = 8
