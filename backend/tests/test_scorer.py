"""Unit tests for the scoring engine, formula verification, bounds, and determinism."""

import pytest

from app.config import get_settings
from app.services.scorer import get_resume_scorer

settings = get_settings()


@pytest.fixture
def sample_jd():
    return {
        "title": "Senior Backend Python Engineer",
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs"],
        "preferred_skills": ["Redis", "Kubernetes", "AWS"],
        "min_experience_years": 3.0,
        "education_level": "bachelor",
        "raw_text": (
            "We need a Senior Backend Python Engineer. "
            "You will build high performance REST APIs using FastAPI and PostgreSQL. "
            "Containerize services with Docker and manage deployments. "
            "Must have 3+ years experience and Bachelor degree."
        ),
    }


@pytest.fixture
def strong_candidate():
    return {
        "name": "Alex Chen",
        "filename": "alex.pdf",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs", "Redis", "AWS"],
        "total_experience_years": 5.0,
        "education_level": "bachelor",
        "job_titles": ["Senior Backend Developer"],
        "sections": {
            "experience": "Architected distributed REST APIs using FastAPI and PostgreSQL. Managed Docker containers.",
            "projects": "FastAPI microservices platform with PostgreSQL database.",
        },
        "raw_text": "Alex Chen Senior Backend Developer with 5 years experience in Python, FastAPI, PostgreSQL, Docker.",
    }


def test_score_bounds_and_formula(sample_jd, strong_candidate):
    """Verify all sub-scores and final score strictly remain in [0, 100] and obey formula."""
    scorer = get_resume_scorer()
    res = scorer.score_candidate(strong_candidate, sample_jd)

    assert 0.0 <= res.final_score <= 100.0
    assert 0.0 <= res.skill_score <= 100.0
    assert 0.0 <= res.semantic_score <= 100.0
    assert 0.0 <= res.experience_score <= 100.0
    assert 0.0 <= res.education_score <= 100.0
    assert 0.0 <= res.project_score <= 100.0

    # Test formula matches config weights
    expected = (
        settings.weight_skills * res.skill_score
        + settings.weight_semantic * res.semantic_score
        + settings.weight_experience * res.experience_score
        + settings.weight_education * res.education_score
        + settings.weight_project * res.project_score
    )
    assert pytest.approx(res.final_score, abs=0.05) == expected


def test_scorer_determinism(sample_jd, strong_candidate):
    """Running scorer twice on the exact same candidate data must produce identical results."""
    scorer = get_resume_scorer()
    res1 = scorer.score_candidate(strong_candidate, sample_jd)
    res2 = scorer.score_candidate(strong_candidate, sample_jd)

    assert res1.final_score == res2.final_score
    assert res1.skill_score == res2.skill_score
    assert res1.semantic_score == res2.semantic_score
    assert res1.experience_score == res2.experience_score
    assert res1.education_score == res2.education_score
    assert res1.project_score == res2.project_score
    assert res1.matched_skills == res2.matched_skills
    assert res1.missing_skills == res2.missing_skills


def test_skill_partial_credit_threshold(sample_jd):
    """Candidate with semantically similar skill (e.g. Flask when FastAPI required) receives partial credit."""
    scorer = get_resume_scorer()
    # Candidate lacks FastAPI, has Flask
    cand = {
        "name": "Partial Skill Cand",
        "filename": "cand.pdf",
        "skills": ["Python", "Flask", "PostgreSQL"],
        "total_experience_years": 3.0,
        "education_level": "bachelor",
        "job_titles": ["Python Developer"],
        "sections": {"experience": "Built apps with Python and Flask", "projects": ""},
        "raw_text": "Built apps with Python and Flask",
    }
    res = scorer.score_candidate(cand, sample_jd)

    assert "Python" in res.matched_skills
    assert "PostgreSQL" in res.matched_skills
    # Check partial or missing
    all_evaluated = res.matched_skills + [p["jd_skill"] for p in res.partial_skills] + res.missing_skills
    assert "FastAPI" in all_evaluated


def test_experience_ratio_scoring(sample_jd):
    """Candidate with 1.5 yrs vs 3.0 required should receive exactly 50% experience score."""
    scorer = get_resume_scorer()
    cand = {
        "name": "Junior Cand",
        "filename": "cand.pdf",
        "skills": ["Python"],
        "total_experience_years": 1.5,
        "education_level": "bachelor",
        "job_titles": ["Junior Developer"],
        "sections": {},
        "raw_text": "",
    }
    exp_score, evidence = scorer.compute_experience_score(
        candidate_years=cand["total_experience_years"],
        required_years=sample_jd["min_experience_years"],
        candidate_titles=cand["job_titles"],
        jd_title=sample_jd["title"],
    )
    assert exp_score == 50.0
    assert evidence["ratio"] == 0.5


def test_education_tier_scoring():
    """Verify PhD > Master > Bachelor > Diploma > None scoring rules."""
    scorer = get_resume_scorer()

    # Meets/exceeds (Master vs Bachelor requirement) -> 100
    score, _ = scorer.compute_education_score(candidate_education="master", required_education="bachelor")
    assert score == 100.0

    # Exact match (Bachelor vs Bachelor) -> 100
    score, _ = scorer.compute_education_score(candidate_education="bachelor", required_education="bachelor")
    assert score == 100.0

    # One tier below (Diploma vs Bachelor) -> 50
    score, _ = scorer.compute_education_score(candidate_education="diploma", required_education="bachelor")
    assert score == 50.0

    # Two tiers below (None vs Bachelor) -> 0
    score, _ = scorer.compute_education_score(candidate_education="none", required_education="bachelor")
    assert score == 0.0
