"""Serialization helpers for authentication responses."""
from __future__ import annotations
from ..models import User


def user_to_dict(user: User) -> dict:
    return {
        # BUG FIX: user.id is a UUID object — must cast to str or
        # jsonify() raises "Object of type UUID is not JSON serializable"
        "id":        str(user.id),
        "name":      user.name,
        "email":     user.email,
        "createdAt": user.created_at.isoformat() if user.created_at else None,
        "updatedAt": user.updated_at.isoformat() if user.updated_at else None,
    }
