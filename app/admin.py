from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .decorators import role_required
from .extensions import db
from .models import POKEMON_TYPES, ROLES, Badge, HallOfFame, Team, User
from .services.avatars import delete_avatar, snapshot_avatar

bp = Blueprint("admin", __name__)


@bp.route("/")
@role_required("admin")
def dashboard():
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        query = query.filter(User.username.ilike(f"%{q}%"))
    users = query.order_by(User.role, User.username).all()
    badges = Badge.query.order_by(Badge.id).all()
    leaders = User.query.filter_by(role="leader").order_by(User.username).all()
    hof = HallOfFame.query.order_by(HallOfFame.inducted_at.desc()).all()
    return render_template("admin/dashboard.html", users=users, badges=badges, leaders=leaders,
                           hof=hof, roles=ROLES, types=POKEMON_TYPES, q=q)


@bp.post("/usuarios/<int:user_id>/rol")
@role_required("admin")
def change_role(user_id):
    user = db.session.get(User, user_id) or abort(404)
    role = request.form.get("role")
    if role not in ROLES:
        abort(400)
    if user.role == "admin" and role != "admin" and User.query.filter_by(role="admin").count() == 1:
        flash("No puedes quitar al último administrador.", "danger")
        return redirect(url_for("admin.dashboard"))
    if user.role == "leader" and role != "leader" and user.led_badge:
        user.led_badge.leader_id = None  # libera la medalla
    user.role = role
    db.session.commit()
    flash(f"{user.username} ahora es {user.role_label}.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/medallas")
@role_required("admin")
def save_badge():
    badge_id = request.form.get("badge_id")
    badge = db.session.get(Badge, int(badge_id)) if badge_id else Badge()
    if badge is None:
        abort(404)
    name = request.form.get("name", "").strip()[:60]
    etype = request.form.get("element_type", "")
    if not name or etype not in POKEMON_TYPES:
        flash("Nombre y tipo de medalla son obligatorios.", "danger")
        return redirect(url_for("admin.dashboard"))
    badge.name, badge.element_type = name, etype
    badge.image_url = request.form.get("image_url", "").strip()[:255] or None

    leader_id = request.form.get("leader_id")
    if leader_id:
        leader = db.session.get(User, int(leader_id))
        if leader is None or leader.role != "leader":
            flash("Sólo un Líder de Gimnasio puede custodiar una medalla.", "danger")
            return redirect(url_for("admin.dashboard"))
        other = Badge.query.filter(Badge.leader_id == leader.id, Badge.id != badge.id).first()
        if other:
            other.leader_id = None  # un líder = una medalla
            db.session.flush()
        badge.leader_id = leader.id
    else:
        badge.leader_id = None
    if badge.id is None:
        db.session.add(badge)
    db.session.commit()
    flash(f"Medalla '{badge.name}' guardada.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.post("/medallas/<int:badge_id>/eliminar")
@role_required("admin")
def delete_badge(badge_id):
    badge = db.session.get(Badge, badge_id) or abort(404)
    db.session.delete(badge)
    db.session.commit()
    flash("Medalla eliminada.", "info")
    return redirect(url_for("admin.dashboard"))


@bp.route("/salon-de-la-fama/nuevo", methods=["GET", "POST"])
@role_required("admin")
def induct():
    if request.method == "POST":
        user = db.session.get(User, int(request.form.get("user_id", 0) or 0))
        team = db.session.get(Team, int(request.form.get("team_id", 0) or 0))
        season = request.form.get("season_title", "").strip()[:80]
        if not user or not team or team.user_id != user.id or not season:
            flash("Selecciona campeón, uno de sus equipos y el título de temporada.", "danger")
            return redirect(url_for("admin.induct"))
        db.session.add(HallOfFame(
            user_id=user.id,
            trainer_name_snapshot=user.username,
            avatar_snapshot=snapshot_avatar(user.avatar_filename),
            season_title=season,
            champion_team_snapshot=team.snapshot(),
            admin_notes=request.form.get("admin_notes", "").strip() or None,
        ))
        db.session.commit()
        flash(f"¡{user.username} entra al Salón de la Fama!", "success")
        return redirect(url_for("main.hall_of_fame"))

    users = [u for u in User.query.order_by(User.username).all() if u.teams]
    teams_by_user = {u.id: [[t.id, t.team_name, t.is_active] for t in u.teams] for u in users}
    return render_template("admin/induct.html", users=users, teams_by_user=teams_by_user)


@bp.post("/salon-de-la-fama/<int:entry_id>/eliminar")
@role_required("admin")
def delete_hof(entry_id):
    entry = db.session.get(HallOfFame, entry_id) or abort(404)
    if entry.avatar_snapshot:
        delete_avatar(entry.avatar_snapshot)
    db.session.delete(entry)
    db.session.commit()
    flash("Registro eliminado del Salón de la Fama.", "info")
    return redirect(url_for("admin.dashboard"))


@bp.app_template_global()
def is_admin():
    return current_user.is_authenticated and current_user.role == "admin"
