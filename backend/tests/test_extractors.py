"""Unit tests for JD and Resume extraction services."""

from pathlib import Path

from app.services.jd_extractor import get_jd_extractor
from app.services.parser import parse_document
from app.services.resume_extractor import get_resume_extractor

SAMPLE_RESUMES_DIR = Path(__file__).resolve().parent.parent.parent / "sample_data" / "resumes"
SAMPLE_JD_PATH = Path(__file__).resolve().parent.parent.parent / "sample_data" / "job_description.txt"


def test_jd_extractor_full():
    """Verify JD extraction extracts min experience, education, skills by priority, and responsibilities."""
    jd_extractor = get_jd_extractor()
    jd_text = SAMPLE_JD_PATH.read_text(encoding="utf-8")

    result = jd_extractor.extract_jd(jd_text)

    # Min experience check ("3+ years")
    assert result["min_experience_years"] == 3.0

    # Education check ("Bachelor's degree")
    assert result["education_level"] == "bachelor"

    # Required skills
    assert "Python" in result["required_skills"]
    assert "FastAPI" in result["required_skills"]
    assert "PostgreSQL" in result["required_skills"]
    assert "Docker" in result["required_skills"]

    # Preferred skills
    assert "Redis" in result["preferred_skills"]
    assert "Kubernetes" in result["preferred_skills"]
    assert "AWS" in result["preferred_skills"]

    # Responsibilities
    assert len(result["responsibilities"]) >= 3


def test_jd_min_experience_regex_variations():
    """Test various regex patterns for years of experience."""
    jd_extractor = get_jd_extractor()

    assert jd_extractor.extract_min_experience("Requires 5+ years experience") == 5.0
    assert jd_extractor.extract_min_experience("Must have 2-4 years of experience") == 2.0
    assert jd_extractor.extract_min_experience("Minimum 4 yrs in backend engineering") == 4.0
    assert jd_extractor.extract_min_experience("At least 3 years building microservices") == 3.0


def test_resume_extractor_strong_match():
    """Verify resume extraction on strong match candidate."""
    extractor = get_resume_extractor()
    resume_path = SAMPLE_RESUMES_DIR / "01_strong_match_alex_chen.pdf"
    text = parse_document(resume_path, filename=resume_path.name)

    result = extractor.extract_resume(text, filename=resume_path.name)

    assert result["name"] == "Alex Chen"
    assert result["email"] == "alex.chen@example.com"
    assert "555" in result["phone"]
    assert "Python" in result["skills"]
    assert "FastAPI" in result["skills"]
    assert "PostgreSQL" in result["skills"]
    assert result["total_experience_years"] >= 4.0
    assert result["education_level"] == "bachelor"
    assert len(result["job_titles"]) >= 1


def test_resume_extractor_career_changer():
    """Verify extraction for candidate with varied history and degree."""
    extractor = get_resume_extractor()
    resume_path = SAMPLE_RESUMES_DIR / "05_career_changer_maya_lin.pdf"
    text = parse_document(resume_path, filename=resume_path.name)

    result = extractor.extract_resume(text, filename=resume_path.name)

    assert result["name"] == "Maya Lin"
    assert result["email"] == "maya.lin@example.com"
    assert "FastAPI" in result["skills"]
    assert result["total_experience_years"] > 0


def test_jd_section_handling_java():
    """Verify explicit Required Skills / Preferred Skills sections, title stripping, and responsibilities."""
    jd_extractor = get_jd_extractor()
    raw_jd = """Job Title: Senior Java Backend Developer (Spring Boot)

About the Role
We are looking for a Java Backend Developer to design, build and maintain
scalable backend services for our fintech platform.

Responsibilities
- Design, develop and maintain REST APIs using Java and Spring Boot.
- Build and deploy microservices that communicate through
  REST and message queues.
- Write efficient SQL queries and manage relational databases such as MySQL and PostgreSQL.
- Use Hibernate and JPA for data access and optimise database performance.
- Write unit and integration tests using JUnit and Mockito.

Required Skills
- Java
- Spring Boot
- REST APIs
- SQL
- Hibernate / JPA
- Microservices
- JUnit
- Git
- Maven

Preferred Skills
- Docker
- Kubernetes
- AWS
- Kafka
- Redis
- Jenkins
- CI/CD
"""
    result = jd_extractor.extract_jd(raw_jd)

    # 1. Title prefix stripped
    assert result["title"] == "Senior Java Backend Developer (Spring Boot)"

    # 2. Required skills from explicit section (Hibernate / JPA split)
    req = result["required_skills"]
    assert "Hibernate" in req
    assert "JPA" in req
    assert "SQL" in req
    assert "Spring Boot" in req
    # MySQL and PostgreSQL are examples in responsibilities, must NOT be required
    assert "MySQL" not in req
    assert "PostgreSQL" not in req

    # 3. Responsibilities hard-wrap joined and "About the role" excluded
    resps = result["responsibilities"]
    assert len(resps) == 5
    assert not any("about the role" in r.lower() for r in resps)
    # Check that line with hard-wrap was joined
    wrapped_resp = [r for r in resps if "microservices" in r.lower()][0]
    assert "communicate through REST and message queues" in wrapped_resp


