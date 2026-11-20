"""Matching engine, ranking, candidate analysis, CSV export, and reset endpoints."""

import csv
import io
from typing import Any

import anyio
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db import get_db, reset_all_data
from app.models import Candidate, JobDescription, MatchResultRecord
from app.schemas import (
    CandidateAnalysisResponse,
    MatchResultsListResponse,
    MatchRunRequest,
    RankedCandidateItem,
)
from app.services.explainer import get_score_explainer
from app.services.scorer import get_resume_scorer

router = APIRouter(tags=["Matching & Analysis"])


def _run_matching_pipeline(
    jd_dict: dict[str, Any],
    candidate_profiles: list[dict[str, Any]],
) -> list[tuple[Any, dict[str, Any]]]:
    """Score candidates and generate explanations in thread pool."""
    scorer = get_resume_scorer()
    explainer = get_score_explainer()
    results: list[tuple[Any, dict[str, Any]]] = []

    for profile in candidate_profiles:
        score_result = scorer.score_candidate(profile, jd_dict)
        explanation = explainer.explain(score_result)
        results.append((score_result, explanation))

    return results


@router.post("/match", response_model=MatchResultsListResponse)
async def run_match_for_jd(
    payload: MatchRunRequest,
    db: Session = Depends(get_db),
) -> MatchResultsListResponse:
    """Score all parsed candidate resumes against the specified Job Description."""
    jd = db.query(JobDescription).filter(JobDescription.id == payload.jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job Description with ID {payload.jd_id} not found.",
        )

    candidates = (
        db.query(Candidate)
        .filter(Candidate.parse_status == "parsed")
        .all()
    )
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No successfully parsed resumes available to match. Upload resumes first.",
        )

    jd_dict = {
        "title": jd.title,
        "required_skills": jd.required_skills,
        "preferred_skills": jd.preferred_skills,
        "min_experience_years": jd.min_experience_years,
        "education_level": jd.education_level,
        "responsibilities": jd.responsibilities,
        "raw_text": jd.raw_text,
    }

    profiles = [c.profile_json for c in candidates]

    # Run CPU-heavy matching in worker thread
    pipeline_results = await anyio.to_thread.run_sync(
        _run_matching_pipeline, jd_dict, profiles
    )

    # Persist or update match records in database
    for cand, (score_res, expl) in zip(candidates, pipeline_results, strict=False):
        matched_details = (
            score_res.matched_skills_details
            if score_res.matched_skills_details
            else [
                {
                    "skill": s,
                    "matched_via": s,
                    "rule": "exact",
                    "credit": 1.0,
                    "evidence_source": "demonstrated",
                }
                for s in score_res.matched_skills
            ]
        )

        existing_record = (
            db.query(MatchResultRecord)
            .filter(
                MatchResultRecord.jd_id == jd.id,
                MatchResultRecord.candidate_id == cand.id,
            )
            .first()
        )

        if existing_record:
            existing_record.final_score = score_res.final_score
            existing_record.skill_score = score_res.skill_score
            existing_record.semantic_score = score_res.semantic_score
            existing_record.experience_score = score_res.experience_score
            existing_record.education_score = score_res.education_score
            existing_record.project_score = score_res.project_score
            existing_record.status_label = expl.get("status_label", "LOW")
            existing_record.matched_skills = matched_details
            existing_record.partial_skills = score_res.partial_skills
            existing_record.missing_skills = score_res.missing_skills
            existing_record.evidence = score_res.evidence
            existing_record.explanation = expl
        else:
            new_record = MatchResultRecord(
                jd_id=jd.id,
                candidate_id=cand.id,
                final_score=score_res.final_score,
                skill_score=score_res.skill_score,
                semantic_score=score_res.semantic_score,
                experience_score=score_res.experience_score,
                education_score=score_res.education_score,
                project_score=score_res.project_score,
                status_label=expl.get("status_label", "LOW"),
                matched_skills=matched_details,
                partial_skills=score_res.partial_skills,
                missing_skills=score_res.missing_skills,
                evidence=score_res.evidence,
                explanation=expl,
            )
            db.add(new_record)

    db.commit()

    # Query and return ranked results
    return get_ranking_results(jd_id=jd.id, db=db)


