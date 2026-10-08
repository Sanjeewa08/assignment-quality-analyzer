import os
import secrets
import json
from pathlib import Path

import click
from flask import Flask
from dotenv import load_dotenv
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message = "Please sign in to continue."
csrf = CSRFProtect()


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    default_db = Path(__file__).resolve().parent.parent / "data" / "assignment_quality.db"
    default_db.parent.mkdir(parents=True, exist_ok=True)
    app.config.update(
        SECRET_KEY=os.environ.get("AQA_SECRET_KEY") or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", f"sqlite:///{default_db.as_posix()}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        UPLOAD_FOLDER=os.environ.get(
            "UPLOAD_FOLDER",
            str(Path(__file__).resolve().parent.parent / "uploads"),
        ),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_HTTPONLY=True,
    )
    if test_config:
        app.config.update(test_config)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models
    from .extractors.factory import ExtractorFactory
    from .routes import main

    app.extensions["extractor_extensions"] = ExtractorFactory.supported_extensions
    app.jinja_env.filters["fromjson"] = json.loads
    app.register_blueprint(main)

    @app.cli.command("init-db")
    def init_db():
        """Create the database tables."""
        with app.app_context():
            db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("create-lecturer")
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_lecturer(email, password):
        """Create a lecturer account without exposing role selection publicly."""
        from .models import User

        normalized = email.strip().lower()
        if "@" not in normalized or len(normalized) > 255:
            raise click.ClickException("Enter a valid email address.")
        if len(password) < 10:
            raise click.ClickException("Use a password with at least 10 characters.")
        if User.query.filter_by(email=normalized).first():
            raise click.ClickException("An account with that email already exists.")
        db.session.add(User(email=normalized, password_hash=User.hash_password(password), role="lecturer"))
        db.session.commit()
        click.echo(f"Lecturer account created for {normalized}.")

    @app.errorhandler(413)
    def request_too_large(_error):
        from flask import flash, redirect, request, url_for

        flash("That upload exceeds the 10 MB limit. Please choose a smaller file.", "error")
        return redirect(url_for("main.index"))

    return app
