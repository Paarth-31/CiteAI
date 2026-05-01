"""Authentication routes."""
from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    current_user,
    get_jwt_identity,
    jwt_required,
)

from ..schemas.auth import user_to_dict
from ..services.auth_service import authenticate_user, create_user, get_user_by_id

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/register")
def register():
    payload  = request.get_json(silent=True) or {}
    name     = (payload.get("name") or "").strip()
    email    = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not name:
        return jsonify({"error": "Name is required"}), HTTPStatus.BAD_REQUEST
    if not email:
        return jsonify({"error": "Email is required"}), HTTPStatus.BAD_REQUEST
    if not password or len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), HTTPStatus.BAD_REQUEST

    try:
        user = create_user(name=name, email=email, password=password)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    return jsonify({"user": user_to_dict(user)}), HTTPStatus.CREATED


@bp.post("/login")
def login():
    payload  = request.get_json(silent=True) or {}
    email    = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), HTTPStatus.BAD_REQUEST

    user = authenticate_user(email=email, password=password)
    if not user:
        return jsonify({"error": "Invalid credentials"}), HTTPStatus.UNAUTHORIZED

    # BUG FIX: user.id is a UUID object (not JSON-serialisable).
    # Pass str(user.id) as the JWT identity so Flask-JWT can serialise it.
    # The user_lookup_loader in extensions.py receives this string and does
    # User.query.filter_by(id=identity) which PostgreSQL handles fine.
    identity = str(user.id)
    access_token = create_access_token(identity=str(identity))
    refresh_token = create_refresh_token(identity=str(identity))

    return jsonify({
    "accessToken": access_token,
    "refreshToken": refresh_token,
    "user": user_to_dict(user)
}), 200


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh_access_token():
    identity = get_jwt_identity()
    if identity is None:
        return jsonify({"error": "Invalid token"}), HTTPStatus.UNAUTHORIZED

    user = get_user_by_id(identity)
    if user is None:
        return jsonify({"error": "User not found"}), HTTPStatus.NOT_FOUND

    return jsonify({"accessToken": create_access_token(identity=identity)}), HTTPStatus.OK


@bp.get("/me")
@jwt_required()
def current_user_profile():
    if current_user is None:
        return jsonify({"error": "User not found"}), HTTPStatus.NOT_FOUND
    return jsonify({"user": user_to_dict(current_user)}), HTTPStatus.OK


@bp.post("/logout")
@jwt_required(optional=True)
def logout():
    # Stateless JWT — frontend discards tokens on its side.
    return jsonify({"success": True}), HTTPStatus.OK
