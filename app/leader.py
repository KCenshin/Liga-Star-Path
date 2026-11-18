from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from .decorators import role_required
from .extensions import db
from .models import Badge, User, UserBadge

bp = Blueprint("leader", __name__)


def _badge_for_action(form_badge_id=None):
    """Líder: sólo su medalla. Admin: cualquier medalla elegida en el formulario."""
    if current_user.role == "admin":
        badge = db.session.get(Badge, int(form_badge_id)) if form_badge_id else None
    else:
        badge = current_user.led_badge
    if badge is None:
        abort(403)
    return badge


@bp.route("/")
@role_required("leader", "admin")
def panel():
    recent = []
    if current_user.led_badge:
        recent = (UserBadge.query.filter_by(badge_id=current_user.led_badge.id)
                  .order_by(UserBadge.awarded_at.desc()).limit(10).all())
    return render_template("leader/panel.html", recent=recent)


@bp.route("/retador/<int:user_id>")
@role_required("leader", "admin")
def challenger(user_id):
    target = db.session.get(User, user_id) or abort(404)
    earned = {ub.badge_id: ub for ub in target.user_badges}
    if current_user.role == "admin":
        badges = Badge.query.order_by(Badge.id).all()
    else:
        badges = [current_user.led_badge] if current_user.led_badge else []
    return render_template("leader/challenger.html", target=target, badges=badges, earned=earned)


@bp.post("/retador/<int:user_id>/otorgar")
@role_required("leader", "admin")
def award(user_id):
    target = db.session.get(User, user_id) or abort(404)
    badge = _badge_for_action(request.form.get("badge_id"))
    if target.id == current_user.id:
        flash("No puedes otorgarte medallas a ti mismo.", "danger")
        return redirect(url_for("leader.challenger", user_id=user_id))

    if UserBadge.query.filter_by(user_id=target.id, badge_id=badge.id).first():
        flash(f"{target.username} ya tiene la {badge.name}.", "warning")
    else:
        db.session.add(UserBadge(
            user_id=target.id, badge_id=badge.id, awarded_by_id=current_user.id,
            battle_notes=request.form.get("battle_notes", "").strip()[:255] or None,
        ))
        try:
            db.session.commit()
        except IntegrityError:  # doble clic / carrera: la restricción única lo impide
            db.session.rollback()
            flash(f"{target.username} ya tiene la {badge.name}.", "warning")
        else:
            db.session.refresh(target)
            msg = f"¡{badge.name} otorgada a {target.username}! ({target.badge_count}/{target.badges_needed})"
            if target.ready_for_elite_four:
                msg += " — ¡Ya puede retar al Alto Mando!"
            flash(msg, "success")
    return redirect(url_for("leader.challenger", user_id=user_id))


@bp.post("/retador/<int:user_id>/revocar")
@role_required("leader", "admin")
def revoke(user_id):
    badge = _badge_for_action(request.form.get("badge_id"))
    ub = UserBadge.query.filter_by(user_id=user_id, badge_id=badge.id).first_or_404()
    db.session.delete(ub)
    db.session.commit()
    flash(f"{badge.name} revocada.", "info")
    return redirect(url_for("leader.challenger", user_id=user_id))
