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
    """Seed the database with a demo user and sample document."""
    from app.models import Document, User

    if User.query.first() is not None:
        click.echo("Database already seeded.")
        return

    user = User(name="Demo User", email="demo@example.com")
    user.set_password("password123")

    document = Document(
        title="Sample Judgment",
        file_url="https://example.com/sample.pdf",
        file_size=1024,
        status="completed",
        user=user,
    )

    db.session.add_all([user, document])
    db.session.commit()
    click.echo("Seed data created — demo@example.com / password123")


@cli.command("warmup-models")
def warmup_models() -> None:
    """Pre-load InLegalBERT (and BioBERT if enabled) into the model registry.

    Run this once after starting the server if you want models loaded at
    startup rather than on the first request.
    """
    from app.extensions import model_registry

    click.echo("Loading InLegalBERT...")
    try:
        model_registry.get_legalbert_agent()
        click.echo("  InLegalBERT loaded.")
    except Exception as exc:
        click.echo(f"  InLegalBERT failed: {exc}")

    click.echo("Loading sentence-transformer...")
    try:
        model_registry.get_sentence_model()
        click.echo("  Sentence-transformer loaded.")
    except Exception as exc:
        click.echo(f"  Sentence-transformer failed: {exc}")

    if app.config.get("BIOBERT_ENABLED", False):
        click.echo("Loading BioBERT...")
        try:
            agent = model_registry.get_biobert_agent()
            if agent:
                click.echo(f"  BioBERT loaded: {agent.model_name}")
            else:
                click.echo("  BioBERT returned None (check BIOBERT_ENABLED).")
        except Exception as exc:
            click.echo(f"  BioBERT failed: {exc}")
    else:
        click.echo("  BioBERT skipped (BIOBERT_ENABLED not set).")

    click.echo(f"\nLoaded: {model_registry.loaded_models()}")


@cli.command("status")
def status() -> None:
    """Print app config summary and loaded model status."""
    click.echo(f"FLASK_CONFIG  : {app.config.get('ENV', 'development')}")
    click.echo(f"DATABASE_URI  : {app.config.get('SQLALCHEMY_DATABASE_URI', '—')}")
    click.echo(f"UPLOAD_FOLDER : {app.config.get('UPLOAD_FOLDER', '—')}")
    click.echo(f"FAISS_INDEX   : {app.config.get('FAISS_INDEX_DIR', '—')}")
    click.echo(f"MODEL_DEVICE  : {app.config.get('MODEL_DEVICE', 'auto')}")
    click.echo(f"LEGALBERT     : {app.config.get('LEGALBERT_MODEL_NAME', '—')}")
    click.echo(f"BIOBERT       : {'enabled — ' + app.config.get('BIOBERT_MODEL_NAME','') if app.config.get('BIOBERT_ENABLED') else 'disabled'}")

    from app.extensions import model_registry
    click.echo(f"Models loaded : {model_registry.loaded_models() or 'none yet'}")


if __name__ == "__main__":
    cli()
