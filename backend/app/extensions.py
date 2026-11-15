"""Flask extensions and model registry for CiteAI backend."""
from __future__ import annotations

import threading
from typing import Any

import numpy as np

from flask import Flask
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

# ── Core extensions ───────────────────────────────────────────────────────────
db      = SQLAlchemy()
bcrypt  = Bcrypt()
jwt     = JWTManager()
cors    = CORS()


# ── Model registry ─────────────────────────────────────────────────────────────
class InLegalBERTEncoder:
    """Small backend-owned InLegalBERT encoder with masked mean pooling."""

    def __init__(self, model_name: str, device: str, max_length: int) -> None:
        from transformers import AutoModel, AutoTokenizer
        self.model_name = model_name
        self.device = device
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(device)
        self.model.eval()

    def encode(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        import torch
        result = []
        for start in range(0, len(texts), batch_size):
            tokens = self.tokenizer(texts[start:start + batch_size], return_tensors="pt", truncation=True,
                                    max_length=self.max_length, padding=True)
            tokens = {key: value.to(self.device) for key, value in tokens.items()}
            with torch.no_grad():
                hidden = self.model(**tokens).last_hidden_state
            mask = tokens["attention_mask"].unsqueeze(-1).expand_as(hidden).float()
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
            values = pooled.detach().cpu().numpy()
            result.extend(values / (np.linalg.norm(values, axis=1, keepdims=True) + 1e-12))
        return np.asarray(result, dtype=np.float32)


class ModelRegistry:
    """Thread-safe lazy loader for the two canonical backend encoders."""

    def __init__(self) -> None:
        self._lock             = threading.Lock()
        self._legalbert_encoder: Any | None = None
        self._sentence_model:  Any | None = None
        self._app: Flask | None = None

    def init_app(self, app: Flask) -> None:
        self._app = app

    # ── InLegalBERT ────────────────────────────────────────────────────────
    def get_legalbert_encoder(self):
        if self._legalbert_encoder is not None:
            return self._legalbert_encoder
        with self._lock:
            if self._legalbert_encoder is not None:
                return self._legalbert_encoder
            device     = self._resolve_device()
            model_name = self._app.config.get("LEGALBERT_MODEL_NAME", "law-ai/InLegalBERT") if self._app else "law-ai/InLegalBERT"
            max_length = int(self._app.config.get("LEGALBERT_MAX_LENGTH", 512) if self._app else 512)
            self._legalbert_encoder = InLegalBERTEncoder(model_name, device, max_length)
            return self._legalbert_encoder

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
        if self._legalbert_encoder is not None: loaded.append("legalbert")
        if self._sentence_model  is not None: loaded.append("sentence-transformer")
        return loaded

    def legalbert_model_name(self) -> str:
        return self._app.config.get("LEGALBERT_MODEL_NAME", "law-ai/InLegalBERT") if self._app else "law-ai/InLegalBERT"

    def sentence_model_name(self) -> str:
        return self._app.config.get("SENTENCE_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2") if self._app else "sentence-transformers/all-MiniLM-L6-v2"


model_registry = ModelRegistry()


# ── Extension initialisation ──────────────────────────────────────────────────
def init_extensions(app: Flask) -> None:
    """Bind all extensions to the Flask app instance."""
    db.init_app(app)
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
