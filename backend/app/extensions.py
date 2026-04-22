"""Flask extensions and model registry for CiteAI backend."""
from __future__ import annotations

import threading
from typing import Any

from flask import Flask
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# ── SQLAlchemy / auth extensions ──────────────────────────────────────────────
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
jwt = JWTManager()
cors = CORS()


# ── Model registry ─────────────────────────────────────────────────────────────
class ModelRegistry:
    """Thread-safe lazy loader for InLegalBERT, BioBERT, and sentence-transformers.

    Models are loaded once on first use and reused for every subsequent
    request, eliminating the per-request reload bottleneck.

    Usage:
        from app.extensions import model_registry
        agent = model_registry.get_legalbert_agent()
        st_model = model_registry.get_sentence_model()
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._legalbert_agent: Any | None = None
        self._biobert_agent: Any | None = None
        self._sentence_model: Any | None = None
        self._app: Flask | None = None

    def init_app(self, app: Flask) -> None:
        self._app = app

    # ── InLegalBERT ────────────────────────────────────────────────────────
    def get_legalbert_agent(self):
        """Return a cached InLegalBERTExternalAgent, loading on first call."""
        if self._legalbert_agent is not None:
            return self._legalbert_agent

        with self._lock:
            # Double-check after acquiring lock
            if self._legalbert_agent is not None:
                return self._legalbert_agent

            import sys
            from pathlib import Path

            if self._app:
                project_root = Path(self._app.root_path).parent.parent
                root_str = str(project_root)
                if root_str not in sys.path:
                    sys.path.insert(0, root_str)

            from lexai.agents.inlegalbert_external_agent import InLegalBERTExternalAgent

            device = self._resolve_device()
            model_name = (
                self._app.config.get("LEGALBERT_MODEL_NAME", "law-ai/InLegalBERT")
                if self._app else "law-ai/InLegalBERT"
            )
            max_length = int(
                self._app.config.get("LEGALBERT_MAX_LENGTH", 512)
                if self._app else 512
            )

            self._legalbert_agent = InLegalBERTExternalAgent(
                model_name=model_name,
                device=device,
                max_length=max_length,
            )
            return self._legalbert_agent

    # ── BioBERT ────────────────────────────────────────────────────────────
    def get_biobert_agent(self):
        """Return a cached BioBERT agent.

        Returns None if BIOBERT_ENABLED is not set — the team will wire this
        in once the updated FAISS integration is ready.
        """
        if self._app and not self._app.config.get("BIOBERT_ENABLED", False):
            return None

        if self._biobert_agent is not None:
            return self._biobert_agent

        with self._lock:
            if self._biobert_agent is not None:
                return self._biobert_agent

            # TODO: Replace with team's updated BioBERT + FAISS agent once ready.
            # The agent class is expected to follow the same interface as
            # InLegalBERTExternalAgent (load_dataset, compute_all_embeddings,
            # retrieve_similar_cases, generate_reasoning_output).
            try:
                import sys
                from pathlib import Path

                if self._app:
                    project_root = Path(self._app.root_path).parent.parent
                    root_str = str(project_root)
                    if root_str not in sys.path:
                        sys.path.insert(0, root_str)

                from transformers import AutoModel, AutoTokenizer

                device = self._resolve_device()
                model_name = (
                    self._app.config.get("BIOBERT_MODEL_NAME", "dmis-lab/biobert-base-cased-v1.2")
                    if self._app else "dmis-lab/biobert-base-cased-v1.2"
                )

                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModel.from_pretrained(model_name)

                # Wrap in a lightweight namespace so callers can access
                # tokenizer and model directly until the full agent is wired in.
                class _BioBERTHandle:
                    def __init__(self, tok, mdl, dev):
                        self.tokenizer = tok
                        self.model = mdl
                        self.device = dev
                        self.model_name = model_name
                        self.model.to(dev)
                        self.model.eval()

                self._biobert_agent = _BioBERTHandle(tokenizer, model, device)
            except Exception as exc:
                if self._app:
                    self._app.logger.warning("BioBERT failed to load: %s", exc)
                return None

            return self._biobert_agent

    # ── Sentence-transformer ───────────────────────────────────────────────
    def get_sentence_model(self):
        """Return a cached SentenceTransformer (used by ExternalInferenceAgent)."""
        if self._sentence_model is not None:
            return self._sentence_model

        with self._lock:
            if self._sentence_model is not None:
                return self._sentence_model

            from sentence_transformers import SentenceTransformer

            model_name = (
                self._app.config.get(
                    "SENTENCE_MODEL_NAME",
                    "sentence-transformers/all-MiniLM-L6-v2",
                )
                if self._app
                else "sentence-transformers/all-MiniLM-L6-v2"
            )
            device = self._resolve_device()
            self._sentence_model = SentenceTransformer(model_name, device=device)
            return self._sentence_model

    # ── Helpers ────────────────────────────────────────────────────────────
    def _resolve_device(self) -> str:
        setting = (
            self._app.config.get("MODEL_DEVICE", "auto") if self._app else "auto"
        )
        if setting != "auto":
            return setting
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def loaded_models(self) -> list[str]:
        """Return names of currently loaded models (for /health endpoint)."""
        loaded = []
        if self._legalbert_agent is not None:
            loaded.append("legalbert")
        if self._biobert_agent is not None:
            loaded.append("biobert")
        if self._sentence_model is not None:
            loaded.append("sentence-transformer")
        return loaded


model_registry = ModelRegistry()


# ── Extension initialisation ────────────────────────────────────────────────
def init_extensions(app: Flask) -> None:
    """Bind all extensions to the Flask app instance."""
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)

    # Single CORS setup — Flask-CORS handles all /api/* preflight and headers.
    # The duplicate after_request CORS block in the old __init__.py is removed.
    origins = [
        o.strip()
        for o in app.config.get("CORS_ORIGINS", "*").split(",")
        if o.strip()
    ]
    cors.init_app(
        app,
        resources={
            r"/api/*": {
                "origins": origins,
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
                "supports_credentials": True,
            }
        },
    )

    model_registry.init_app(app)

    # Lazy model import — prevents circular imports
    from . import models  # noqa: F401

    @jwt.user_lookup_loader
    def _load_user(_jwt_header, jwt_data):
        from .models import User
        identity = jwt_data.get("sub")
        if identity is None:
            return None
        return User.query.filter_by(id=identity).one_or_none()

    @jwt.expired_token_loader
    def _expired_token(_jwt_header, _jwt_data):
        from flask import jsonify
        from http import HTTPStatus
        return jsonify({"error": "Token has expired"}), HTTPStatus.UNAUTHORIZED

    @jwt.invalid_token_loader
    def _invalid_token(reason: str):
        from flask import jsonify
        from http import HTTPStatus
        return jsonify({"error": f"Invalid token: {reason}"}), HTTPStatus.UNAUTHORIZED