def test_open_vocabulary_skills():
    """Verify open-vocabulary extraction and matching on non-taxonomy skills."""
    from app.services.scorer import get_resume_scorer

    jd_extractor = get_jd_extractor()
    resume_extractor = get_resume_extractor()
    scorer = get_resume_scorer()

    # JD with open-vocabulary skills (Airflow, Svelte, Terraform)
    jd_text = """Job Title: DevOps & Data Engineer

Required Skills
- Airflow
- Terraform
- Python
- Docker

Preferred Skills
- Svelte
- Kubernetes
"""
    jd_data = jd_extractor.extract_jd(jd_text)
    assert "Airflow" in jd_data["required_skills"]
    assert "Terraform" in jd_data["required_skills"]
    assert "Svelte" in jd_data["preferred_skills"]

    # Candidate with open-vocabulary skills
    resume_text = """Alex Rivers
alex@example.com | 555-0199
SKILLS
Python, Airflow, Terraform, Docker, Svelte, Linux
EXPERIENCE
Data Engineer | DataCorp | 2022 - 2025
Developed Python data pipelines using Airflow, containerized with Docker, and managed infrastructure with Terraform.
"""
    resume_data = resume_extractor.extract_resume(resume_text, "alex.txt")
    assert "Airflow" in resume_data["skills"]
    assert "Terraform" in resume_data["skills"]
    assert "Svelte" in resume_data["skills"]

    # Score candidate
    match_result = scorer.score_candidate(resume_data, jd_data)
    assert "Airflow" in match_result.matched_skills
    assert "Terraform" in match_result.matched_skills
    assert match_result.skill_score >= 80.0


def test_keyword_stuffing_badge_detection():
    """Verify keyword stuffing badge triggers when >70% listed only and <2 demonstrated."""
    from app.services.explainer import get_score_explainer
    from app.services.scorer import get_resume_scorer

    scorer = get_resume_scorer()
    explainer = get_score_explainer()

    jd_data = {
        "title": "Senior Java Developer",
        "required_skills": ["Java", "Spring Boot", "SQL", "Hibernate", "REST APIs"],
        "preferred_skills": ["Docker", "Kubernetes", "AWS"],
        "min_experience_years": 3.0,
        "education_level": "bachelor",
        "responsibilities": ["Develop REST APIs in Java and Spring Boot"],
        "raw_text": "Java Spring Boot developer required.",
    }

    # Keyword stuffer: lists skills, experience has NO tech mentions
    stuffer_resume = {
        "name": "Vikram Nair",
        "filename": "vikram.pdf",
        "skills": ["Java", "Spring Boot", "SQL", "Hibernate", "REST APIs", "Docker", "Kubernetes", "AWS"],
        "total_experience_years": 2.5,
        "education_level": "bachelor",
        "job_titles": ["Customer Support"],
        "sections": {
            "skills": "Java, Spring Boot, SQL, Hibernate, REST APIs, Docker, Kubernetes, AWS",
            "experience": "Customer Support Executive at Brightline Telecom. Answered phone calls.",
            "education": "B.Com",
        },
        "raw_text": "Customer support only.",
    }

    result = scorer.score_candidate(stuffer_resume, jd_data)
    explanation = explainer.explain(result)

    assert result.possible_keyword_stuffing is True
    assert explanation["possible_keyword_stuffing"] is True
    assert any("possible keyword stuffing" in b.lower() for b in explanation["bullet_points"])

    # Legitimate candidate: 5 demonstrated skills
    legit_resume = {
        "name": "Aarav Mehta",
        "filename": "aarav.pdf",
        "skills": ["Java", "Spring Boot", "SQL", "Hibernate", "REST APIs", "Docker", "Kubernetes", "AWS"],
        "total_experience_years": 5.0,
        "education_level": "bachelor",
        "job_titles": ["Senior Backend Engineer"],
        "sections": {
            "skills": "Java, Spring Boot, SQL, Hibernate, REST APIs, Docker, Kubernetes, AWS",
            "experience": "Senior Backend Engineer. Built REST APIs in Java and Spring Boot. Wrote SQL and Hibernate. Containerized with Docker.",
            "education": "B.Tech in Computer Science",
        },
        "raw_text": "Senior backend engineer experience.",
    }

    legit_result = scorer.score_candidate(legit_resume, jd_data)
    legit_explanation = explainer.explain(legit_result)

    assert legit_result.possible_keyword_stuffing is False
    assert legit_explanation["possible_keyword_stuffing"] is False


