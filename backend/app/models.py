"""SQLAlchemy 2.0 database models for Job Descriptions, Candidates, and Match Results."""

import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class JobDescription(Base):
    """Job Description model containing parsed requirements and raw text."""

    __tablename__ = "job_descriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Target Position")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    required_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    min_experience_years: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    education_level: Mapped[str] = mapped_column(String(50), nullable=False, default="bachelor")
    responsibilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False
    )

    matches: Mapped[list["MatchResultRecord"]] = relationship(
        "MatchResultRecord",
        back_populates="job_description",
        cascade="all, delete-orphan",
    )


class Candidate(Base):
    """Candidate profile model storing raw text, parsed structure, and errors."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Candidate")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    parse_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="parsed"
    )  # "parsed" | "failed"
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False
    )

    matches: Mapped[list["MatchResultRecord"]] = relationship(
        "MatchResultRecord",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class MatchResultRecord(Base):
    """Match result record storing scores, detailed evidence, and human explanations."""

    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    jd_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    skill_score: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_score: Mapped[float] = mapped_column(Float, nullable=False)
    experience_score: Mapped[float] = mapped_column(Float, nullable=False)
    education_score: Mapped[float] = mapped_column(Float, nullable=False)
    project_score: Mapped[float] = mapped_column(Float, nullable=False)

    status_label: Mapped[str] = mapped_column(String(20), nullable=False)  # HIGH, MEDIUM, LOW

    matched_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    partial_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    explanation: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False
    )

    job_description: Mapped["JobDescription"] = relationship(
        "JobDescription", back_populates="matches"
    )
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="matches")
