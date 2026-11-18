"""Integración con PokéAPI: precarga (seed) a caché local y detalles bajo demanda.

Incluye formas alternativas (regionales, Mega, Ursaluna Luna Carmesí, Floette Flor Eterna...),
que PokéAPI expone como Pokémon con ID >= 10000, y excluye las que no se usan en la liga.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

import requests
from flask import current_app
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..extensions import db
from ..models import PokemonCache, TeamMember

SPRITE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{id}.png"
_session = requests.Session()
_session.headers["User-Agent"] = "liga-pokemon-app/1.0"
_session.mount("https://", HTTPAdapter(pool_maxsize=16, max_retries=Retry(
    total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))))

# --- Formas excluidas: Gigamax, Totem y variantes cosméticas / no competitivas ---
EXCLUDED_SUFFIXES = ("-gmax", "-eternamax", "-starter")
EXCLUDED_CONTAINS = ("-totem",)
EXCLUDED_PREFIXES = ("pikachu-",)  # gorras y cosplay de Pikachu
EXCLUDED_NAMES = {
    "koraidon-limited-build", "koraidon-sprinting-build", "koraidon-swimming-build",
    "koraidon-gliding-build", "miraidon-low-power-mode", "miraidon-drive-mode",
    "miraidon-aquatic-mode", "miraidon-glide-mode",
}


def is_excluded(name: str) -> bool:
    return (
        name in EXCLUDED_NAMES
        or name.endswith(EXCLUDED_SUFFIXES)
        or any(s in name for s in EXCLUDED_CONTAINS)
        or name.startswith(EXCLUDED_PREFIXES)
    )


# --- Nombres legibles ---
_HYPHENATED_SPECIES = {"ho-oh", "porygon-z", "jangmo-o", "hakamo-o", "kommo-o"}
_FORM_LABELS = {
    "eternal": "Flor Eterna",
    "bloodmoon": "Luna Carmesí",
    "female": "Hembra",
    "male": "Macho",
    "origin": "Origen",
}


def _title(slug: str) -> str:
    if slug in _HYPHENATED_SPECIES:
        return "-".join(p.capitalize() for p in slug.split("-"))
    return " ".join(p.capitalize() for p in slug.split("-"))


def format_display_name(name: str, species: str | None) -> str:
    """'ursaluna-bloodmoon' + 'ursaluna' -> 'Ursaluna (Luna Carmesí)'."""
    if not species or name == species or not name.startswith(species + "-"):
        return _title(species or name)
    form = name[len(species) + 1:]
    return f"{_title(species)} ({_FORM_LABELS.get(form) or _title(form)})"


def _get(url, timeout):
    resp = _session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _id_from_url(url):
    return int(url.rstrip("/").split("/")[-1])


def _pick_sprite(sprites):
    other = sprites.get("other") or {}
    return (
        sprites.get("front_default")
        or (other.get("home") or {}).get("front_default")
        or (other.get("official-artwork") or {}).get("front_default")
    )


def _fetch_pokemon(base, poke_id, timeout):
    data = _get(f"{base}/pokemon/{poke_id}", timeout)
    types = [t["type"]["name"] for t in sorted(data["types"], key=lambda t: t["slot"])]
    return poke_id, types, _pick_sprite(data["sprites"]), data["species"]["name"]


def seed_pokemon(limit=None, workers=8, echo=print):
    """Llena/actualiza pokemon_cache. Es re-ejecutable: sólo descarga lo que falte.

    1) Índice de especies (1 petición) -> nombre de especie de los IDs 1..1025.
    2) Índice completo de Pokémon (1 petición) -> especies base + formas alternativas.
    3) Una petición por cada Pokémon al que le falten tipos o nombre (en paralelo).
    """
    cfg = current_app.config
    base, timeout = cfg["POKEAPI_BASE"], cfg["POKEAPI_TIMEOUT"]

    species_count = _get(f"{base}/pokemon-species?limit=1", timeout)["count"]
    species_idx = _get(f"{base}/pokemon-species?limit={species_count}", timeout)["results"]
    species_by_id = {_id_from_url(s["url"]): s["name"] for s in species_idx}

    total = limit or _get(f"{base}/pokemon?limit=1", timeout)["count"]
    index = _get(f"{base}/pokemon?limit={total}", timeout)["results"]

    existing = {p.pokeapi_id: p for p in PokemonCache.query.all()}
    wanted, pending, skipped = set(), [], 0
    for entry in index:
        name, poke_id = entry["name"], _id_from_url(entry["url"])
        if is_excluded(name):
            skipped += 1
            continue
        wanted.add(poke_id)
        row = existing.get(poke_id)
        if row is None:
            row = PokemonCache(pokeapi_id=poke_id, name=name)
            if poke_id in species_by_id:
                row.sprite_url = SPRITE_URL.format(id=poke_id)
            db.session.add(row)
            existing[poke_id] = row
        # Especies base: el nombre de especie sale del índice, sin petición extra.
        if not row.display_name and poke_id in species_by_id:
            row.display_name = format_display_name(name, species_by_id[poke_id])
        if not row.type_1 or not row.display_name:
            pending.append(poke_id)

    # Limpia formas que ahora estén excluidas, salvo que algún equipo las use.
    if not limit:
        used = {pid for (pid,) in db.session.query(TeamMember.pokeapi_id).distinct()}
        for pid, row in existing.items():
            if pid not in wanted and pid not in used:
                db.session.delete(row)
    db.session.commit()
    echo(f"Índice: {len(index)} entradas ({skipped} formas excluidas). "
         f"Por descargar: {len(pending)}.")

    done = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_fetch_pokemon, base, pid, timeout) for pid in pending]
        for fut in as_completed(futures):
            try:
                poke_id, types, sprite, species = fut.result()
            except Exception as exc:  # noqa: BLE001
                failed += 1
                echo(f"  ! error: {exc}")
                continue
            row = existing[poke_id]
            row.type_1 = types[0] if types else None
            row.type_2 = types[1] if len(types) > 1 else None
            row.sprite_url = sprite
            row.display_name = format_display_name(row.name, species)
            done += 1
            if done % 100 == 0:
                db.session.commit()
                echo(f"  {done}/{len(pending)}")
    db.session.commit()
    echo(f"Listo. {done} actualizados" + (f", {failed} fallaron (vuelve a ejecutar el comando)." if failed else "."))
    return done


@lru_cache(maxsize=512)
def _details_cached(base, poke_id, timeout):
    data = _get(f"{base}/pokemon/{poke_id}", timeout)
    return {
        "id": data["id"],
        "name": data["name"],
        "types": [t["type"]["name"] for t in sorted(data["types"], key=lambda t: t["slot"])],
        "abilities": [
            {"name": a["ability"]["name"], "hidden": a["is_hidden"]} for a in data["abilities"]
        ],
        "moves": sorted(m["move"]["name"] for m in data["moves"]),
        "sprite": _pick_sprite(data["sprites"]),
    }


def get_pokemon_details(poke_id):
    """Habilidades legales y movimientos; sólo se llama al seleccionar un Pokémon."""
    cfg = current_app.config
    return _details_cached(cfg["POKEAPI_BASE"], int(poke_id), cfg["POKEAPI_TIMEOUT"])
