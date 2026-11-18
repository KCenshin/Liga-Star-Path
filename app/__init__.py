import os

from flask import Flask

from config import Config

from .extensions import csrf, db, login_manager


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)
    if os.environ.get("DATA_DIR"):
        os.makedirs(os.environ["DATA_DIR"], exist_ok=True)
    os.makedirs(app.config["AVATAR_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401  (registra modelos)
    from .admin import bp as admin_bp
    from .api import bp as api_bp
    from .auth import bp as auth_bp
    from .leader import bp as leader_bp
    from .main import bp as main_bp
    from .teams import bp as teams_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(teams_bp, url_prefix="/equipos")
    app.register_blueprint(leader_bp, url_prefix="/lider")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")

    from .cli import register_cli

    register_cli(app)

    from .models import ROLE_COLORS, ROLE_LABELS

    @app.context_processor
    def inject_roles():
        return {"ROLE_LABELS": ROLE_LABELS, "ROLE_COLORS": ROLE_COLORS}

    with app.app_context():
        db.create_all()
        _add_missing_columns()

    return app


def _add_missing_columns():
    """Migración mínima: agrega columnas nuevas a tablas existentes sin perder datos."""
    from sqlalchemy import inspect, text

    new_columns = {"pokemon_cache": {"display_name": "VARCHAR(80)"}}
    insp = inspect(db.engine)
    with db.engine.begin() as conn:
        for table, cols in new_columns.items():
            present = {c["name"] for c in insp.get_columns(table)}
            for col, ddl in cols.items():
                if col not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
