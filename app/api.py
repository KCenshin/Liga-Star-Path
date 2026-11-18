from flask import Blueprint, jsonify, request

from .decorators import role_required
from .extensions import db
from .models import PokemonCache, User
from .services.pokeapi import get_pokemon_details

bp = Blueprint("api", __name__)


@bp.get("/pokemon/search")
def pokemon_search():
    """Autocompletado local: consulta sólo la tabla pokemon_cache (sin llamar a PokéAPI)."""
    q = request.args.get("q", "").strip().lower()
    if len(q) < 2 and not q.isdigit():
        return jsonify([])
    if q.isdigit():
        rows = PokemonCache.query.filter_by(pokeapi_id=int(q)).all()
    else:
        starts = PokemonCache.query.filter(PokemonCache.name.like(f"{q}%"))
        rows = starts.order_by(PokemonCache.pokeapi_id).limit(10).all()
        if len(rows) < 10:
            ids = [r.pokeapi_id for r in rows]
            # Coincidencia parcial en el slug o en el nombre legible ("luna carmesí", "alola"...)
            rows += (PokemonCache.query
                     .filter((PokemonCache.name.like(f"%{q.replace(' ', '-')}%"))
                             | PokemonCache.display_name.ilike(f"%{q}%"),
                             ~PokemonCache.pokeapi_id.in_(ids or [0]))
                     .order_by(PokemonCache.pokeapi_id).limit(10 - len(rows)).all())
    return jsonify([r.to_dict() for r in rows])


@bp.get("/pokemon/<int:poke_id>")
def pokemon_details(poke_id):
    """Detalles bajo demanda (habilidades y movimientos) al seleccionar un Pokémon."""
    if not db.session.get(PokemonCache, poke_id):
        return jsonify({"error": "Pokémon no encontrado en la caché local"}), 404
    try:
        return jsonify(get_pokemon_details(poke_id))
    except Exception:  # noqa: BLE001
        return jsonify({"error": "PokéAPI no disponible en este momento"}), 502


@bp.get("/users/search")
@role_required("leader", "admin")
def users_search():
    """Buscador rápido de retadores para el panel del Líder (por usuario o ID)."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    query = User.query
    if q.isdigit():
        query = query.filter((User.id == int(q)) | User.username.ilike(f"%{q}%"))
    else:
        query = query.filter(User.username.ilike(f"%{q}%"))
    users = query.order_by(User.username).limit(10).all()
    return jsonify([
        {"id": u.id, "username": u.username, "role": u.role_label,
         "avatar": u.avatar_url, "badges": u.badge_count}
        for u in users
    ])