def test_data_scientist_jd_extraction():
    """Verify Data Scientist JD extracts exactly 8 required and 7 preferred skills."""
    jd_extractor = get_jd_extractor()
    jd_path = Path(__file__).resolve().parent.parent.parent / "sample_data" / "data_scientist_test" / "sample_JD_data_scientist.txt"
    jd_text = jd_path.read_text(encoding="utf-8")

    result = jd_extractor.extract_jd(jd_text)

    # Required skills assertion: exactly 8 skills
    expected_required = [
        "Python", "SQL", "Machine Learning", "scikit-learn",
        "Pandas", "NumPy", "Statistics", "Git",
    ]
    assert result["required_skills"] == expected_required, f"Got: {result['required_skills']}"
    assert len(result["required_skills"]) == 8

    # Preferred skills assertion: exactly 7 skills
    expected_preferred = [
        "PyTorch", "TensorFlow", "NLP", "Spark", "MLflow", "AWS", "Docker",
    ]
    assert result["preferred_skills"] == expected_preferred, f"Got: {result['preferred_skills']}"
    assert len(result["preferred_skills"]) == 7

    # Machine Learning must NOT appear in preferred
    assert "Machine Learning" not in result["preferred_skills"]
    assert result["min_experience_years"] == 2.0
    assert result["education_level"] == "master"


def test_education_detection_all_patterns():
    """Verify education detection supports all required degree patterns and picks the highest."""
    extractor = get_resume_extractor()

    degree_tests = [
        ("M.Sc. in Statistics | Delhi University", "master"),
        ("MSc Statistics", "master"),
        ("M.S. in Computer Science", "master"),
        ("MS in Software Engineering", "master"),
        ("M.Tech in AI", "master"),
        ("MTech Computer Science", "master"),
        ("M.E. in Electronics", "master"),
        ("MBA in Business Analytics", "master"),
        ("MCA from Bangalore University", "master"),
        ("M.A. in Economics", "master"),
        ("Master of Science in Data Analytics", "master"),
        ("Ph.D in Machine Learning", "phd"),
        ("PhD in Statistics", "phd"),
        ("Doctorate in Computer Science", "phd"),
        ("B.Sc. in Mathematics", "bachelor"),
        ("B.E. in Information Technology", "bachelor"),
        ("B.Tech in Computer Science", "bachelor"),
        ("BCA from Osmania", "bachelor"),
        ("BCom | Osmania University", "bachelor"),
        ("B.A. in English", "bachelor"),
        ("Bachelor of Technology", "bachelor"),
        ("Diploma in Electrical Engineering", "diploma"),
        # Multiple degrees take highest:
        ("B.Com 2016 - 2019\nMBA in Business Analytics 2019 - 2021", "master"),
        ("M.Sc. in Statistics | Delhi University | 2019 - 2021", "master"),
        ("B.Tech in CS 2014-2018, M.Tech in CS 2018-2020", "master"),
        ("B.Sc. in Physics, M.Sc. in Data Science, Ph.D in AI", "phd"),
    ]

    for text, expected in degree_tests:
        level = extractor.extract_education_level(text, text)
        assert level == expected, f"Failed for '{text}': expected {expected}, got {level}"


