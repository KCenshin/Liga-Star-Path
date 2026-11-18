from flask import (Blueprint, current_app, flash, redirect, render_template, request,
                   send_from_directory, url_for)
from flask_login import current_user, login_required

from .extensions import db
from .models import Badge, HallOfFame, User
from .services.avatars import AvatarError, save_avatar

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    badges = Badge.query.order_by(Badge.id).all()
    leaders = User.query.filter_by(role="leader").all()
    elite = User.query.filter_by(role="elite_four").all()
    champions = HallOfFame.query.order_by(HallOfFame.inducted_at.desc()).limit(3).all()
    return render_template("index.html", badges=badges, leaders=leaders,
                           elite=elite, champions=champions)


@bp.route("/entrenadores")
def trainers():
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        query = query.filter(User.username.ilike(f"%{q}%"))
    users = query.order_by(User.username).limit(100).all()
    return render_template("trainers.html", users=users, q=q)


@bp.route("/entrenador/<username>")
def trainer_card(username):
    user = User.query.filter_by(username=username).first_or_404()
    badges = Badge.query.order_by(Badge.id).all()
    earned = {ub.badge_id: ub for ub in user.user_badges}
    return render_template("trainer_card.html", user=user, badges=badges, earned=earned)


@bp.route("/perfil", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        current_user.trainer_title = request.form.get("trainer_title", "").strip()[:60] or None
        current_user.friend_code = request.form.get("friend_code", "").strip()[:32] or None

        avatar = request.files.get("avatar")
        if avatar and avatar.filename:
            try:
                current_user.avatar_filename = save_avatar(avatar, current_user.avatar_filename)
            except AvatarError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("main.edit_profile"))
        db.session.commit()
        flash("Perfil actualizado.", "success")
        return redirect(url_for("main.trainer_card", username=current_user.username))
    return render_template("profile_edit.html")


@bp.route("/media/avatars/<path:filename>")
def avatar_file(filename):
    """Sirve avatares desde AVATAR_FOLDER (puede estar en un disco persistente fuera de /static)."""
    return send_from_directory(current_app.config["AVATAR_FOLDER"], filename, max_age=3600)


@bp.route("/salon-de-la-fama")
def hall_of_fame():
    entries = HallOfFame.query.order_by(HallOfFame.inducted_at.desc()).all()
    return render_template("hall_of_fame.html", entries=entries)


@bp.app_errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, msg="No tienes permiso para ver esto."), 403


@bp.app_errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, msg="Esta ruta no existe... ¡aún!"), 404


@bp.app_errorhandler(413)
def too_large(_e):
    return render_template("error.html", code=413, msg="El archivo es demasiado grande."), 413
