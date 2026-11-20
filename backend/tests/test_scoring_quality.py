"""Comprehensive unit tests validating scoring quality, defense mechanisms, and calibrations."""

from pathlib import Path

from app.config import get_settings
from app.services.jd_extractor import get_jd_extractor
from app.services.parser import parse_document
from app.services.resume_extractor import get_resume_extractor
from app.services.scorer import get_resume_scorer

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data"
settings = get_settings()


def _get_parsed_jd():
    jd_text = (SAMPLE_DIR / "job_description.txt").read_text(encoding="utf-8")
    return get_jd_extractor().extract_jd(jd_text)


def _get_scored_sample_set():
    """Helper to parse and score all sample resumes."""
    resume_extractor = get_resume_extractor()
    scorer = get_resume_scorer()

    jd_data = _get_parsed_jd()

    results = {}
    for path in sorted((SAMPLE_DIR / "resumes").glob("*")):
        if path.suffix.lower() in [".pdf", ".docx"] and "scanned" not in path.name:
            text = parse_document(path, path.name)
            profile = resume_extractor.extract_resume(text, path.name)
            res = scorer.score_candidate(profile, jd_data)
            results[path.name] = (profile, res)
    return results


def test_keyword_stuffer_defense():
    """(a) Keyword stuffer (Kevin Brooks) must rank below all genuinely good matches."""
    results = _get_scored_sample_set()

    kevin_score = results["06_keyword_stuffer_kevin_brooks.docx"][1].final_score
    alex_score = results["01_strong_match_alex_chen.pdf"][1].final_score
    jordan_score = results["02_good_match_jordan_taylor.docx"][1].final_score
    david_score = results["10_two_column_david_kim.pdf"][1].final_score
    rachel_score = results["11_good_match_rachel_green.pdf"][1].final_score

    assert kevin_score < alex_score
    assert kevin_score < jordan_score
    assert kevin_score < david_score
    assert kevin_score < rachel_score

    # Check evidence source tracking
    kevin_evidence = results["06_keyword_stuffer_kevin_brooks.docx"][1].evidence["skills"]
    assert kevin_evidence["listed_only_penalty_applied"] is True
    assert kevin_evidence["listed_only_count"] > 5
    assert kevin_evidence["demonstrated_count"] <= 2


def test_flask_django_candidate_beats_wrong_domain():
    """(b) Backend candidates with adjacent stacks (Flask/Django) must score above wrong-domain frontend candidates."""
    results = _get_scored_sample_set()

    elena_flask = results["07_same_skills_diff_wording_elena.pdf"][1].final_score
    priya_django = results["03_partial_match_priya_sharma.pdf"][1].final_score
    liam_frontend = results["04_wrong_domain_liam_oconnor.docx"][1].final_score

    assert elena_flask > liam_frontend
    assert priya_django > liam_frontend
    assert liam_frontend < 45.0


def test_fresher_vs_strong_match():
    """(c) Fresher candidate (Samira Khan) is not scored above strong 4+ year matches."""
    results = _get_scored_sample_set()

    samira_fresher = results["09_fresher_with_projects_samira.docx"][1].final_score
    alex_strong = results["01_strong_match_alex_chen.pdf"][1].final_score
    jordan_good = results["02_good_match_jordan_taylor.docx"][1].final_score
    david_mid = results["10_two_column_david_kim.pdf"][1].final_score

    assert samira_fresher < alex_strong
    assert samira_fresher < jordan_good
    assert samira_fresher < david_mid
    # Fresher experience score must be 0
    assert results["09_fresher_with_projects_samira.docx"][1].experience_score == 0.0


def test_continuous_scores_not_identical_constants():
    """(d) Semantic and project scores across the dataset must vary continuously and not be constants."""
    results = _get_scored_sample_set()

    semantic_scores = set(res.semantic_score for _, res in results.values())
    project_scores = set(res.project_score for _, res in results.values())

    # Ensure significant variety (not just 2 or 3 fallback values)
    assert len(semantic_scores) >= 8, f"Semantic scores too uniform: {semantic_scores}"
    assert len(project_scores) >= 8, f"Project scores too uniform: {project_scores}"

    # Top candidates must land around 85-95, not saturated at 100
    alex_semantic = results["01_strong_match_alex_chen.pdf"][1].semantic_score
    jordan_semantic = results["02_good_match_jordan_taylor.docx"][1].semantic_score
    assert 85.0 <= alex_semantic <= 95.0
    assert 85.0 <= jordan_semantic <= 95.0