def test_education_abbreviations_and_false_positives():
    """Verify degree abbreviations (MS, ME, MA, BE, BA, MBA, MCA) match only as standalone tokens.

    Company names containing 'ms' or 'me' inside words (e.g. Systems, Microsystems,
    become, schema, name) must NOT yield a degree; real degree lines in several formats must.
    """
    extractor = get_resume_extractor()

    # Negative test cases: substring occurrences of ms, me, ma inside words must return 'none'
    negative_cases = [
        "Senior Systems Engineer at Microsystems Inc.",
        "Microsystems Systems Architecture",
        "Helped the company become the market leader",
        "Designed schema migration pipelines and database schemas",
        "My name is John Doe and welcome to my profile",
        "Lead developer for payment systems and game engines",
        "Came up with algorithms for distributed cache items",
        "Contact me for references",
        "Degree expected to be completed in May 2024",
        "Boston, MA",
        "Portland, ME",
    ]

    for text in negative_cases:
        level = extractor.extract_education_level(text, text)
        assert level == "none", f"False positive degree detected for '{text}': got '{level}'"

    # Degree abbreviations must NOT match outside the education section
    for abbrev_text in ["MS in Computer Science", "BE in Electronics", "MBA"]:
        # When education_section is empty, abbreviations should not match in raw text
        level_no_sec = extractor.extract_education_level(abbrev_text, "")
        assert level_no_sec == "none", f"Abbreviation '{abbrev_text}' should not match outside education section, got '{level_no_sec}'"

    # Positive test cases: real degree lines in several formats
    positive_cases = [
        ("MS in Computer Science", "master"),
        ("M.S. in Computer Science", "master"),
        ("M.S.", "master"),
        ("MS", "master"),
        ("ME in Mechanical Engineering", "master"),
        ("M.E. in Electronics", "master"),
        ("M.E.", "master"),
        ("MA in Economics", "master"),
        ("M.A. in History", "master"),
        ("M.A.", "master"),
        ("MBA in Business Analytics", "master"),
        ("MBA", "master"),
        ("mba", "master"),
        ("MCA from Delhi University", "master"),
        ("MCA", "master"),
        ("mca", "master"),
        ("BE in Computer Engineering", "bachelor"),
        ("B.E. in Information Technology", "bachelor"),
        ("B.E.", "bachelor"),
        ("BE", "bachelor"),
        ("BA in Economics", "bachelor"),
        ("B.A. in English Literature", "bachelor"),
        ("B.A.", "bachelor"),
        ("BA", "bachelor"),
        ("BS in Computer Science", "bachelor"),
        ("B.S. in Computer Science", "bachelor"),
        ("B.S.", "bachelor"),
        ("BS", "bachelor"),
        ("Bachelor of Science in General Studies", "bachelor"),
        ("Master of Science in Software Engineering", "master"),
        ("Ph.D. in Computer Science", "phd"),
    ]

    for text, expected in positive_cases:
        level = extractor.extract_education_level(text, text)
        assert level == expected, f"Failed to detect degree for '{text}': expected '{expected}', got '{level}'"


