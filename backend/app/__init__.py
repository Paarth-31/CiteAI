"""CiteAI backend — application factory."""
from __future__ import annotations

import os
from http import HTTPStatus

from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory

from .config import config_by_name
from .extensions import init_extensions
from .routes import register_blueprints


def create_app(config_name: str | None = None) -> Flask:
    """Application factory used by Flask CLI and tests."""
    load_dotenv()

    app = Flask(__name__)

    config_key = config_name or os.getenv("FLASK_CONFIG", "default")
    app.config.from_object(config_by_name[config_key])

    init_extensions(app)
    register_blueprints(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # ── Static file serving ──────────────────────────────────────────────────
    @app.get("/uploads/<path:filename>")
    def serve_upload(filename: str):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    # ── Health check ─────────────────────────────────────────────────────────
    @app.get("/health")
    def health_check():
        from .extensions import model_registry
        return jsonify({
            "status": "ok",
            "models_loaded": model_registry.loaded_models(),
        })

    # ── Error handlers ────────────────────────────────────────────────────────
    # Centralised here so every blueprint gets consistent JSON errors
    # instead of Flask's default HTML responses.

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "detail": str(e)}), HTTPStatus.BAD_REQUEST

    @app.errorhandler(401)
    def unauthorised(e):
        return jsonify({"error": "Unauthorised"}), HTTPStatus.UNAUTHORIZED

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden"}), HTTPStatus.FORBIDDEN

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), HTTPStatus.NOT_FOUND

    @app.errorhandler(413)
    def payload_too_large(e):
        return jsonify({"error": "File too large"}), HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.exception("Unhandled server error: %s", e)
        return jsonify({"error": "Internal server error"}), HTTPStatus.INTERNAL_SERVER_ERROR

    return app
