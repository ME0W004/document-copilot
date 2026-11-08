"""FastAPI router for Showcase and Evidence Mode (Sprint 5.5).

Provides read-only, screenshot-ready endpoints for:
- /showcase/overview: Document catalog and system readiness status
- /showcase/analysis: Grounded conversation turn, citations, and technical analysis trace
- /showcase/evaluation: 30-case evaluation report and measured metrics
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from showcase.artifacts import read_artifact

router = APIRouter(prefix="/showcase", tags=["showcase"])


@router.get("/overview")
async def get_showcase_overview() -> dict[str, Any]:
    data = read_artifact("documents.json")
    if not data:
        # Fallback: run seed if not generated yet
        from scripts.seed_showcase import seed_showcase

        seed_showcase()
        data = read_artifact("documents.json")
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Showcase documents artifact not found",
        )
    return data


@router.get("/analysis")
async def get_showcase_analysis() -> dict[str, Any]:
    data = read_artifact("analysis.json")
    if not data:
        from scripts.seed_showcase import seed_showcase

        seed_showcase()
        data = read_artifact("analysis.json")
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Showcase analysis artifact not found",
        )
    return data


@router.get("/evaluation")
async def get_showcase_evaluation() -> dict[str, Any]:
    data = read_artifact("evaluation.json")
    if not data:
        from scripts.run_showcase_eval import run_evaluation

        run_evaluation()
        data = read_artifact("evaluation.json")
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Showcase evaluation artifact not found",
        )
    return data
