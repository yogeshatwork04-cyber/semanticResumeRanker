"""Job Description endpoints: creation (text/file), retrieval, and editing."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JobDescription
from app.schemas import JDResponse, JDUpdateRequest
from app.services.jd_extractor import get_jd_extractor
from app.services.parser import DocumentParseError, EmptyDocumentError, parse_document

router = APIRouter(prefix="/jd", tags=["Job Description"])

ALLOWED_JD_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("", response_model=JDResponse, status_code=status.HTTP_201_CREATED)
async def create_job_description(
    request: Request,
    db: Session = Depends(get_db),
) -> JDResponse:
    """Create and extract structured Job Description from JSON body, form text, or uploaded file."""
    content_type = request.headers.get("content-type", "").lower()
    raw_text: str = ""

    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        text_field = form.get("text")

        if file and hasattr(file, "filename") and file.filename:
            filename = file.filename
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in ALLOWED_JD_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(ALLOWED_JD_EXTENSIONS)}",
                )

            content = await file.read()
            if len(content) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File exceeds maximum allowed size of 5 MB ({len(content)} bytes).",
                )

            try:
                raw_text = parse_document(content, filename)
            except EmptyDocumentError as err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Uploaded JD file is empty or scanned: {err}",
                ) from err
            except DocumentParseError as err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to parse JD document: {err}",
                ) from err
        elif text_field and str(text_field).strip():
            raw_text = str(text_field).strip()
    else:
        # JSON body or plain text
        try:
            body = await request.json()
            if isinstance(body, dict):
                raw_text = body.get("text", "").strip()
            elif isinstance(body, str):
                raw_text = body.strip()
        except Exception:
            body_bytes = await request.body()
            raw_text = body_bytes.decode("utf-8", errors="ignore").strip()

    if not raw_text or len(raw_text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either valid 'text' (min 10 chars) in JSON body or upload a valid file.",
        )

    extractor = get_jd_extractor()
    extracted = extractor.extract_jd(raw_text)

    jd_model = JobDescription(
        title=extracted.get("title", "Target Position"),
        raw_text=raw_text,
        required_skills=extracted.get("required_skills", []),
        preferred_skills=extracted.get("preferred_skills", []),
        min_experience_years=extracted.get("min_experience_years", 0.0),
        education_level=extracted.get("education_level", "bachelor"),
        responsibilities=extracted.get("responsibilities", []),
    )
    db.add(jd_model)
    db.commit()
    db.refresh(jd_model)

    return JDResponse.model_validate(jd_model)


@router.get("/{id}", response_model=JDResponse)
def get_job_description(id: int, db: Session = Depends(get_db)) -> JDResponse:
    """Retrieve structured Job Description by ID."""
    jd = db.query(JobDescription).filter(JobDescription.id == id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job Description with ID {id} not found.",
        )
    return JDResponse.model_validate(jd)


@router.put("/{id}", response_model=JDResponse)
def update_job_description(
    id: int,
    payload: JDUpdateRequest,
    db: Session = Depends(get_db),
) -> JDResponse:
    """Allow recruiter to edit extracted skills, experience requirements, or role metadata."""
    jd = db.query(JobDescription).filter(JobDescription.id == id).first()
    if not jd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job Description with ID {id} not found.",
        )

    if payload.title is not None:
        extractor = get_jd_extractor()
        jd.title = extractor._clean_title(payload.title)
    if payload.required_skills is not None:
        jd.required_skills = [s.strip() for s in payload.required_skills if s.strip()]
    if payload.preferred_skills is not None:
        jd.preferred_skills = [s.strip() for s in payload.preferred_skills if s.strip()]
    if payload.min_experience_years is not None:
        jd.min_experience_years = max(0.0, float(payload.min_experience_years))
    if payload.education_level is not None:
        jd.education_level = payload.education_level.lower().strip()
    if payload.responsibilities is not None:
        jd.responsibilities = [r.strip() for r in payload.responsibilities if r.strip()]

    db.commit()
    db.refresh(jd)
    return JDResponse.model_validate(jd)