def test_status_thresholds():
    """(e) Status threshold categorization functions properly with strict boundary checks."""
    from app.config import get_status_label

    assert get_status_label(59.9) == "LOW"
    assert get_status_label(60.0) == "MEDIUM"
    assert get_status_label(79.9) == "MEDIUM"
    assert get_status_label(80.0) == "HIGH"
    assert get_status_label(0.0) == "LOW"
    assert get_status_label(100.0) == "HIGH"


def test_hard_req_experience_status_cap():
    """Verify that if candidate_years < 50% of required_years, status label is capped at LOW."""
    from app.config import get_status_label

    # High score (85.0) but experience 1.0y < 50% of 3.0y (1.5y) -> Capped at LOW
    assert get_status_label(85.0, candidate_years=1.0, required_years=3.0) == "LOW"

    # Medium score (68.0) but experience 0.5y < 50% of 3.0y (1.5y) -> Capped at LOW
    assert get_status_label(68.0, candidate_years=0.5, required_years=3.0) == "LOW"

    # Experience 1.5y >= 50% of 3.0y -> Not capped, maintains normal threshold (HIGH)
    assert get_status_label(85.0, candidate_years=1.5, required_years=3.0) == "HIGH"
    assert get_status_label(68.0, candidate_years=2.0, required_years=3.0) == "MEDIUM"

    # No hard requirement stated (required_years = 0) -> Normal threshold applies
    assert get_status_label(85.0, candidate_years=0.5, required_years=0.0) == "HIGH"

    results = _get_scored_sample_set()

    high_matches = [
        name for name, (_, res) in results.items() if res.final_score >= settings.threshold_high
    ]
    med_matches = [
        name
        for name, (_, res) in results.items()
        if settings.threshold_medium <= res.final_score < settings.threshold_high
    ]
    low_matches = [
        name for name, (_, res) in results.items() if res.final_score < settings.threshold_medium
    ]

    # Verify distribution is balanced and sensible
    assert len(high_matches) >= 2
    assert len(med_matches) >= 4
    assert len(low_matches) >= 2


def test_two_column_parsing_regression():
    """Regression test: two-column layout (David Kim) parses cleanly ~7.6 years, education dates not counted."""
    path = SAMPLE_DIR / "resumes" / "10_two_column_david_kim.pdf"
    assert path.exists()

    text = parse_document(path, path.name)
    resume_extractor = get_resume_extractor()
    profile = resume_extractor.extract_resume(text, path.name)

    # Experience must be ~7.6 years (from May 2019 to Present), NOT 11.9 years
    assert 7.0 <= profile["total_experience_years"] <= 8.0, (
        f"Expected experience around 7.6 yrs, got {profile['total_experience_years']}"
    )

    # Education section must contain UCLA 2015 - 2019
    edu_text = profile["sections"].get("education", "")
    assert "UCLA" in edu_text or "2015" in edu_text
    # Experience section must NOT contain 2015
    exp_text = profile["sections"].get("experience", "")
    assert "2015" not in exp_text


def test_projects_consistency_alex_chen_and_samira():
    """0.1 Projects consistency: Alex Chen has no projects section; Samira has a dedicated section."""
    from app.services.scorer import get_resume_scorer

    extractor = get_resume_extractor()
    scorer = get_resume_scorer()
    jd_data = _get_parsed_jd()

    # Alex Chen: has NO dedicated projects section
    alex_path = SAMPLE_DIR / "resumes" / "01_strong_match_alex_chen.pdf"
    alex_text = parse_document(alex_path, alex_path.name)
    alex_prof = extractor.extract_resume(alex_text, alex_path.name)
    assert "projects" not in alex_prof["sections"]
    alex_score = scorer.score_candidate(alex_prof, jd_data)
    assert alex_score.evidence["projects"]["has_dedicated_projects"] is False

    # Samira Khan: has a dedicated projects section
    samira_path = SAMPLE_DIR / "resumes" / "09_fresher_with_projects_samira.docx"
    samira_text = parse_document(samira_path, samira_path.name)
    samira_prof = extractor.extract_resume(samira_text, samira_path.name)
    assert "projects" in samira_prof["sections"]
    samira_score = scorer.score_candidate(samira_prof, jd_data)
    assert samira_score.evidence["projects"]["has_dedicated_projects"] is True


