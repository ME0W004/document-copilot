"""Persistence and serialization of showcase artifacts (Sprint 5.5).

Stores and reads machine-readable JSON artifacts in repo-level artifacts/showcase/:
- artifacts/showcase/documents.json
- artifacts/showcase/analysis.json
- artifacts/showcase/evaluation.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "showcase"


def get_artifacts_dir() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACTS_DIR


def write_artifact(name: str, data: dict[str, Any]) -> Path:
    path = get_artifacts_dir() / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_artifact(name: str) -> dict[str, Any] | None:
    path = ARTIFACTS_DIR / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
