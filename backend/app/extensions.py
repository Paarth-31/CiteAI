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

# ── Core extensions ───────────────────────────────────────────────────────────
db      = SQLAlchemy()
migrate = Migrate()
bcrypt  = Bcrypt()
jwt     = JWTManager()
cors    = CORS()


# ── Model registry ─────────────────────────────────────────────────────────────
class ModelRegistry:
    """Thread-safe lazy loader for InLegalBERT, BioBERT, and sentence-transformers."""

    def __init__(self) -> None:
        self._lock             = threading.Lock()
        self._legalbert_agent: Any | None = None
        self._biobert_agent:   Any | None = None
        self._sentence_model:  Any | None = None
        self._app: Flask | None = None

    def init_app(self, app: Flask) -> None:
        self._app = app

    # ── InLegalBERT ────────────────────────────────────────────────────────
    def get_legalbert_agent(self):
        if self._legalbert_agent is not None:
            return self._legalbert_agent
        with self._lock:
            if self._legalbert_agent is not None:
                return self._legalbert_agent
            import sys
            from pathlib import Path
            if self._app:
                project_root = Path(self._app.root_path).parent.parent
                for p in [str(project_root), str(project_root / "lexai")]:
                    if p not in sys.path:
                        sys.path.insert(0, p)
            from lexai.agents.inlegalbert_external_agent import InLegalBERTExternalAgent
            device     = self._resolve_device()
            model_name = self._app.config.get("LEGALBERT_MODEL_NAME", "law-ai/InLegalBERT") if self._app else "law-ai/InLegalBERT"
            max_length = int(self._app.config.get("LEGALBERT_MAX_LENGTH", 512) if self._app else 512)
            self._legalbert_agent = InLegalBERTExternalAgent(
                model_name=model_name, device=device, max_length=max_length,
            )
            return self._legalbert_agent

    # ── BioBERT ────────────────────────────────────────────────────────────
    def get_biobert_agent(self):
        if self._app and not self._app.config.get("BIOBERT_ENABLED", False):
            return None
        if self._biobert_agent is not None:
            return self._biobert_agent
        with self._lock:
            if self._biobert_agent is not None:
                return self._biobert_agent
            try:
                import sys
                from pathlib import Path
                if self._app:
                    project_root = Path(self._app.root_path).parent.parent
                    for p in [str(project_root), str(project_root / "lexai")]:
                        if p not in sys.path:
                            sys.path.insert(0, p)
                from transformers import AutoModel, AutoTokenizer
                device     = self._resolve_device()
                model_name = self._app.config.get("BIOBERT_MODEL_NAME", "dmis-lab/biobert-base-cased-v1.2") if self._app else "dmis-lab/biobert-base-cased-v1.2"
                tokenizer  = AutoTokenizer.from_pretrained(model_name)
                model      = AutoModel.from_pretrained(model_name)

                class _BioBERTHandle:
                    def __init__(self, tok, mdl, dev):
                        self.tokenizer = tok; self.model = mdl; self.device = dev
                        self.model_name = model_name
                        self.model.to(dev); self.model.eval()

                self._biobert_agent = _BioBERTHandle(tokenizer, model, device)
            except Exception as exc:
                if self._app:
                    self._app.logger.warning("BioBERT failed to load: %s", exc)
                return None
            return self._biobert_agent

    # ── Sentence-transformer ───────────────────────────────────────────────
    def get_sentence_model(self):
        if self._sentence_model is not None:
            return self._sentence_model
        with self._lock:
            if self._sentence_model is not None:
                return self._sentence_model
            from sentence_transformers import SentenceTransformer
            model_name = self._app.config.get("SENTENCE_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2") if self._app else "sentence-transformers/all-MiniLM-L6-v2"
            self._sentence_model = SentenceTransformer(model_name, device=self._resolve_device())
            return self._sentence_model

    # ── Helpers ────────────────────────────────────────────────────────────
    def _resolve_device(self) -> str:
        setting = self._app.config.get("MODEL_DEVICE", "auto") if self._app else "auto"
        if setting != "auto":
            return setting
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def loaded_models(self) -> list[str]:
        loaded = []
        if self._legalbert_agent is not None: loaded.append("legalbert")
        if self._biobert_agent   is not None: loaded.append("biobert")
        if self._sentence_model  is not None: loaded.append("sentence-transformer")
        return loaded


model_registry = ModelRegistry()


# ── Extension initialisation ──────────────────────────────────────────────────
def init_extensions(app: Flask) -> None:
    """Bind all extensions to the Flask app instance."""
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)

    origins = [o.strip() for o in app.config.get("CORS_ORIGINS", "*").split(",") if o.strip()]
    cors.init_app(
        app,
        resources={
            r"/api/*": {
                "origins":           origins,
                "methods":           ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers":     ["Content-Type", "Authorization", "X-Requested-With"],
                "supports_credentials": True,
            }
        },
    )

    model_registry.init_app(app)
    from . import models  # noqa: F401

    @jwt.user_lookup_loader
    def _load_user(_jwt_header, jwt_data):
        from .models import User
        identity = jwt_data.get("sub")
        if identity is None:
            return None
        # User lives in citeai_auth (bind_key="auth")
        # SQLAlchemy routes this query to the auth engine automatically
        try:
            import uuid
            identity_val = uuid.UUID(str(identity)) if identity else None
        except (ValueError, AttributeError):
            identity_val = identity
        return User.query.filter_by(id=identity_val).one_or_none()

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
