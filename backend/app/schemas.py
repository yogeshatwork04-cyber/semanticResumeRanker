"""Pydantic v2 schemas for all API requests and responses."""

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JDExtractRequest(BaseModel):
    """Request payload for text-based JD analysis."""

    text: str = Field(..., min_length=10, description="Full text of Job Description")


class JDUpdateRequest(BaseModel):
    """Payload allowing recruiter to correct or customize extracted JD fields."""

    title: str | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    min_experience_years: float | None = None
    education_level: str | None = None
    responsibilities: list[str] | None = None


class JDResponse(BaseModel):
    """Response containing parsed and structured Job Description."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    raw_text: str
    required_skills: list[str]
    preferred_skills: list[str]
    min_experience_years: float
    education_level: str
    responsibilities: list[str]
    created_at: datetime.datetime


class CandidateSummaryResponse(BaseModel):
    """Summary of a parsed candidate profile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    name: str
    email: str | None
    phone: str | None
    total_experience_years: float
    education_level: str
    skills: list[str]
    parse_status: str
    parse_error: str | None
    created_at: datetime.datetime


class CandidateUploadBatchResponse(BaseModel):
    """Response returned after multi-file resume batch upload."""

    total_uploaded: int
    successful: int
    failed: int
    candidates: list[CandidateSummaryResponse]
    errors: list[dict[str, str]]


class MatchRunRequest(BaseModel):
    """Request to initiate scoring against a specific Job Description."""

    jd_id: int


class RankedCandidateItem(BaseModel):
    """Item representation in the ranking dashboard table."""

    candidate_id: int
    name: str
    filename: str
    experience_years: float
    relevant_years: float = 0.0
    total_years: float = 0.0
    final_score: float
    status_label: str  # HIGH, MEDIUM, LOW
    sub_scores: dict[str, float]
    matched_skills_top: list[str]
    matched_skills_count: int
    missing_skills_count: int
    experience_cap_applied: bool = False
    possible_keyword_stuffing: bool = False
    required_years: float = 0.0
    found_years: float = 0.0
    cap_ratio: float = 0.50


class MatchResultsListResponse(BaseModel):
    """List response for ranked matching results."""

    jd_id: int
    job_title: str
    total_candidates: int
    results: list[RankedCandidateItem]


class CandidateAnalysisResponse(BaseModel):
    """Comprehensive candidate evaluation and explanation report."""

    candidate_id: int
    name: str
    email: str | None
    phone: str | None
    filename: str
    overall_score: float
    relevant_years: float = 0.0
    total_years: float = 0.0
    status_label: str  # HIGH, MEDIUM, LOW
    experience_cap_applied: bool = False
    possible_keyword_stuffing: bool = False
    required_years: float = 0.0
    found_years: float = 0.0
    cap_ratio: float = 0.50
    sub_scores: dict[str, float]
    extracted_info: dict[str, Any]
    matched_skills: list[dict[str, Any]]
    partial_skills: list[dict[str, Any]]
    missing_skills: list[str]
    experience_comparison: dict[str, Any]
    explanation_bullets: list[str]
    headline: str
    recommendation: str
    raw_evidence: dict[str, Any]


class HealthResponse(BaseModel):
    """API health and service readiness response."""

    status: str
    app_name: str
    app_version: str
    database: str
    models_loaded: bool

