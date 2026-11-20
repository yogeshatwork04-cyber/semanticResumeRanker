"""Comprehensive integration tests for FastAPI REST API endpoints using TestClient."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import reset_all_data
from app.main import app

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="module")
def client():
    """Create FastAPI TestClient within lifespan context."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure database is clean before and after each test."""
    reset_all_data()
    yield
    reset_all_data()


def test_health_endpoints(client: TestClient):
    """Verify health endpoints return healthy state with database connection."""
    r1 = client.get("/health")
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["status"] == "healthy"
    assert data1["database"] == "ok"
    assert data1["models_loaded"] is True

    r2 = client.get("/api/health")
    assert r2.status_code == 200
    assert r2.json()["status"] == "healthy"


def test_jd_create_text_and_update(client: TestClient):
    """Test JD text creation, extraction, retrieval, and recruiter editing."""
    jd_text = (
        "Role: Senior Backend Engineer\n"
        "Requirements: Must have 4+ years experience. Strong Python, FastAPI, Docker, and PostgreSQL."
    )
    # Create via JSON text
    res = client.post("/api/jd", json={"text": jd_text})
    assert res.status_code == 201
    jd_data = res.json()
    jd_id = jd_data["id"]
    assert "Python" in jd_data["required_skills"]
    assert jd_data["min_experience_years"] == 4.0

    # Retrieve
    get_res = client.get(f"/api/jd/{jd_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == jd_data["title"]

    # Recruiter update
    update_res = client.put(
        f"/api/jd/{jd_id}",
        json={
            "required_skills": ["Python", "FastAPI", "Kubernetes"],
            "min_experience_years": 5.0,
            "education_level": "master",
        },
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["required_skills"] == ["Python", "FastAPI", "Kubernetes"]
    assert updated_data["min_experience_years"] == 5.0
    assert updated_data["education_level"] == "master"


def test_bad_file_handling(client: TestClient):
    """Verify upload safety: file type validation, size limit, and per-file errors."""
    # 1. Unsupported JD upload format
    bad_jd = ("script.exe", b"binarycontent", "application/octet-stream")
    r_bad_jd = client.post("/api/jd", files={"file": bad_jd})
    assert r_bad_jd.status_code == 400
    assert "Unsupported file format" in r_bad_jd.json()["detail"]

    # 2. Unsupported resume format in batch
    bad_resume = ("malicious.sh", b"#!/bin/bash echo hello", "text/x-sh")
    r_bad_res = client.post("/api/resumes", files=[("files", bad_resume)])
    assert r_bad_res.status_code == 201
    batch_res = r_bad_res.json()
    assert batch_res["total_uploaded"] == 1
    assert batch_res["failed"] == 1
    assert batch_res["successful"] == 0
    assert "Unsupported file format" in batch_res["errors"][0]["error"]

    # 3. File exceeding 5 MB limit
    oversized = ("huge.pdf", b"0" * (5 * 1024 * 1024 + 10), "application/pdf")
    r_huge = client.post("/api/resumes", files=[("files", oversized)])
    assert r_huge.status_code == 201
    batch_huge = r_huge.json()
    assert batch_huge["failed"] == 1
    assert "exceeds maximum allowed size" in batch_huge["errors"][0]["error"]


def test_full_pipeline_ranking_details_csv_and_reset(client: TestClient):
    """End-to-end integration test: JD upload, batch resume upload, match, ranking, details, CSV, reset."""
    # 1. Create JD from sample file
    jd_path = BASE_DIR / "sample_data" / "job_description.txt"
    assert jd_path.exists()
    jd_bytes = jd_path.read_bytes()

    jd_res = client.post(
        "/api/jd",
        files={"file": (jd_path.name, jd_bytes, "text/plain")},
    )
    assert jd_res.status_code == 201
    jd_id = jd_res.json()["id"]

    # 2. Upload all 17 sample resumes in one batch
    resumes_dir = BASE_DIR / "sample_data" / "resumes"
    resume_files = sorted([p for p in resumes_dir.iterdir() if p.suffix.lower() in {".pdf", ".docx"}])
    assert len(resume_files) >= 14

    upload_payload = []
    for p in resume_files:
        mime = "application/pdf" if p.suffix.lower() == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        upload_payload.append(("files", (p.name, p.read_bytes(), mime)))

    upload_res = client.post("/api/resumes", files=upload_payload)
    assert upload_res.status_code == 201
    batch = upload_res.json()
    assert batch["total_uploaded"] == len(resume_files)
    # 16 should succeed, 1 scanned empty should fail gracefully
    assert batch["successful"] == len(resume_files) - 1
    assert batch["failed"] == 1

    # 3. Run Matching
    match_res = client.post("/api/match", json={"jd_id": jd_id})
    assert match_res.status_code == 200
    ranking_data = match_res.json()
    results = ranking_data["results"]
    assert len(results) == batch["successful"]

    # Check top candidate score order
    assert results[0]["final_score"] >= results[1]["final_score"]
    assert results[0]["name"] in {"Alex Chen", "Sarah Lindqvist"}
    assert results[0]["status_label"] == "HIGH"

    # 4. Candidate Detail Analysis endpoint
    top_candidate_id = results[0]["candidate_id"]
    analysis_res = client.get(f"/api/candidates/{top_candidate_id}?jd_id={jd_id}")
    assert analysis_res.status_code == 200
    analysis = analysis_res.json()

    # Verify all required fields
    assert analysis["candidate_id"] == top_candidate_id
    assert analysis["overall_score"] > 85.0
    assert analysis["status_label"] == "HIGH"
    assert "skill" in analysis["sub_scores"]
    assert "semantic" in analysis["sub_scores"]
    assert "experience" in analysis["sub_scores"]
    assert "education" in analysis["sub_scores"]
    assert "project" in analysis["sub_scores"]

    # Skills evidence structure check
    assert len(analysis["matched_skills"]) > 0
    first_match = analysis["matched_skills"][0]
    assert "evidence_source" in first_match
    assert first_match["evidence_source"] in {"listed", "demonstrated"}
    assert "rule" in first_match
    assert "credit" in first_match

    # Experience comparison check
    exp_comp = analysis["experience_comparison"]
    assert exp_comp["required_years"] == 3.0
    assert exp_comp["found_years"] >= 3.0
    assert exp_comp["meets_requirement"] is True

    # Explanations check
    assert len(analysis["explanation_bullets"]) >= 4
    assert len(analysis["headline"]) > 0
    assert len(analysis["recommendation"]) > 0

    # 5. CSV Export endpoint
    csv_res = client.get(f"/api/results/export.csv?jd_id={jd_id}")
    assert csv_res.status_code == 200
    assert csv_res.headers["content-type"].startswith("text/csv")
    csv_text = csv_res.text
    assert "Rank,Candidate Name,Final Score (%),Status" in csv_text
    assert results[0]["name"] in csv_text

    # 6. Reset endpoint
    del_res = client.delete("/api/reset")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Verify database is empty after reset
    list_cand = client.get("/api/resumes")
    assert len(list_cand.json()) == 0