def test_education_detection_robustness():
    """Verify specific user robustness constraints:

    - MUST yield master: 'Stanford University, MS in Computer Science', 'University of Texas, M.S. Data Science | 2019 - 2021', 'MS (Computer Science), 2019'
    - MUST NOT yield any degree from state codes: 'Boston University, Boston, MA | 2016 - 2020', 'Portland, ME', 'Austin, MA 02101 | email | phone'
    - Section recognition: 'Academic Background', 'Academics', 'Qualifications', 'Educational Qualifications', 'Education & Training'
    - No header at all: abbreviation allowed on line with university/college/institute/school keyword or year range
    """
    extractor = get_resume_extractor()

    # 1. MUST yield master
    must_master = [
        "Stanford University, MS in Computer Science",
        "University of Texas, M.S. Data Science | 2019 - 2021",
        "MS (Computer Science), 2019",
    ]
    for text in must_master:
        assert extractor.extract_education_level(text, text) == "master", f"Expected master for '{text}'"

    # 2. MUST NOT yield any degree from state codes
    must_not_degree = [
        "Boston University, Boston, MA | 2016 - 2020",
        "Portland, ME",
        "Austin, MA 02101 | email | phone",
    ]
    for text in must_not_degree:
        assert extractor.extract_education_level(text, text) == "none", f"Expected none for '{text}'"

    # Header line in full resume parse
    hr_text = "Austin, MA 02101 | email | phone\n\nExperience\nSoftware Engineer at TechCorp\n"
    assert extractor.extract_resume(hr_text)["education_level"] == "none"

    # 3. Section recognition:
    section_headings = [
        "Academic Background",
        "Academics",
        "Qualifications",
        "Educational Qualifications",
        "Education & Training",
    ]
    for heading in section_headings:
        resume_text = f"Jane Doe\njane@example.com\n\n{heading}\nMS in Computer Science | 2018 - 2020\n\nExperience\nSoftware Engineer\n"
        parsed = extractor.extract_resume(resume_text)
        assert parsed["sections"].get("education", "").strip(), f"Heading '{heading}' not recognized"
        assert parsed["education_level"] == "master", f"Expected master for heading '{heading}'"

    # 4. No header at all:
    no_header_text = (
        "John Doe\n"
        "john@example.com\n"
        "B.Tech in Computer Science | XYZ University | 2016 - 2020\n"
        "Experience\n"
        "Software Engineer at Acme Corp | 2020 - 2023\n"
    )
    assert extractor.extract_resume(no_header_text)["education_level"] == "bachelor"

    no_header_abbrevs = [
        ("MS in Computer Science | Stanford University | 2018 - 2020", "master"),
        ("BE in Electronics | City College of Engineering | 2014 - 2018", "bachelor"),
        ("MBA | Harvard Business School | 2019 - 2021", "master"),
    ]
    for line, exp in no_header_abbrevs:
        raw = f"Candidate Name\nemail@test.com\n{line}\nExperience\nEngineer\n"
        assert extractor.extract_resume(raw)["education_level"] == exp


def test_unsegmented_experience_lines_with_years_no_false_positive_degrees():
    """Verify resumes without an education heading containing year ranges in experience do not yield degrees.

    Checks:
    - 'Backend Engineer | CloudNest Labs | Jan 2021 - Dec 2025'
    - 'Built services designed to be scalable and reliable (2022 - 2024)'
    - 'Please contact me for references, available 2025'
    - 'Scrum Master | Acme Corp | 2019 - 2022'
    - 'Master of Ceremonies for the annual company event, 2023'
    And verifies abbreviations (MS, ME, MA, BE, BA) only match as uppercase tokens or with dots.
    """
    extractor = get_resume_extractor()

    false_positive_lines = [
        "Backend Engineer | CloudNest Labs | Jan 2021 - Dec 2025",
        "Built services designed to be scalable and reliable (2022 - 2024)",
        "Please contact me for references, available 2025",
        "Scrum Master | Acme Corp | 2019 - 2022",
        "Master of Ceremonies for the annual company event, 2023",
        "Expected to be in the office (2022 - 2024)",
        "Presented to me in 2023",
        "Implemented schema changes across microservices (2021 - 2023)",
    ]

    for line in false_positive_lines:
        raw_resume = f"John Doe\njohn.doe@example.com\n\nExperience\n{line}\n"
        parsed = extractor.extract_resume(raw_resume)
        assert parsed["education_level"] == "none", (
            f"Line '{line}' erroneously yielded degree level '{parsed['education_level']}'"
        )


def test_jd_education_requirement_preference_and_lowest_level():
    """Verify JD education requirement ignores preference markers and selects lowest required degree."""
    from app.services.jd_extractor import get_jd_extractor

    jd_extractor = get_jd_extractor()

    cases = [
        ("Bachelor's degree required; Master's preferred", "bachelor"),
        ("Master's degree in Statistics", "master"),
        ("Bachelor's or Master's in CS", "bachelor"),
        ("PhD is a plus, Bachelor's required", "bachelor"),
        ("Bachelor's degree in Marketing, Business or a related field. MBA is a plus.", "bachelor"),
        ("PhD in Computer Science", "phd"),
    ]

    for jd_text, expected_level in cases:
        level = jd_extractor.extract_education_level(jd_text)
        assert level == expected_level, (
            f"JD '{jd_text}' extracted '{level}', expected '{expected_level}'"
        )