@router.get("/results", response_model=MatchResultsListResponse)
def get_ranking_results(
    jd_id: int = Query(..., description="ID of the Job Description"),
    db: Session = Depends(get_db),
) -> MatchResultsListResponse:
    """Return ranked candidate list for a given Job Description, ordered by Final Score."""
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job Description with ID {jd_id} not found.",
        )

    records = (
        db.query(MatchResultRecord)
        .filter(MatchResultRecord.jd_id == jd_id)
        .order_by(MatchResultRecord.final_score.desc())
        .all()
    )

    from app.config import get_settings

    cfg = get_settings()

    ranked_items: list[RankedCandidateItem] = []
    for r in records:
        cand = r.candidate
        exp_ev = (r.evidence or {}).get("experience", {})
        rel_years = exp_ev.get("relevant_years", exp_ev.get("candidate_years", 0.0))
        tot_years = exp_ev.get("total_years")
        if (tot_years is None or tot_years == 0.0) and cand and cand.profile_json:
            tot_years = cand.profile_json.get("total_experience_years", 0.0)
        if tot_years is None:
            tot_years = rel_years
        rel_years = min(rel_years, tot_years)

        top_matched = [
            m.get("jd_skill", m.get("skill", str(m))) if isinstance(m, dict) else str(m)
            for m in r.matched_skills[:4]
        ]

        exp_cap_applied = (r.explanation or {}).get("experience_cap_applied")
        if exp_cap_applied is None:
            exp_cap_applied = (
                jd.min_experience_years > 0.0
                and rel_years < (cfg.hard_req_experience_ratio_cap * jd.min_experience_years)
                and (r.final_score >= cfg.threshold_medium)
            )

        is_stuffing = bool((r.explanation or {}).get("possible_keyword_stuffing", False))

        ranked_items.append(
            RankedCandidateItem(
                candidate_id=r.candidate_id,
                name=cand.name if cand else "Unknown",
                filename=cand.filename if cand else "",
                experience_years=rel_years,
                relevant_years=rel_years,
                total_years=tot_years,
                final_score=round(r.final_score, 1),
                status_label=r.status_label,
                experience_cap_applied=bool(exp_cap_applied),
                possible_keyword_stuffing=is_stuffing,
                required_years=jd.min_experience_years,
                found_years=rel_years,
                cap_ratio=cfg.hard_req_experience_ratio_cap,
                sub_scores={
                    "skill": round(r.skill_score, 1),
                    "semantic": round(r.semantic_score, 1),
                    "experience": round(r.experience_score, 1),
                    "education": round(r.education_score, 1),
                    "project": round(r.project_score, 1),
                },
                matched_skills_top=top_matched,
                matched_skills_count=len(r.matched_skills),
                missing_skills_count=len(r.missing_skills),
            )
        )

    return MatchResultsListResponse(
        jd_id=jd.id,
        job_title=jd.title,
        total_candidates=len(ranked_items),
        results=ranked_items,
    )


