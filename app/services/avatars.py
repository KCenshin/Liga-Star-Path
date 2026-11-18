"""Carga segura y optimización de avatares con Pillow."""
import io
import os
import shutil
import uuid

from flask import current_app
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

# Firmas binarias ("magic numbers") de los formatos permitidos
_SIGNATURES = {
    "jpeg": lambda h: h[:3] == b"\xff\xd8\xff",
    "png": lambda h: h[:8] == b"\x89PNG\r\n\x1a\n",
    "webp": lambda h: h[:4] == b"RIFF" and h[8:12] == b"WEBP",
}
_EXT_TO_FORMAT = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}


class AvatarError(ValueError):
    pass


def _detect_format(header: bytes):
    for fmt, check in _SIGNATURES.items():
        if check(header):
            return fmt
    return None


def save_avatar(file_storage, old_filename=None) -> str:
    """Valida, recorta (1:1), redimensiona y guarda el avatar. Devuelve el nombre final."""
    cfg = current_app.config
    original = secure_filename(file_storage.filename or "")
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in cfg["AVATAR_ALLOWED_EXTENSIONS"]:
        raise AvatarError("Formato no permitido. Usa .jpg, .png o .webp.")

    data = file_storage.read()
    real_format = _detect_format(data[:16])
    if real_format is None or real_format != _EXT_TO_FORMAT[ext]:
        raise AvatarError("El contenido del archivo no coincide con su extensión.")

    try:
        img = Image.open(io.BytesIO(data))
        img.verify()  # detecta archivos corruptos o manipulados
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
    except Exception as exc:  # noqa: BLE001
        raise AvatarError("La imagen está dañada o no es válida.") from exc

    size = cfg["AVATAR_SIZE"]
    img = img.convert("RGBA") if img.mode in ("P", "LA", "RGBA") else img.convert("RGB")
    img = ImageOps.fit(img, (size, size), Image.LANCZOS, centering=(0.5, 0.5))

    # Guardar como WebP bajando calidad hasta quedar < 300 KB
    filename = secure_filename(f"{uuid.uuid4().hex}.webp")
    buf = b""
    for quality in (90, 80, 70, 60, 50, 40, 30):
        out = io.BytesIO()
        img.save(out, "WEBP", quality=quality, method=6)
        buf = out.getvalue()
        if len(buf) <= cfg["AVATAR_MAX_BYTES"]:
            break

    with open(os.path.join(cfg["AVATAR_FOLDER"], filename), "wb") as fh:
        fh.write(buf)

    if old_filename:
        delete_avatar(old_filename)
    return filename


def delete_avatar(filename):
    path = os.path.join(current_app.config["AVATAR_FOLDER"], secure_filename(filename))
    if os.path.isfile(path):
        os.remove(path)


def snapshot_avatar(filename):
    """Copia el avatar actual para que el Salón de la Fama no cambie si el usuario lo reemplaza."""
    if not filename:
        return None
    folder = current_app.config["AVATAR_FOLDER"]
    src = os.path.join(folder, secure_filename(filename))
    if not os.path.isfile(src):
        return None
    new_name = f"hof_{uuid.uuid4().hex}.webp"
    shutil.copyfile(src, os.path.join(folder, new_name))
    return new_name