def test_degree_coverage_indian_and_common_degrees():
    """Verify degree coverage for Indian and common degree acronyms and negative false positives."""
    extractor = get_resume_extractor()

    bachelor_cases = [
        "BBA in Marketing | Christ University | 2017 - 2020",
        "BBM in Finance | Bangalore University | 2016 - 2019",
        "BMS in Management | Mumbai University | 2015 - 2018",
        "BFA in Applied Arts | Delhi University | 2016 - 2020",
        "B.Ed | Calicut University | 2017 - 2019",
        "B.Pharm | Manipal University | 2015 - 2019",
        "B.Arch | IIT Roorkee | 2014 - 2019",
        "LLB | Faculty of Law, DU | 2016 - 2019",
    ]

    for line in bachelor_cases:
        raw = f"Candidate Name\nemail@example.com\n\nEducation\n{line}\n"
        parsed = extractor.extract_resume(raw)
        assert parsed["education_level"] == "bachelor", (
            f"Line '{line}' extracted '{parsed['education_level']}', expected 'bachelor'"
        )

    master_cases = [
        "PGDM | XLRI | 2018 - 2020",
        "PGDBM | NMIMS | 2016 - 2018",
        "MFA | Jamia Millia Islamia | 2018 - 2020",
        "M.Ed | BHU | 2019 - 2021",
        "M.Pharm | NIPER | 2018 - 2020",
        "M.Arch | CEPT University | 2017 - 2019",
        "LLM | NLSIU | 2019 - 2020",
    ]

    for line in master_cases:
        raw = f"Candidate Name\nemail@example.com\n\nEducation\n{line}\n"
        parsed = extractor.extract_resume(raw)
        assert parsed["education_level"] == "master", (
            f"Line '{line}' extracted '{parsed['education_level']}', expected 'master'"
        )

    # Re-verify false positive resistance
    false_positives = [
        "Systems Engineering Lead",
        "Microsystems Architect",
        "Boston University, Boston, MA | 2016 - 2020",
        "Portland, ME",
        "Austin, MA 02101 | email | phone",
        "Please contact me for references",
        "Scrum Master | Acme Corp | 2019 - 2022",
        "Master of Ceremonies for the annual event",
        "March 2020 - April 2022",
    ]
    for line in false_positives:
        raw = f"Candidate Name\nemail@example.com\n\nExperience\n{line}\n"
        parsed = extractor.extract_resume(raw)
        assert parsed["education_level"] == "none", (
            f"Line '{line}' falsely yielded degree '{parsed['education_level']}'"
        )


def test_score_status_consistency_round_once():
    """Verify that an unrounded 59.96 score rounds ONCE to 60.0 and is labelled MEDIUM."""
    from app.services.explainer import ScoreExplainer
    from app.services.scorer import MatchResult

    explainer = ScoreExplainer()

    # Create result with final_score = 60.0 (rounded from 59.96)
    mock_result = MatchResult(
        candidate_name="Generic Candidate",
        filename="generic_candidate.pdf",
        final_score=60.0,
        skill_score=50.0,
        semantic_score=50.0,
        experience_score=100.0,
        education_score=100.0,
        project_score=50.0,
        relevant_years=5.0,
        total_years=5.0,
        matched_skills=["Python"],
        partial_skills=[],
        missing_skills=[],
        matched_skills_details=[],
        evidence={
            "experience": {
                "candidate_years": 5.0,
                "required_years": 3.0,
                "relevant_years": 5.0,
                "total_years": 5.0,
            },
            "skills": {},
            "semantic": {},
            "education": {},
            "projects": {},
        },
        possible_keyword_stuffing=False,
    )

    explanation = explainer.explain(mock_result)
    assert mock_result.final_score == 60.0
    assert explanation["status_label"] == "MEDIUM", (
        f"Score 60.0 must be labelled MEDIUM, got {explanation['status_label']}"
    )


