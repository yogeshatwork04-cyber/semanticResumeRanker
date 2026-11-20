"""Unit tests for the template-based explanation generator."""

from app.services.explainer import get_score_explainer
from app.services.scorer import MatchResult


def test_explainer_high_match_output():
    """Verify high scoring match produces clear positive explanation and advance recommendation."""
    explainer = get_score_explainer()

    result = MatchResult(
        candidate_name="Alex Chen",
        filename="alex.pdf",
        final_score=88.5,
        skill_score=92.0,
        semantic_score=85.0,
        experience_score=100.0,
        education_score=100.0,
        project_score=80.0,
        matched_skills=["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs"],
        partial_skills=[],
        missing_skills=["Kubernetes"],
        evidence={
            "experience": {
                "candidate_years": 5.0,
                "required_years": 3.0,
                "ratio": 1.0,
                "title_relevant": True,
            },
            "education": {
                "candidate_education": "bachelor",
                "required_education": "bachelor",
            },
            "semantic": {
                "raw_avg_cosine": 0.62,
            },
            "projects": {
                "has_dedicated_projects": True,
            },
        },
    )

    explanation = explainer.explain(result)

    assert "Top Match" in explanation["headline"]
    assert "Alex Chen" in explanation["headline"]
    assert "Matched 5" in explanation["skills_explanation"]
    assert "Kubernetes" in explanation["skills_explanation"]
    assert "5.0 years vs 3.0 required" in explanation["experience_explanation"]
    assert "Strong Candidate" in explanation["recommendation"]
    assert len(explanation["bullet_points"]) >= 4


def test_explainer_missing_skills_recommendation():
    """Verify candidate with missing skills mentions those skills in recommendation."""
    explainer = get_score_explainer()

    result = MatchResult(
        candidate_name="Jordan Taylor",
        filename="jordan.docx",
        final_score=72.0,
        skill_score=70.0,
        semantic_score=68.0,
        experience_score=80.0,
        education_score=100.0,
        project_score=50.0,
        matched_skills=["Python", "FastAPI"],
        partial_skills=[],
        missing_skills=["Docker", "PostgreSQL"],
        evidence={
            "experience": {
                "candidate_years": 2.5,
                "required_years": 3.0,
                "ratio": 0.83,
                "title_relevant": True,
            },
            "education": {"candidate_education": "bachelor", "required_education": "bachelor"},
            "semantic": {"raw_avg_cosine": 0.45},
            "projects": {"has_dedicated_projects": False},
        },
    )

    explanation = explainer.explain(result)

    assert "Medium Match" in explanation["headline"] or "Good Match" in explanation["headline"]
    assert "Docker" in explanation["recommendation"] or "PostgreSQL" in explanation["recommendation"]