def test_explanation_skill_counts_add_up():
    """0.2 Explanation skill count consistency: demonstrated + listed == matched, matched + partial + missing == total."""
    from app.services.explainer import get_score_explainer
    from app.services.scorer import get_resume_scorer

    extractor = get_resume_extractor()
    scorer = get_resume_scorer()
    explainer = get_score_explainer()
    jd_data = _get_parsed_jd()

    alex_path = SAMPLE_DIR / "resumes" / "01_strong_match_alex_chen.pdf"
    alex_text = parse_document(alex_path, alex_path.name)
    alex_prof = extractor.extract_resume(alex_text, alex_path.name)
    alex_score = scorer.score_candidate(alex_prof, jd_data)
    explanation = explainer.explain(alex_score)

    skills_text = explanation["skills_explanation"]
    # Verify text format
    assert "Matched 13 of 15 JD skills:" in skills_text
    assert "demonstrated in work history" in skills_text
    assert "listed only" in skills_text
    assert "1 partial" in skills_text
    assert "1 missing: Message Queues" in skills_text


def test_experience_cap_applied_flag_logic():
    """0.3 Experience cap flag: True ONLY when status was lowered by experience < 50% rule."""
    from app.config import check_experience_cap

    # Case 1: Samira Khan (score ~61.4% [would be MEDIUM], 0.0y < 1.5y) -> lowered to LOW -> True
    status, cap_applied = check_experience_cap(61.4, candidate_years=0.0, required_years=3.0)
    assert status == "LOW"
    assert cap_applied is True

    # Case 2: Chloe Bennett (score ~51.8% [already LOW by score], 2.1y) -> LOW not due to cap -> False
    status, cap_applied = check_experience_cap(51.8, candidate_years=2.1, required_years=3.0)
    assert status == "LOW"
    assert cap_applied is False

    # Case 3: Candidate with 0.5y experience and 45.0% score -> already LOW by score -> False
    status, cap_applied = check_experience_cap(45.0, candidate_years=0.5, required_years=3.0)
    assert status == "LOW"
    assert cap_applied is False

    # Case 4: Alex Chen (score 92.8% [HIGH], 7.9y >= 1.5y) -> not capped -> False
    status, cap_applied = check_experience_cap(92.8, candidate_years=7.9, required_years=3.0)
    assert status == "HIGH"
    assert cap_applied is False


def test_keyword_stuffing_badge_rules():
    """Verify stuffing badge triggers only if listed_only >= 8 AND share >= 70% AND demonstrated < 2.

    Liam O'Connor: 1 matched skill (Git), listed only -> NOT flagged (< 8 listed).
    Kevin Brooks: 13 listed-only skills, 0 demonstrated -> FLAGGED.
    Vikram Nair: 18 listed-only skills, 0 demonstrated -> FLAGGED.
    Tanvi Shah: 15 listed-only skills, 0 demonstrated -> FLAGGED.
    """
    from app.services.jd_extractor import get_jd_extractor
    from app.services.parser import parse_document
    from app.services.resume_extractor import get_resume_extractor
    from app.services.scorer import get_resume_scorer

    jd_extractor = get_jd_extractor()
    resume_extractor = get_resume_extractor()
    scorer = get_resume_scorer()

    # 1. Liam O'Connor (Python JD) -> NOT FLAGGED
    py_jd = jd_extractor.extract_jd(
        (SAMPLE_DIR / "job_description.txt").read_text(encoding="utf-8")
    )
    liam_path = SAMPLE_DIR / "resumes" / "04_wrong_domain_liam_oconnor.docx"
    liam_prof = resume_extractor.extract_resume(parse_document(liam_path, liam_path.name), liam_path.name)
    liam_res = scorer.score_candidate(liam_prof, py_jd)
    assert liam_res.possible_keyword_stuffing is False, "Liam O'Connor should NOT be flagged as keyword stuffer"

    # 2. Kevin Brooks (Python JD) -> FLAGGED
    kevin_path = SAMPLE_DIR / "resumes" / "06_keyword_stuffer_kevin_brooks.docx"
    kevin_prof = resume_extractor.extract_resume(parse_document(kevin_path, kevin_path.name), kevin_path.name)
    kevin_res = scorer.score_candidate(kevin_prof, py_jd)
    assert kevin_res.possible_keyword_stuffing is True, "Kevin Brooks should be flagged as keyword stuffer"

    # 3. Vikram Nair (Java JD) -> FLAGGED
    java_jd_path = SAMPLE_DIR / "java_test" / "sample_JD_java_spring_boot.txt"
    java_jd = jd_extractor.extract_jd(java_jd_path.read_text(encoding="utf-8"))
    vikram_path = SAMPLE_DIR / "java_test" / "05_vikram_nair_keyword_stuffer.pdf"
    vikram_prof = resume_extractor.extract_resume(parse_document(vikram_path, vikram_path.name), vikram_path.name)
    vikram_res = scorer.score_candidate(vikram_prof, java_jd)
    assert vikram_res.possible_keyword_stuffing is True, "Vikram Nair should be flagged as keyword stuffer"

    # 4. Tanvi Shah (DS JD) -> FLAGGED
    ds_jd_path = SAMPLE_DIR / "data_scientist_test" / "sample_JD_data_scientist.txt"
    ds_jd = jd_extractor.extract_jd(ds_jd_path.read_text(encoding="utf-8"))
    tanvi_path = SAMPLE_DIR / "data_scientist_test" / "05_tanvi_shah_keyword_stuffer.pdf"
    tanvi_prof = resume_extractor.extract_resume(parse_document(tanvi_path, tanvi_path.name), tanvi_path.name)
    tanvi_res = scorer.score_candidate(tanvi_prof, ds_jd)
    assert tanvi_res.possible_keyword_stuffing is True, "Tanvi Shah should be flagged as keyword stuffer"