def test_experience_relevance_and_cap():
    """Verify experience relevance computation and cap rule on content writer vs data scientist."""
    from app.services.explainer import ScoreExplainer
    from app.services.scorer import get_resume_scorer

    scorer = get_resume_scorer()
    explainer = ScoreExplainer()

    jd_data = {
        "title": "Data Scientist (Machine Learning)",
        "required_skills": ["Python", "SQL", "Machine Learning", "scikit-learn", "Pandas", "NumPy", "Statistics", "Git"],
        "preferred_skills": ["PyTorch", "TensorFlow", "NLP", "Spark", "MLflow", "AWS", "Docker"],
        "min_experience_years": 2.0,
        "education_level": "master",
        "responsibilities": [
            "Build and evaluate machine learning models such as classification and regression models.",
            "Analyse large datasets using Python, Pandas and NumPy.",
            "Write complex SQL queries on PostgreSQL or BigQuery.",
        ],
        "raw_text": "Data Scientist Machine Learning required.",
    }

    # Content writer resume (Tanvi Shah): 2.7y experience in writing blogs
    content_writer = {
        "name": "Tanvi Shah",
        "filename": "05_tanvi_shah_keyword_stuffer.txt",
        "skills": ["Python", "SQL", "Machine Learning", "scikit-learn", "Pandas", "NumPy", "Statistics", "Git"],
        "total_experience_years": 2.7,
        "education_level": "bachelor",
        "job_titles": ["Content Writer"],
        "roles": [
            {
                "header": "Content Writer | BrightWords Media | Apr 2023 - Dec 2025",
                "start_date": None,
                "end_date": None,
                "lines": [
                    "Content Writer | BrightWords Media | Apr 2023 - Dec 2025",
                    "Wrote blog posts and social media copy for client brands.",
                    "Managed the editorial calendar and coordinated with designers.",
                    "Edited articles written by freelance contributors.",
                ],
            }
        ],
        "sections": {
            "skills": "Python, SQL, Machine Learning, scikit-learn, Pandas, NumPy, Statistics, Git",
            "experience": "Content Writer | BrightWords Media | Apr 2023 - Dec 2025\nWrote blog posts and social media copy.",
            "education": "B.A. in English Literature",
        },
        "raw_text": "Content writer resume text.",
    }

    res = scorer.score_candidate(content_writer, jd_data)
    explanation = explainer.explain(res)

    # Relevant years must be near 0 for content writer
    assert res.relevant_years < 0.5, f"Expected relevant years < 0.5, got {res.relevant_years}"
    assert res.final_score > 0
    assert explanation["status_label"] == "LOW"
    assert "0.0 relevant" in explanation["experience_explanation"] or "0.0" in explanation["experience_explanation"]

    # Verify experience cap rule lowers candidate from MEDIUM to LOW when relevant_years < 50%
    from app.config import check_experience_cap
    status, cap_applied = check_experience_cap(68.0, candidate_years=res.relevant_years, required_years=2.0)
    assert status == "LOW"
    assert cap_applied is True


