"""Unit tests verifying relative ranking order on the synthetic resume set."""

from pathlib import Path

from app.services.jd_extractor import get_jd_extractor
from app.services.parser import parse_document
from app.services.resume_extractor import get_resume_extractor
from app.services.scorer import get_resume_scorer

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data"


def test_ranking_relative_order():
    """Verify strong match > good match > wrong domain on the sample dataset."""
    jd_extractor = get_jd_extractor()
    resume_extractor = get_resume_extractor()
    scorer = get_resume_scorer()

    jd_text = (SAMPLE_DIR / "job_description.txt").read_text(encoding="utf-8")
    jd_data = jd_extractor.extract_jd(jd_text)

    # 1. Parse Strong Match
    strong_path = SAMPLE_DIR / "resumes" / "01_strong_match_alex_chen.pdf"
    strong_text = parse_document(strong_path, strong_path.name)
    strong_profile = resume_extractor.extract_resume(strong_text, strong_path.name)
    strong_res = scorer.score_candidate(strong_profile, jd_data)

    # 2. Parse Good Match
    good_path = SAMPLE_DIR / "resumes" / "02_good_match_jordan_taylor.docx"
    good_text = parse_document(good_path, good_path.name)
    good_profile = resume_extractor.extract_resume(good_text, good_path.name)
    good_res = scorer.score_candidate(good_profile, jd_data)

    # 3. Parse Wrong Domain (Frontend dev)
    wrong_path = SAMPLE_DIR / "resumes" / "04_wrong_domain_liam_oconnor.docx"
    wrong_text = parse_document(wrong_path, wrong_path.name)
    wrong_profile = resume_extractor.extract_resume(wrong_text, wrong_path.name)
    wrong_res = scorer.score_candidate(wrong_profile, jd_data)

    # 4. Parse Keyword Stuffer
    stuffer_path = SAMPLE_DIR / "resumes" / "06_keyword_stuffer_kevin_brooks.docx"
    stuffer_text = parse_document(stuffer_path, stuffer_path.name)
    stuffer_profile = resume_extractor.extract_resume(stuffer_text, stuffer_path.name)
    stuffer_res = scorer.score_candidate(stuffer_profile, jd_data)

    # Assert relative order:
    # Strong Match must outperform Good Match
    assert strong_res.final_score > good_res.final_score
    # Good Match must comfortably beat Wrong Domain
    assert good_res.final_score > wrong_res.final_score
    # Strong match should be >= 80%
    assert strong_res.final_score >= 80.0
    # Wrong domain should be low (< 50%)
    assert wrong_res.final_score < 50.0
    # Strong match must beat keyword stuffer
    assert strong_res.final_score > stuffer_res.final_score
