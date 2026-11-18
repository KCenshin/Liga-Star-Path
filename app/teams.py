from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import POKEMON_TYPES, PokemonCache, Team, TeamMember
from .services.pokeapi import get_pokemon_details

bp = Blueprint("teams", __name__)

FORMATS = ("Singles 6v6", "Dobles VGC", "Singles 3v3", "Monotipo", "Libre")


def _own_team_or_404(team_id):
    team = db.session.get(Team, team_id)
    if team is None or team.user_id != current_user.id:
        abort(404)
    return team


def _parse_members(form):
    """Lee las 6 ranuras del formulario y valida contra la caché local."""
    members, errors = [], []
    for slot in range(1, 7):
        raw_id = form.get(f"slot{slot}_id", "").strip()
        if not raw_id:
            continue
        if not raw_id.isdigit():
            errors.append(f"Ranura {slot}: Pokémon inválido.")
            continue
        cache = db.session.get(PokemonCache, int(raw_id))
        if cache is None:
            errors.append(f"Ranura {slot}: el Pokémon no existe en la caché.")
            continue
        ability = form.get(f"slot{slot}_ability", "").strip()[:60] or None
        if ability:
            try:  # validar habilidad legal (si PokéAPI responde)
                legal = {a["name"] for a in get_pokemon_details(cache.pokeapi_id)["abilities"]}
                if ability not in legal:
                    errors.append(f"Ranura {slot}: {cache.name} no puede tener la habilidad '{ability}'.")
            except Exception:  # noqa: BLE001
                pass
        tera = form.get(f"slot{slot}_tera", "").strip().lower() or None
        if tera and tera not in POKEMON_TYPES:
            errors.append(f"Ranura {slot}: teratipo inválido.")
        members.append(TeamMember(
            pokeapi_id=cache.pokeapi_id,
            species_name=cache.name,
            nickname=form.get(f"slot{slot}_nickname", "").strip()[:30] or None,
            item=form.get(f"slot{slot}_item", "").strip()[:60] or None,
            ability=ability,
            tera_type=tera,
            slot_position=len(members) + 1,
        ))
    if not members:
        errors.append("El equipo necesita al menos 1 Pokémon.")
    return members, errors


def _initial_slots(team, form):
    """Datos iniciales de las 6 ranuras para el constructor (desde BD o desde un POST fallido)."""
    slots = []
    for slot in range(1, 7):
        if form is not None:
            raw = form.get(f"slot{slot}_id", "")
            cache = db.session.get(PokemonCache, int(raw)) if raw.isdigit() else None
            data = {k: form.get(f"slot{slot}_{k}", "") for k in ("nickname", "item", "ability", "tera")}
        else:
            m = team.members[slot - 1] if team and slot <= len(team.members) else None
            cache = m.cache if m else None
            data = {"nickname": m.nickname or "", "item": m.item or "",
                    "ability": m.ability or "", "tera": m.tera_type or ""} if m else {}
        slots.append({"pokemon": cache.to_dict() if cache else None, **data})
    return slots


@bp.route("/")
@login_required
def my_teams():
    return render_template("teams/list.html", teams=current_user.teams)


@bp.route("/nuevo", methods=["GET", "POST"])
@bp.route("/<int:team_id>/editar", methods=["GET", "POST"])
@login_required
def edit_team(team_id=None):
    team = _own_team_or_404(team_id) if team_id else None
    if request.method == "POST":
        name = request.form.get("team_name", "").strip()[:60]
        fmt = request.form.get("format_tag", "")
        members, errors = _parse_members(request.form)
        if not name:
            errors.append("Ponle nombre al equipo.")
        if fmt not in FORMATS:
            fmt = FORMATS[0]
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("teams/edit.html", team=team, formats=FORMATS,
                                   types=POKEMON_TYPES, form=request.form,
                                   slots=_initial_slots(team, request.form))
        if team is None:
            team = Team(user_id=current_user.id, is_active=not current_user.teams)
            db.session.add(team)
        team.team_name, team.format_tag = name, fmt
        team.members.clear()
        db.session.flush()  # libera las ranuras antes de reinsertar
        team.members.extend(members)
        db.session.commit()
        flash("Equipo guardado.", "success")
        return redirect(url_for("teams.my_teams"))
    return render_template("teams/edit.html", team=team, formats=FORMATS,
                           types=POKEMON_TYPES, form=None, slots=_initial_slots(team, None))


@bp.post("/<int:team_id>/activar")
@login_required
def activate(team_id):
    team = _own_team_or_404(team_id)
    for t in current_user.teams:
        t.is_active = t.id == team.id
    db.session.commit()
    flash(f"'{team.team_name}' es ahora tu equipo activo.", "success")
    return redirect(url_for("teams.my_teams"))


@bp.post("/<int:team_id>/eliminar")
@login_required
def delete(team_id):
    team = _own_team_or_404(team_id)
    db.session.delete(team)
    db.session.commit()
    flash("Equipo eliminado. (El Salón de la Fama conserva su propia copia.)", "info")
    return redirect(url_for("teams.my_teams"))