@router.get("/candidates/{id}", response_model=CandidateAnalysisResponse)
def get_candidate_analysis(
    id: int,
    jd_id: int = Query(..., description="Job Description ID to evaluate against"),
    db: Session = Depends(get_db),
) -> CandidateAnalysisResponse:
    """Return full detailed candidate analysis report with evidence and explanations."""
    cand = db.query(Candidate).filter(Candidate.id == id).first()
    if not cand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {id} not found.",
        )

    match_rec = (
        db.query(MatchResultRecord)
        .filter(
            MatchResultRecord.candidate_id == id,
            MatchResultRecord.jd_id == jd_id,
        )
        .first()
    )

    if not match_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match analysis not found for candidate {id} and JD {jd_id}. Run matching first.",
        )

    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    req_years = jd.min_experience_years if jd else 0.0

    exp_ev = (match_rec.evidence or {}).get("experience", {})
    rel_years = exp_ev.get("relevant_years", exp_ev.get("candidate_years", 0.0))
    tot_years = exp_ev.get("total_years")
    if (tot_years is None or tot_years == 0.0) and cand and cand.profile_json:
        tot_years = cand.profile_json.get("total_experience_years", 0.0)
    if tot_years is None:
        tot_years = rel_years
    rel_years = min(rel_years, tot_years)

    # Experience comparison based on relevant years
    ratio = min(rel_years / req_years, 1.0) if req_years > 0 else 1.0
    meets_req = rel_years >= req_years if req_years > 0 else True

    from app.config import get_settings

    cfg = get_settings()

    exp_cap_applied = (match_rec.explanation or {}).get("experience_cap_applied")
    if exp_cap_applied is None:
        exp_cap_applied = (
            req_years > 0.0
            and rel_years < (cfg.hard_req_experience_ratio_cap * req_years)
            and (match_rec.final_score >= cfg.threshold_medium)
        )

    exp_comparison = {
        "required_years": req_years,
        "found_years": rel_years,
        "relevant_years": rel_years,
        "total_years": tot_years,
        "ratio": round(ratio, 2),
        "percentage": int(ratio * 100),
        "meets_requirement": meets_req,
        "cap_ratio": cfg.hard_req_experience_ratio_cap,
        "experience_cap_applied": bool(exp_cap_applied),
    }

    sub_scores = {
        "skill": round(match_rec.skill_score, 1),
        "semantic": round(match_rec.semantic_score, 1),
        "experience": round(match_rec.experience_score, 1),
        "education": round(match_rec.education_score, 1),
        "project": round(match_rec.project_score, 1),
    }

    explanation_data = match_rec.explanation or {}
    bullets = explanation_data.get("bullet_points", [])
    headline = explanation_data.get("headline", "")
    recommendation = explanation_data.get("recommendation", "")

    extracted_info = {
        "total_experience_years": tot_years,
        "relevant_experience_years": rel_years,
        "education_level": cand.profile_json.get("education_level", "bachelor"),
        "job_titles": cand.profile_json.get("job_titles", []),
        "sections_found": [
            k for k, v in cand.profile_json.get("sections", {}).items() if v.strip()
        ],
        "skills_count": len(cand.profile_json.get("skills", [])),
    }

    return CandidateAnalysisResponse(
        candidate_id=cand.id,
        name=cand.name,
        email=cand.email,
        phone=cand.phone,
        filename=cand.filename,
        overall_score=round(match_rec.final_score, 1),
        relevant_years=rel_years,
        total_years=tot_years,
        status_label=match_rec.status_label,
        experience_cap_applied=bool(exp_cap_applied),
        possible_keyword_stuffing=bool((match_rec.explanation or {}).get("possible_keyword_stuffing", False)),
        required_years=req_years,
        found_years=rel_years,
        cap_ratio=cfg.hard_req_experience_ratio_cap,
        sub_scores=sub_scores,
        extracted_info=extracted_info,
        matched_skills=match_rec.matched_skills,
        partial_skills=match_rec.partial_skills,
        missing_skills=match_rec.missing_skills,
        experience_comparison=exp_comparison,
        explanation_bullets=bullets,
        headline=headline,
        recommendation=recommendation,
        raw_evidence=match_rec.evidence,
    )


@router.get("/results/export.csv")
def export_results_csv(
    jd_id: int = Query(..., description="ID of the Job Description"),
    db: Session = Depends(get_db),
) -> Response:
    """Generate and download CSV export of ranked candidates for a Job Description."""
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job Description with ID {jd_id} not found.",
        )

    records = (
        db.query(MatchResultRecord)
        .filter(MatchResultRecord.jd_id == jd_id)
        .order_by(MatchResultRecord.final_score.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # CSV Header
    writer.writerow([
        "Rank",
        "Candidate Name",
        "Final Score (%)",
        "Status",
        "Experience Cap Applied",
        "Experience (Years)",
        "Skill Score",
        "Semantic Score",
        "Experience Score",
        "Education Score",
        "Project Score",
        "Matched Skills",
        "Missing Skills",
    ])

    for rank, r in enumerate(records, start=1):
        cand = r.candidate
        exp_years = (
            cand.profile_json.get("total_experience_years", 0.0)
            if cand and cand.profile_json
            else 0.0
        )
        exp_cap = (
            bool((r.explanation or {}).get("experience_cap_applied", False))
        )
        matched_str = "; ".join([
            m.get("jd_skill", m.get("skill", str(m))) if isinstance(m, dict) else str(m)
            for m in r.matched_skills
        ])
        missing_str = "; ".join(r.missing_skills)

        writer.writerow([
            rank,
            cand.name if cand else "Unknown",
            f"{r.final_score:.1f}",
            r.status_label,
            str(exp_cap),
            f"{exp_years:.1f}",
            f"{r.skill_score:.1f}",
            f"{r.semantic_score:.1f}",
            f"{r.experience_score:.1f}",
            f"{r.education_score:.1f}",
            f"{r.project_score:.1f}",
            matched_str,
            missing_str,
        ])

    csv_data = output.getvalue()
    filename = f"ranked_candidates_jd_{jd_id}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/reset")
def reset_system_data() -> dict[str, Any]:
    """Delete all database records (matches, candidates, JDs) for demo/test resets."""
    reset_all_data()
    return {"message": "All database records have been reset successfully.", "deleted": True}

