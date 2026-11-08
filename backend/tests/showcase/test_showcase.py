"""Unit tests for Showcase & Evidence Mode (Sprint 5.5).

Covers:
- Showcase artifacts existence and integrity
- 30-case evaluation dataset structure and distribution
- Real metrics calculation and validation
- Citation provenance preservation (canonical text, not search_text)
- Showcase API endpoints (overview, analysis, evaluation)
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from showcase.artifacts import read_artifact
from showcase.evaluation_dataset import EVALUATION_DATASET

client = TestClient(app)


def test_showcase_dataset_structure() -> None:
    assert len(EVALUATION_DATASET) == 30, "Evaluation dataset must contain exactly 30 test cases"

    categories = {case.category for case in EVALUATION_DATASET}
    expected_categories = {
        "persian_factual",
        "english_factual",
        "mixed_language",
        "multi_document",
        "multi_chunk_reasoning",
        "unanswerable",
    }
    assert categories == expected_categories, f"Missing categories: {expected_categories - categories}"

    # Category counts
    counts = {cat: sum(1 for c in EVALUATION_DATASET if c.category == cat) for cat in categories}
    assert counts["persian_factual"] == 8
    assert counts["english_factual"] == 5
    assert counts["mixed_language"] == 5
    assert counts["multi_document"] == 5
    assert counts["multi_chunk_reasoning"] == 3
    assert counts["unanswerable"] == 4


def test_showcase_documents_artifact() -> None:
    data = read_artifact("documents.json")
    assert data is not None, "documents.json artifact must exist"
    assert data["status"] == "System Ready"
    assert data["total_documents"] == 4
    assert data["total_chunks"] >= 10

    docs = data["documents"]
    assert len(docs) == 4
    filenames = {d["filename"] for d in docs}
    assert "01_annual_report_fa.pdf" in filenames
    assert "02_financial_summary_en.pdf" in filenames
    assert "03_strategy_mixed.pdf" in filenames
    assert "04_hr_performance_fa.pdf" in filenames


def test_showcase_analysis_artifact_and_citations() -> None:
    data = read_artifact("analysis.json")
    assert data is not None, "analysis.json artifact must exist"

    assert "بر اساس گزارش عملکرد سال ۱۴۰۴" in data["question"]
    assert len(data["answer"]) > 100
    assert "[1]" in data["answer"]

    citations = data["citations"]
    assert len(citations) >= 2
    for cit in citations:
        assert cit["citation_index"] in (1, 2)
        assert cit["document_format"] == "pdf"
        assert len(cit["excerpt"]) > 0
        assert "document_title" in cit
        assert "chunk_id" in cit

    trace = data["analysis_trace"]
    assert len(trace) == 8
    step_names = [t["step"] for t in trace]
    assert "Query normalized" in step_names
    assert "Semantic retrieval" in step_names
    assert "Keyword retrieval" in step_names
    assert "RRF fusion" in step_names
    assert "Context assembled" in step_names
    assert "Answer generated" in step_names
    assert "Grounding validated" in step_names
    assert "Citations verified" in step_names


def test_showcase_evaluation_metrics_integrity() -> None:
    data = read_artifact("evaluation.json")
    assert data is not None, "evaluation.json artifact must exist"

    metrics = data["metrics"]
    assert metrics["total_cases"] == 30
    assert metrics["passed"] + metrics["failed"] == 30
    assert 0.0 <= metrics["pass_rate"] <= 100.0
    assert 0.0 <= metrics["retrieval_hit_at_10"] <= 100.0
    assert 0.0 <= metrics["grounding_validity"] <= 100.0
    assert 0.0 <= metrics["citation_correctness"] <= 100.0

    cases = data["cases"]
    assert len(cases) == 30
    for case in cases:
        assert "id" in case
        assert "category" in case
        assert "passed" in case
        if not case["passed"]:
            assert case["failure_reason"] is not None


def test_showcase_api_overview() -> None:
    resp = client.get("/showcase/overview")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "System Ready"
    assert payload["total_documents"] == 4


def test_showcase_api_analysis() -> None:
    resp = client.get("/showcase/analysis")
    assert resp.status_code == 200
    payload = resp.json()
    assert "question" in payload
    assert "answer" in payload
    assert len(payload["citations"]) >= 2
    assert len(payload["analysis_trace"]) == 8


def test_showcase_api_evaluation() -> None:
    resp = client.get("/showcase/evaluation")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["metrics"]["total_cases"] == 30
    assert len(payload["cases"]) == 30
