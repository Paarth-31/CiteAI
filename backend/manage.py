"""Flask application management entry point."""
from __future__ import annotations

import click
from flask.cli import FlaskGroup

from app import create_app
from app.extensions import db

app = create_app()
cli = FlaskGroup(create_app=create_app)


@cli.command("seed")
def seed_database() -> None:
    """Seed the database with a demo user."""
    from app.models import User

    if User.query.first() is not None:
        click.echo("Database already seeded.")
        return

    user = User(name="Demo User", email="demo@example.com")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    # BUG FIX: removed Document(user=user) - Document has no `user` relationship.
    # Document.user_id is a plain string UUID column, not a relationship.
    # Use init_db.py instead for full seeding including baseline cases.
    click.echo(f"Demo user created: demo@example.com / password123 (id: {user.id})")


@cli.command("warmup-models")
def warmup_models() -> None:
    """Pre-load the canonical InLegalBERT and sentence-transformer encoders."""
    from app.extensions import model_registry

    click.echo("Loading InLegalBERT...")
    try:
        model_registry.get_legalbert_encoder()
        click.echo("  InLegalBERT loaded.")
    except Exception as exc:
        click.echo(f"  InLegalBERT failed: {exc}")

    click.echo("Loading sentence-transformer...")
    try:
        model_registry.get_sentence_model()
        click.echo("  Sentence-transformer loaded.")
    except Exception as exc:
        click.echo(f"  Sentence-transformer failed: {exc}")

    click.echo(f"\nLoaded: {model_registry.loaded_models()}")


@cli.command("status")
def status() -> None:
    """Print app config and loaded model status."""
    click.echo(f"DATABASE_URI  : {app.config.get('SQLALCHEMY_DATABASE_URI', '-')}")
    click.echo(f"AUTH_DB       : {app.config.get('SQLALCHEMY_BINDS', {}).get('auth', '-')}")
    click.echo(f"UPLOAD_FOLDER : {app.config.get('UPLOAD_FOLDER', '-')}")
    click.echo(f"MODEL_DEVICE  : {app.config.get('MODEL_DEVICE', 'auto')}")
    click.echo(f"LEGALBERT     : {app.config.get('LEGALBERT_MODEL_NAME', '-')}")

    from app.extensions import model_registry
    click.echo(f"Models loaded : {model_registry.loaded_models() or 'none yet'}")


# ``flask --app manage`` loads the ``app`` object, not the separate FlaskGroup
# below. Expose the same project commands through both entry points.
app.cli.add_command(seed_database)
app.cli.add_command(warmup_models)
app.cli.add_command(status)


if __name__ == "__main__":
    cli()
