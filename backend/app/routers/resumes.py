"""Resume upload and retrieval endpoints supporting multi-file batches."""

import anyio
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Candidate
from app.schemas import CandidateSummaryResponse, CandidateUploadBatchResponse
from app.services.parser import DocumentParseError, EmptyDocumentError, parse_document
from app.services.resume_extractor import get_resume_extractor

router = APIRouter(prefix="/resumes", tags=["Resumes"])

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_BATCH_SIZE = 30


def _parse_and_extract_resume(content: bytes, filename: str) -> dict:
    """Parse document bytes and run resume extraction (runs inside thread pool)."""
    raw_text = parse_document(content, filename)
    extractor = get_resume_extractor()
    return extractor.extract_resume(raw_text, filename)


@router.post("", response_model=CandidateUploadBatchResponse, status_code=status.HTTP_201_CREATED)
async def upload_resumes(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> CandidateUploadBatchResponse:
    """Multi-file resume upload endpoint with batch safety and per-file error handling."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded. Provide at least one PDF or DOCX resume.",
        )

    if len(files) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size of {len(files)} exceeds maximum allowed limit of {MAX_BATCH_SIZE} files.",
        )

    saved_candidates: list[Candidate] = []
    errors: list[dict[str, str]] = []

    for file in files:
        filename = file.filename or "unknown_resume"
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        # Format validation
        if ext not in ALLOWED_RESUME_EXTENSIONS:
            err_msg = f"Unsupported file format '{ext}'. Allowed: {', '.join(ALLOWED_RESUME_EXTENSIONS)}"
            failed_candidate = Candidate(
                filename=filename,
                name="Unknown",
                parse_status="failed",
                parse_error=err_msg,
                profile_json={},
            )
            db.add(failed_candidate)
            db.commit()
            db.refresh(failed_candidate)
            saved_candidates.append(failed_candidate)
            errors.append({"filename": filename, "error": err_msg})
            continue

        # Size check
        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            err_msg = f"File exceeds maximum allowed size of 5 MB ({len(content)} bytes)."
            failed_candidate = Candidate(
                filename=filename,
                name="Unknown",
                parse_status="failed",
                parse_error=err_msg,
                profile_json={},
            )
            db.add(failed_candidate)
            db.commit()
            db.refresh(failed_candidate)
            saved_candidates.append(failed_candidate)
            errors.append({"filename": filename, "error": err_msg})
            continue

        # Parsing in thread pool to prevent blocking event loop
        try:
            profile = await anyio.to_thread.run_sync(
                _parse_and_extract_resume, content, filename
            )
            is_failed = profile.get("status") == "failed"
            candidate = Candidate(
                filename=filename,
                name=profile.get("name", "Candidate"),
                email=profile.get("email"),
                phone=profile.get("phone"),
                raw_text=profile.get("raw_text"),
                profile_json=profile,
                parse_status="failed" if is_failed else "parsed",
                parse_error=profile.get("error") if is_failed else None,
            )
            db.add(candidate)
            db.commit()
            db.refresh(candidate)
            saved_candidates.append(candidate)
            if is_failed:
                errors.append({"filename": filename, "error": profile.get("error") or "Extraction failed"})
        except EmptyDocumentError as err:
            err_msg = f"Empty or scanned document: {err}"
            failed_candidate = Candidate(
                filename=filename,
                name="Unparseable Document",
                parse_status="failed",
                parse_error=err_msg,
                profile_json={},
            )
            db.add(failed_candidate)
            db.commit()
            db.refresh(failed_candidate)
            saved_candidates.append(failed_candidate)
            errors.append({"filename": filename, "error": err_msg})
        except DocumentParseError as err:
            err_msg = f"Parse error: {err}"
            failed_candidate = Candidate(
                filename=filename,
                name="Unparseable Document",
                parse_status="failed",
                parse_error=err_msg,
                profile_json={},
            )
            db.add(failed_candidate)
            db.commit()
            db.refresh(failed_candidate)
            saved_candidates.append(failed_candidate)
            errors.append({"filename": filename, "error": err_msg})
        except Exception as err:
            err_msg = f"Unexpected processing error: {err}"
            failed_candidate = Candidate(
                filename=filename,
                name="Unparseable Document",
                parse_status="failed",
                parse_error=err_msg,
                profile_json={},
            )
            db.add(failed_candidate)
            db.commit()
            db.refresh(failed_candidate)
            saved_candidates.append(failed_candidate)
            errors.append({"filename": filename, "error": err_msg})

    candidate_summaries = [
        CandidateSummaryResponse(
            id=c.id,
            filename=c.filename,
            name=c.name,
            email=c.email,
            phone=c.phone,
            total_experience_years=(
                c.profile_json.get("total_experience_years", 0.0)
                if c.parse_status == "parsed"
                else 0.0
            ),
            education_level=(
                c.profile_json.get("education_level", "none")
                if c.parse_status == "parsed"
                else "none"
            ),
            skills=(
                c.profile_json.get("skills", [])
                if c.parse_status == "parsed"
                else []
            ),
            parse_status=c.parse_status,
            parse_error=c.parse_error,
            created_at=c.created_at,
        )
        for c in saved_candidates
    ]

    successful_count = sum(1 for c in saved_candidates if c.parse_status == "parsed")
    failed_count = sum(1 for c in saved_candidates if c.parse_status == "failed")

    return CandidateUploadBatchResponse(
        total_uploaded=len(files),
        successful=successful_count,
        failed=failed_count,
        candidates=candidate_summaries,
        errors=errors,
    )


@router.get("", response_model=list[CandidateSummaryResponse])
def list_candidates(db: Session = Depends(get_db)) -> list[CandidateSummaryResponse]:
    """List all candidate profiles present in the system."""
    candidates = db.query(Candidate).order_by(Candidate.id.desc()).all()
    return [
        CandidateSummaryResponse(
            id=c.id,
            filename=c.filename,
            name=c.name,
            email=c.email,
            phone=c.phone,
            total_experience_years=(
                c.profile_json.get("total_experience_years", 0.0)
                if c.parse_status == "parsed"
                else 0.0
            ),
            education_level=(
                c.profile_json.get("education_level", "none")
                if c.parse_status == "parsed"
                else "none"
            ),
            skills=(
                c.profile_json.get("skills", [])
                if c.parse_status == "parsed"
                else []
            ),
            parse_status=c.parse_status,
            parse_error=c.parse_error,
            created_at=c.created_at,
        )
        for c in candidates
    ]

