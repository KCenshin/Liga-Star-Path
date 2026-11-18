from datetime import datetime, timezone

from flask import current_app, url_for
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

ROLES = ("challenger", "leader", "elite_four", "admin")
ROLE_LABELS = {
    "challenger": "Retador",
    "leader": "Líder de Gimnasio",
    "elite_four": "Alto Mando",
    "admin": "Administrador",
}
ROLE_COLORS = {
    "challenger": "#3b82f6",
    "leader": "#22c55e",
    "elite_four": "#a855f7",
    "admin": "#ef4444",
}
POKEMON_TYPES = (
    "normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison",
    "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark",
    "steel", "fairy", "stellar",
)


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="challenger")
    avatar_filename = db.Column(db.String(64))
    trainer_title = db.Column(db.String(60))
    friend_code = db.Column(db.String(32))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    teams = db.relationship("Team", back_populates="user", cascade="all, delete-orphan")
    user_badges = db.relationship(
        "UserBadge", foreign_keys="UserBadge.user_id", back_populates="user",
        cascade="all, delete-orphan",
    )
    led_badge = db.relationship("Badge", back_populates="leader", uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles):
        return self.role in roles

    @property
    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def role_color(self):
        return ROLE_COLORS.get(self.role, "#64748b")

    @property
    def avatar_url(self):
        if self.avatar_filename:
            return url_for("main.avatar_file", filename=self.avatar_filename)
        return url_for("static", filename="img/default_avatar.svg")

    @property
    def active_team(self):
        return next((t for t in self.teams if t.is_active), None)

    @property
    def badge_count(self):
        return len(self.user_badges)

    @property
    def badges_needed(self):
        return current_app.config["BADGES_FOR_ELITE_FOUR"]

    @property
    def ready_for_elite_four(self):
        return self.badge_count >= self.badges_needed


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Badge(db.Model):
    __tablename__ = "badges"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    element_type = db.Column(db.String(16), nullable=False)
    image_url = db.Column(db.String(255))
    leader_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), unique=True)

    leader = db.relationship("User", back_populates="led_badge")


class UserBadge(db.Model):
    __tablename__ = "user_badges"
    __table_args__ = (db.UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey("badges.id", ondelete="CASCADE"), nullable=False)
    awarded_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    awarded_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    battle_notes = db.Column(db.String(255))

    user = db.relationship("User", foreign_keys=[user_id], back_populates="user_badges")
    badge = db.relationship("Badge")
    awarded_by = db.relationship("User", foreign_keys=[awarded_by_id])


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team_name = db.Column(db.String(60), nullable=False)
    format_tag = db.Column(db.String(30), default="Singles 6v6")
    is_active = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="teams")
    members = db.relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan",
        order_by="TeamMember.slot_position",
    )

    def snapshot(self):
        """Instantánea inmutable del equipo (para el Salón de la Fama)."""
        out = []
        for m in self.members:
            cache = db.session.get(PokemonCache, m.pokeapi_id)
            out.append({
                "slot": m.slot_position,
                "pokeapi_id": m.pokeapi_id,
                "species": m.species_name,
                "display_name": cache.label if cache else m.species_name,
                "nickname": m.nickname,
                "item": m.item,
                "ability": m.ability,
                "tera_type": m.tera_type,
                "sprite_url": cache.sprite_url if cache else None,
                "types": [t for t in ((cache.type_1, cache.type_2) if cache else ()) if t],
            })
        return {"team_name": self.team_name, "format_tag": self.format_tag, "members": out}


class TeamMember(db.Model):
    __tablename__ = "team_members"
    __table_args__ = (
        db.UniqueConstraint("team_id", "slot_position", name="uq_team_slot"),
        db.CheckConstraint("slot_position BETWEEN 1 AND 6", name="ck_slot_range"),
    )

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    pokeapi_id = db.Column(db.Integer, nullable=False)
    species_name = db.Column(db.String(60), nullable=False)
    nickname = db.Column(db.String(30))
    item = db.Column(db.String(60))
    ability = db.Column(db.String(60))
    tera_type = db.Column(db.String(16))
    slot_position = db.Column(db.Integer, nullable=False)

    team = db.relationship("Team", back_populates="members")

    @property
    def cache(self):
        return db.session.get(PokemonCache, self.pokeapi_id)

    @property
    def label(self):
        c = self.cache
        return c.label if c else self.species_name.replace("-", " ").title()


class PokemonCache(db.Model):
    __tablename__ = "pokemon_cache"

    pokeapi_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    name = db.Column(db.String(60), nullable=False, index=True)  # slug de PokéAPI
    display_name = db.Column(db.String(80))  # ej. "Ursaluna (Luna Carmesí)"
    type_1 = db.Column(db.String(16))
    type_2 = db.Column(db.String(16))
    sprite_url = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    @property
    def label(self):
        return self.display_name or self.name.replace("-", " ").title()

    @property
    def is_alt_form(self):
        return self.pokeapi_id >= 10000

    def to_dict(self):
        return {
            "id": self.pokeapi_id,
            "name": self.name,
            "display": self.label,
            "alt_form": self.is_alt_form,
            "types": [t for t in (self.type_1, self.type_2) if t],
            "sprite": self.sprite_url,
        }


class HallOfFame(db.Model):
    __tablename__ = "hall_of_fame"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    # Copia del nombre/avatar al momento de ingresar, para no depender de datos vivos.
    trainer_name_snapshot = db.Column(db.String(32), nullable=False)
    avatar_snapshot = db.Column(db.String(64))  # copia física del avatar
    season_title = db.Column(db.String(80), nullable=False)
    inducted_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    champion_team_snapshot = db.Column(db.JSON, nullable=False)
    admin_notes = db.Column(db.Text)

    user = db.relationship("User")
