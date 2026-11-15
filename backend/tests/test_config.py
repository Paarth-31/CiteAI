"""Database URL driver selection must not depend on SQLAlchemy defaults."""

from app.config import _postgresql_url


def test_bare_postgresql_url_uses_installed_driver():
    assert _postgresql_url("postgresql://user:pass@localhost:5432/db") == (
        "postgresql+psycopg2://user:pass@localhost:5432/db"
    )


def test_explicit_postgresql_driver_is_preserved():
    url = "postgresql+psycopg://user:pass@localhost:5432/db"
    assert _postgresql_url(url) == url
