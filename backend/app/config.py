"""Application configuration module.

Defines all scoring weights, model settings, thresholds, and environment
variables in one central location with Pydantic v2 BaseSettings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for application and matching engine."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # General App Config
    app_name: str = "AI-Based Resume Matching & Ranking System"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    debug: bool = False
    cors_origins: list[str] = ["*"]

    # Database: SQLite by default, PostgreSQL overridable via DATABASE_URL
    database_url: str = "sqlite:///./resume_matcher.db"

    # NLP Models
    embedding_model_name: str = "all-MiniLM-L6-v2"
    spacy_model_name: str = "en_core_web_sm"

    # Match Engine Scoring Weights (must sum to 1.0)
    weight_skills: float = 0.40
    weight_semantic: float = 0.25
    weight_experience: float = 0.20
    weight_education: float = 0.10
    weight_project: float = 0.05

    # Skill Matching Weights & Thresholds
    required_skill_weight: float = 2.0
    preferred_skill_weight: float = 1.0
    # Embedding fallback threshold: ONLY applied when cosine >= 0.75
    skill_embed_threshold: float = 0.75
    # Keyword-stuffer defense: skills found ONLY in a list get reduced credit
    listed_only_credit: float = 0.50

    # Semantic Calibration Range & Top-K Sentences
    semantic_min_cosine: float = 0.28
    semantic_max_cosine: float = 0.78
    semantic_top_k: int = 5

    # Project Score Continuous Calibration Range
    project_min_cosine: float = 0.25
    project_max_cosine: float = 0.75
    # Cap contribution for fallback-extracted project sentences from experience
    fallback_project_cap: float = 70.0

    # Status Classification Thresholds (HIGH >= 80, MEDIUM 60-79.9, LOW < 60)
    threshold_high: float = 80.0
    threshold_medium: float = 60.0
    # Hard requirement experience ratio: if candidate_years < ratio * required_years, cap status at LOW
    hard_req_experience_ratio_cap: float = 0.50

    # Role Relevance Tier Thresholds
    role_min_skills_full_credit: int = 2
    role_semantic_threshold: float = 0.55

    # Keyword-Stuffer Defense Thresholds
    stuffing_min_listed_only: int = 8
    stuffing_min_listed_share: float = 0.70
    stuffing_max_demonstrated: int = 2

    # Legacy Experience Relevance Thresholds (kept for backward compatibility)
    exp_relevance_min_cosine: float = 0.35
    exp_relevance_max_cosine: float = 0.55

    # Education Hierarchy Mapping
    education_ranks: dict[str, int] = {
        "phd": 4,
        "doctorate": 4,
        "master": 3,
        "masters": 3,
        "msc": 3,
        "m.sc": 3,
        "ms": 3,
        "m.s": 3,
        "m.tech": 3,
        "mtech": 3,
        "mba": 3,
        "mca": 3,
        "m.e": 3,
        "me": 3,
        "m.a": 3,
        "ma": 3,
        "mfa": 3,
        "med": 3,
        "m.ed": 3,
        "mpharm": 3,
        "m.pharm": 3,
        "march": 3,
        "m.arch": 3,
        "llm": 3,
        "ll.m": 3,
        "pgdm": 3,
        "pgdbm": 3,
        "bachelor": 2,
        "bachelors": 2,
        "bsc": 2,
        "b.sc": 2,
        "bs": 2,
        "b.s": 2,
        "b.tech": 2,
        "btech": 2,
        "be": 2,
        "b.e": 2,
        "bca": 2,
        "bcom": 2,
        "b.com": 2,
        "ba": 2,
        "b.a": 2,
        "bba": 2,
        "bbm": 2,
        "bms": 2,
        "bfa": 2,
        "bed": 2,
        "b.ed": 2,
        "bpharm": 2,
        "b.pharm": 2,
        "barch": 2,
        "b.arch": 2,
        "llb": 2,
        "ll.b": 2,
        "diploma": 1,
        "associate": 1,
        "none": 0,
    }


@lru_cache
def get_settings() -> Settings:
    """Return cached instance of application settings."""
    return Settings()


def check_experience_cap(
    score: float,
    candidate_years: float | None = None,
    required_years: float | None = None,
) -> tuple[str, bool]:
    """Determine status label and whether the 50% experience cap rule was applied.

    Returns:
        (status_label, experience_cap_applied)
    """
    cfg = get_settings()
    uncapped_status = (
        "HIGH"
        if score >= cfg.threshold_high
        else ("MEDIUM" if score >= cfg.threshold_medium else "LOW")
    )

    cap_triggered = (
        required_years is not None
        and required_years > 0.0
        and candidate_years is not None
        and candidate_years < (cfg.hard_req_experience_ratio_cap * required_years)
    )

    if cap_triggered and uncapped_status != "LOW":
        return "LOW", True

    return uncapped_status, False


def get_status_label(
    score: float,
    candidate_years: float | None = None,
    required_years: float | None = None,
) -> str:
    """Return status classification strictly based on configured thresholds.

    HIGH >= 80.0
    MEDIUM >= 60.0 and < 80.0
    LOW < 60.0

    Hard requirement experience cap:
    If candidate_years < 50% of required_years (when required_years > 0),
    the status label cannot be above LOW.
    """
    label, _ = check_experience_cap(score, candidate_years, required_years)
    return label
