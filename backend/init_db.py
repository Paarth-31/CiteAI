"""Initialise both PostgreSQL databases for CiteAI.

Run once after creating the Postgres databases:
    cd backend
    python init_db.py

Fixes in this version:
  1. Each extension gets its own AUTOCOMMIT connection so one failure
     does not abort the entire transaction and block the rest.
  2. pgvector must succeed before create_all — we abort with a clear
     message if it is not installed instead of silently continuing.
  3. PROCESSED_DIR path corrected to lexai/data/processed (not double-nested).
  4. db.engines compatibility for both Flask-SQLAlchemy 2.x and 3.x.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from sqlalchemy import text

from app import create_app
from app.extensions import db
from app.models import BaselineCase, User

# ── Paths ─────────────────────────────────────────────────────────────────────
BACKEND_ROOT  = Path(__file__).resolve().parent      # .../CiteAI/backend/
CITEAI_ROOT   = BACKEND_ROOT.parent                  # .../CiteAI/
PROCESSED_DIR = CITEAI_ROOT / "lexai" / "data" / "processed"

app = create_app()


# ── Engine helper ─────────────────────────────────────────────────────────────

def _get_engine(bind_key):
    """Compatible with Flask-SQLAlchemy 2.x and 3.x."""
    try:
        engine = db.engines.get(bind_key)
        if engine:
            return engine
    except AttributeError:
        pass
    try:
        return db.get_engine(bind=bind_key)
    except Exception:
        pass
    if bind_key is None:
        return db.engine
    raise RuntimeError(f"Cannot resolve engine for bind '{bind_key}'")


# ── Extension installer ───────────────────────────────────────────────────────

def enable_extension(engine, ext_name: str, label: str, required: bool = False) -> bool:
    """
    Install one PostgreSQL extension using AUTOCOMMIT isolation so that
    a failure does NOT abort the surrounding transaction and block the rest.

    Without AUTOCOMMIT: all 4 extensions share one transaction. When pgvector
    fails, PostgreSQL marks the transaction as aborted — every subsequent
    command in that transaction returns InFailedSqlTransaction regardless of
    whether it would have succeeded on its own.

    With AUTOCOMMIT: each extension is its own implicit transaction.
    A failure rolls back only that statement.
    """
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {ext_name}"))
        print(f"  ✓ {label}")
        return True
    except Exception as exc:
        print(f"  ✗ {label}: {exc}")
        if required:
            print(f"\n  FATAL: {ext_name} is required but not installed on the system.")
            print(f"  Fix:  sudo apt install postgresql-16-{ext_name}")
            print(f"        (replace 16 with your PostgreSQL version)")
            print(f"  Then retry: python init_db.py")
            sys.exit(1)
        return False
    finally:
        conn.close()


def enable_extensions(engine, db_name: str) -> None:
    """Install all extensions — each in its own autocommit connection."""
    print(f"\nEnabling extensions on {db_name}:")
    # pgvector is required — VECTOR columns in the documents table cannot
    # be created without it, so we exit immediately if it fails.
    enable_extension(engine, "vector",   "vector / pgvector  (vector similarity / embeddings)", required=True)
    enable_extension(engine, "pg_trgm",  "pg_trgm   (trigram similarity search)")
    enable_extension(engine, "unaccent", "unaccent  (accent-insensitive search)")
    enable_extension(engine, "pgcrypto", "pgcrypto  (gen_random_uuid)")


# ── FTS triggers ──────────────────────────────────────────────────────────────

def create_fts_triggers(conn) -> None:
    conn.execute(text("""
        CREATE OR REPLACE FUNCTION baseline_cases_fts_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.full_text_tsv :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.full_text, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    conn.execute(text("""
        DROP TRIGGER IF EXISTS trig_baseline_cases_fts ON baseline_cases;
        CREATE TRIGGER trig_baseline_cases_fts
        BEFORE INSERT OR UPDATE OF title, full_text ON baseline_cases
        FOR EACH ROW EXECUTE FUNCTION baseline_cases_fts_update();
    """))
    print("  ✓ baseline_cases FTS trigger")

    conn.execute(text("""
        CREATE OR REPLACE FUNCTION documents_fts_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.ocr_text_tsv :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.ocr_text, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    conn.execute(text("""
        DROP TRIGGER IF EXISTS trig_documents_fts ON documents;
        CREATE TRIGGER trig_documents_fts
        BEFORE INSERT OR UPDATE OF title, ocr_text ON documents
        FOR EACH ROW EXECUTE FUNCTION documents_fts_update();
    """))
    print("  ✓ documents FTS trigger")


# ── Seeding ───────────────────────────────────────────────────────────────────

def seed_demo_user() -> None:
    if User.query.filter_by(email="demo@example.com").first():
        print("  Demo user already exists — skipping.")
        return
    user = User(name="Demo User", email="demo@example.com")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    print("  ✓ demo@example.com / password123")


def _clean_title(raw: str) -> str:
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    for line in lines:
        if re.search(r"v\.|vs\.|versus", line, re.IGNORECASE):
            return line[:255]
    return lines[-1][:255] if lines else raw[:255]


def seed_baseline_cases() -> None:
    if not PROCESSED_DIR.exists():
        print(f"  WARNING: {PROCESSED_DIR} not found — skipping.")
        print(f"  Expected: CiteAI/lexai/data/processed/")
        return

    seeded = skipped = 0
    for json_file in sorted(PROCESSED_DIR.glob("*.json")):
        slug = json_file.stem
        if BaselineCase.query.filter_by(slug=slug).first():
            skipped += 1
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            raw_title = data.get("title") or slug.replace("_", " ").title()
            case = BaselineCase(
                slug      = slug,
                title     = _clean_title(raw_title),
                full_text = data.get("full_text") or "",
                citations = data.get("citations") or [],
                articles  = data.get("articles")  or [],
                keywords  = data.get("keywords")  or [],
                stats     = data.get("stats")     or {},
            )
            db.session.add(case)
            seeded += 1
            print(f"  ✓ {slug}")
        except Exception as exc:
            print(f"  ✗ ERROR {slug}: {exc}")

    db.session.commit()
    print(f"  {seeded} seeded, {skipped} already existed.")


# ── Main ──────────────────────────────────────────────────────────────────────

with app.app_context():

    # 1. Auth database
    print("\n=== citeai_auth ===")
    auth_engine = _get_engine("auth")
    enable_extensions(auth_engine, "citeai_auth")
    print("Creating tables...")
    db.create_all(bind_key="auth")
    print("  ✓ users")
    print("\nSeeding demo user...")
    seed_demo_user()

    # 2. Main database
    print("\n=== citeai_main ===")
    main_engine = _get_engine(None)
    enable_extensions(main_engine, "citeai_main")   # pgvector must succeed here
    print("Creating tables...")
    db.create_all(bind_key=None)
    print("  ✓ baseline_cases, documents, citations, chats, messages")

    # 3. FTS triggers
    print("\nInstalling FTS triggers...")
    with main_engine.begin() as conn:
        create_fts_triggers(conn)

    # 4. Baseline cases
    print("\nSeeding baseline cases...")
    seed_baseline_cases()

    print("\n✓ All done.")