import click

from .extensions import db
from .models import Badge, User

DEFAULT_BADGES = [
    ("Medalla Roca", "rock"),
    ("Medalla Cascada", "water"),
    ("Medalla Trueno", "electric"),
    ("Medalla Arcoíris", "grass"),
    ("Medalla Alma", "poison"),
    ("Medalla Pantano", "psychic"),
    ("Medalla Volcán", "fire"),
    ("Medalla Tierra", "ground"),
]


def register_cli(app):
    @app.cli.command("seed-pokemon")
    @click.option("--limit", type=int, default=None,
                  help="Sólo las primeras N entradas (por defecto todas, incluidas formas alternativas).")
    @click.option("--workers", type=int, default=8, help="Peticiones paralelas a PokéAPI.")
    def seed_pokemon_cmd(limit, workers):
        """Precarga Pokémon y formas alternativas (nombre, tipos, sprite) a pokemon_cache."""
        from .services.pokeapi import seed_pokemon

        seed_pokemon(limit=limit, workers=workers, echo=click.echo)

    @app.cli.command("seed-badges")
    def seed_badges_cmd():
        """Crea las 8 medallas base de la liga (sin líder asignado)."""
        created = 0
        for name, etype in DEFAULT_BADGES:
            if not Badge.query.filter_by(name=name).first():
                db.session.add(Badge(name=name, element_type=etype))
                created += 1
        db.session.commit()
        click.echo(f"{created} medallas creadas.")

    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin_cmd(username, email, password):
        """Crea (o promueve) un usuario Administrador."""
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, email=email.lower())
            user.set_password(password)
            db.session.add(user)
        user.role = "admin"
        db.session.commit()
        click.echo(f"'{username}' ahora es Administrador.")