def test_role_relevance_three_tiers():
    """Verify three explainable tiers per role:

    Tier 1.0: >= 2 JD skills demonstrated.
    Tier 0.5: exactly 1 JD skill demonstrated OR (0 skills and semantic cosine >= 0.55).
    Tier 0.0: 0 JD skills and semantic cosine < 0.55.
    """
    from app.services.scorer import get_resume_scorer

    scorer = get_resume_scorer()

    # Role with 2 JD skills -> Tier 1.0
    _, ev_full = scorer.compute_experience_score(
        candidate_years=3.0,
        required_years=3.0,
        candidate_titles=["Software Engineer"],
        jd_title="Backend Python Developer",
        candidate_roles=[{
            "header": "Python Developer | TechCorp | 2021 - 2024",
            "lines": ["Developed REST APIs with Python and managed PostgreSQL databases."],
            "start_date": "2021-01-01",
            "end_date": "2024-01-01",
        }],
        jd_required_skills=["Python", "PostgreSQL", "FastAPI"],
        jd_preferred_skills=["Docker"],
        jd_responsibilities=["Build backend REST APIs with Python and databases."],
    )
    assert ev_full["role_breakdown"][0]["tier"] == 1.0
    assert ev_full["role_breakdown"][0]["relevance"] == 1.0

    # Role with 1 JD skill -> Tier 0.5
    _, ev_half = scorer.compute_experience_score(
        candidate_years=3.0,
        required_years=3.0,
        candidate_titles=["Junior Engineer"],
        jd_title="Backend Python Developer",
        candidate_roles=[{
            "header": "Developer | TechCorp | 2021 - 2024",
            "lines": ["Built automated scripts in Python."],
            "start_date": "2021-01-01",
            "end_date": "2024-01-01",
        }],
        jd_required_skills=["Python", "PostgreSQL", "FastAPI"],
        jd_preferred_skills=["Docker"],
        jd_responsibilities=["Manage cloud deployments."],
    )
    assert ev_half["role_breakdown"][0]["tier"] == 0.5
    assert ev_half["role_breakdown"][0]["relevance"] == 0.5

    # Role with 0 JD skills and low semantic similarity -> Tier 0.0
    _, ev_zero = scorer.compute_experience_score(
        candidate_years=3.0,
        required_years=3.0,
        candidate_titles=["Customer Support"],
        jd_title="Backend Python Developer",
        candidate_roles=[{
            "header": "Customer Support Specialist | CallCenter | 2021 - 2024",
            "lines": ["Answered incoming phone calls and resolved billing issues."],
            "start_date": "2021-01-01",
            "end_date": "2024-01-01",
        }],
        jd_required_skills=["Python", "PostgreSQL", "FastAPI"],
        jd_preferred_skills=["Docker"],
        jd_responsibilities=["Build high-performance REST APIs."],
    )
    assert ev_zero["role_breakdown"][0]["tier"] == 0.0
    assert ev_zero["role_breakdown"][0]["relevance"] == 0.0


