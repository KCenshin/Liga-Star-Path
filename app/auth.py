import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import User

bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else None


@bp.route("/registro", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        errors = []
        if not USERNAME_RE.match(username):
            errors.append("El usuario debe tener 3-32 caracteres (letras, números o _).")
        if not EMAIL_RE.match(email):
            errors.append("Correo inválido.")
        if len(password) < 8:
            errors.append("La contraseña debe tener al menos 8 caracteres.")
        if User.query.filter(db.func.lower(User.username) == username.lower()).first():
            errors.append("Ese nombre de usuario ya existe.")
        if User.query.filter_by(email=email).first():
            errors.append("Ese correo ya está registrado.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", username=username, email=email)

        user = User(username=username, email=email, role="challenger")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("¡Bienvenido a la Liga, entrenador!", "success")
        return redirect(url_for("main.edit_profile"))
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        ident = request.form.get("username", "").strip()
        user = User.query.filter(
            (db.func.lower(User.username) == ident.lower()) | (User.email == ident.lower())
        ).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user, remember=bool(request.form.get("remember")))
            return redirect(_safe_next(request.args.get("next")) or url_for("main.index"))
        flash("Usuario o contraseña incorrectos.", "danger")
    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("main.index"))
