"""Project-root helpers so every route does not reimplement sys.path hacks."""
from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    # backend/app/services/paths.py → CiteAI/
    return Path(__file__).resolve().parent.parent.parent.parent


def ensure_project_root() -> Path:
    root = project_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root