def test_benchmark_invariants_and_hybrid_relevance_all_sets():
    """Verify all three invariant rules across Python, Java, and Data Scientist benchmark sets:
    1. relevant_years <= total_years for every candidate.
    2. total_years equals real profile total_experience_years unchanged by relevance.
    3. ExperienceScore == min(relevant_years / required_years, 1) * 100 and final_score equals weighted sum of sub-scores (+-0.1).
    4. experience_cap_applied is True ONLY when status was actually lowered by cap.
    5. Failed / scanned PDF is marked failed and excluded.
    """
    import pytest

    from app.services.explainer import ScoreExplainer
    from app.services.parser import EmptyDocumentError, parse_document
    from app.services.scorer import get_resume_scorer

    jd_extractor = get_jd_extractor()
    resume_extractor = get_resume_extractor()
    scorer = get_resume_scorer()
    explainer = ScoreExplainer()

    # 1. Failed file check
    empty_pdf = SAMPLE_RESUMES_DIR / "13_scanned_empty_edge_case.pdf"
    with pytest.raises(EmptyDocumentError):
        parse_document(empty_pdf, empty_pdf.name)

    empty_profile = resume_extractor.extract_resume("", filename="empty.pdf")
    assert empty_profile["status"] == "failed"

    # 2. Benchmark sets verification
    base_dir = SAMPLE_JD_PATH.parent.parent
    java_jd = base_dir / "sample_data" / "java_test" / "sample_JD_java_spring_boot.txt"
    if not java_jd.exists():
        java_jd = base_dir / "sample_JD_java_spring_boot.txt"
    ds_jd = base_dir / "sample_data" / "data_scientist_test" / "sample_JD_data_scientist.txt"
    if not ds_jd.exists():
        ds_jd = base_dir / "sample_JD_data_scientist.txt"
    benchmarks = [
        ("Python", SAMPLE_JD_PATH, SAMPLE_RESUMES_DIR),
        ("Java", java_jd, base_dir / "sample_data" / "java_test"),
        ("DS", ds_jd, base_dir / "sample_data" / "data_scientist_test"),
    ]

    for set_name, jd_path, resumes_dir in benchmarks:
        jd_data = jd_extractor.extract_jd(jd_path.read_text(encoding="utf-8"))
        req_years = jd_data.get("min_experience_years", 0.0)

        resume_files = sorted([
            f for f in resumes_dir.glob("*.*")
            if f.suffix.lower() in [".pdf", ".docx", ".txt"] and "sample_jd" not in f.name.lower() and not f.name.startswith("~")
        ])

        for rf in resume_files:
            try:
                raw_text = parse_document(rf, filename=rf.name)
            except EmptyDocumentError:
                continue

            prof = resume_extractor.extract_resume(raw_text, filename=rf.name)
            if prof.get("status") == "failed":
                continue

            res = scorer.score_candidate(prof, jd_data)
            exp = explainer.explain(res)

            # Invariant 1: relevant_years <= total_years
            assert res.relevant_years <= res.total_years + 1e-4, (
                f"{set_name} candidate {prof['name']} has relevant_years ({res.relevant_years}) > total_years ({res.total_years})"
            )

            # Invariant 2: total_years must equal parsed profile total_experience_years
            assert res.total_years == pytest.approx(prof["total_experience_years"], abs=0.01), (
                f"{set_name} candidate {prof['name']} total_years changed from profile: {res.total_years} vs {prof['total_experience_years']}"
            )

            # Invariant 3: ExperienceScore == min(relevant_years / required_years, 1) * 100
            if req_years > 0:
                expected_exp_score = min(res.relevant_years / req_years, 1.0) * 100.0
                assert res.experience_score == pytest.approx(expected_exp_score, abs=0.05)

            # Invariant 3b: final_score equals weighted sum of printed sub-scores (tolerance 0.1)
            weighted_sum = (
                0.40 * res.skill_score
                + 0.25 * res.semantic_score
                + 0.20 * res.experience_score
                + 0.10 * res.education_score
                + 0.05 * res.project_score
            )
            assert res.final_score == pytest.approx(weighted_sum, abs=0.1)

            # Check specific candidates
            if "alex_chen" in rf.name.lower():
                assert res.total_years == 7.9
                assert res.relevant_years == 7.9
            elif "david_kim" in rf.name.lower():
                assert res.total_years == 7.6
                assert res.relevant_years == 7.6
            elif "marcus_vance" in rf.name.lower():
                assert res.total_years == 16.9
            elif "maya_lin" in rf.name.lower():
                assert res.total_years == 6.1
            elif "priya_sharma" in rf.name.lower():
                assert res.total_years == 3.2
            elif "chloe" in rf.name.lower():
                assert res.total_years == 2.1
            elif "carlos" in rf.name.lower():
                assert res.total_years == 4.1
            elif "kevin_brooks" in rf.name.lower():
                assert res.total_years == 2.9
            elif "liam_oconnor" in rf.name.lower():
                assert res.total_years == 6.9
                assert res.relevant_years == 0.0
            elif "ananya_iyer" in rf.name.lower():
                assert res.total_years == 0.5
                assert res.relevant_years <= 0.5
            elif "vikram_nair" in rf.name.lower():
                assert res.total_years == 2.6
                assert res.relevant_years == 0.0
            elif "tanvi_shah" in rf.name.lower():
                assert res.total_years == 2.7
                assert res.relevant_years == 0.0
                assert exp["experience_cap_applied"] is False
            elif "divya_menon" in rf.name.lower():
                assert res.total_years == 0.5
                assert exp["experience_cap_applied"] is False
            elif "samira" in rf.name.lower():
                assert exp["experience_cap_applied"] is True



