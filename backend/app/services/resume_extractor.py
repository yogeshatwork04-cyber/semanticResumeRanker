"""Resume extraction service.

Extracts candidate name, contact info, canonical skills, section segmentation,
job titles, education level, and calculates merged total years of experience
without double-counting overlapping roles.
"""

import re
from datetime import date
from typing import Any

from app.services.skills import get_skills_service

# Month abbreviation mapping
MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def merge_date_intervals(intervals: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """Merge overlapping or consecutive date intervals.

    Guarantees no double-counting of simultaneous positions.
    """
    if not intervals:
        return []

    # Sort intervals by start date, then end date
    sorted_intervals = sorted(intervals, key=lambda x: (x[0], x[1]))
    merged: list[tuple[date, date]] = [sorted_intervals[0]]

    for current_start, current_end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]

        # If current interval overlaps or directly abuts the last interval (within 35 days)
        if current_start <= last_end or (current_start - last_end).days <= 35:
            new_end = max(last_end, current_end)
            merged[-1] = (last_start, new_end)
        else:
            merged.append((current_start, current_end))

    return merged


def calculate_total_years(merged_intervals: list[tuple[date, date]]) -> float:
    """Calculate total accumulated years from merged non-overlapping intervals."""
    if not merged_intervals:
        return 0.0

    total_days = sum((end - start).days for start, end in merged_intervals)
    # 365.25 accounts for leap years
    years = round(total_days / 365.25, 1)
    return max(0.0, years)


def calculate_relevant_and_total_years(roles: list[dict[str, Any]]) -> tuple[float, float]:
    """Calculate both relevant years (weighted by role relevance) and total years.

    Merges overlapping periods: during overlapping dates, the candidate receives
    the maximum relevance among active roles, avoiding double-counting while crediting
    the most relevant experience.
    """
    if not roles:
        return 0.0, 0.0

    def parse_d(val: Any) -> date | None:
        if not val:
            return None
        if isinstance(val, date):
            return val
        try:
            return date.fromisoformat(str(val))
        except (ValueError, TypeError):
            return None

    # Parse and clean dates
    parsed_roles = []
    for r in roles:
        sd = parse_d(r.get("start_date"))
        ed = parse_d(r.get("end_date"))
        if sd and ed and sd <= ed:
            parsed_roles.append({
                "start_date": sd,
                "end_date": ed,
                "relevance": r.get("relevance", 0.0),
            })

    if not parsed_roles:
        return 0.0, 0.0

    # Collect unique boundary dates
    dates = sorted(list({r["start_date"] for r in parsed_roles} | {r["end_date"] for r in parsed_roles}))
    if len(dates) < 2:
        return 0.0, 0.0

    relevant_days = 0.0
    total_days = 0.0

    for i in range(len(dates) - 1):
        seg_start = dates[i]
        seg_end = dates[i + 1]
        seg_days = (seg_end - seg_start).days
        if seg_days <= 0:
            continue

        # Find active roles in this segment
        active = [
            r for r in parsed_roles
            if r["start_date"] <= seg_start and r["end_date"] >= seg_end
        ]
        if active:
            max_rel = max(r.get("relevance", 0.0) for r in active)
            relevant_days += seg_days * max_rel
            total_days += seg_days

    tot_years = round(total_days / 365.25, 1)
    rel_years = min(round(relevant_days / 365.25, 1), tot_years)
    return rel_years, tot_years


class ResumeExtractor:
    """Deterministic extractor for candidate resumes."""

    def __init__(self):
        self.skills_service = get_skills_service()

        self._email_regex = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
        )
        self._phone_regex = re.compile(
            r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        )

        # Date range patterns
        months_pattern = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        present_pattern = r"(?:Present|Current|Now|Ongoing|Till\s+Date)"

        self._date_range_regexes = [
            # "Jan 2020 - Mar 2023", "May 2021 to Present"
            re.compile(
                rf"\b({months_pattern})\s+(\d{{4}})\s*(?:-|–|—|to)\s*({months_pattern}\s+\d{{4}}|{present_pattern})\b",
                re.IGNORECASE,
            ),
            # "01/2020 - 03/2023", "05/2021 to Present"
            re.compile(
                rf"\b(0?[1-9]|1[0-2])[\/\-](\d{{4}})\s*(?:-|–|—|to)\s*((?:0?[1-9]|1[0-2])[\/\-]\d{{4}}|{present_pattern})\b",
                re.IGNORECASE,
            ),
            # "2019 - 2022", "2020 - Present"
            re.compile(
                rf"\b(\d{{4}})\s*(?:-|–|—|to)\s*(\d{{4}}|{present_pattern})\b",
                re.IGNORECASE,
            ),
        ]

        self._education_patterns = [
            (
                re.compile(
                    r"\b(ph\.?d\.?|doctorate|doctoral|doctor\s+of\s+[a-z\s]+)\b",
                    re.IGNORECASE,
                ),
                "phd",
            ),
            (
                re.compile(
                    r"(?i:\b("
                    r"master(?:'?s)?\s+(?:degree|in\s+[a-z\s&]+|of\s+(?:science|arts|engineering|technology|business|computer|philosophy|studies|applied|management|education|administration|data|analytics|finance)\b)"
                    r"|m\.?\s*sc\.?|msc"
                    r"|m\.?\s*tech\.?|mtech"
                    r"|m\.?\s*b\.?\s*a\.?|mba"
                    r"|m\.?\s*c\.?\s*a\.?|mca"
                    r"|m\.s\.|m\.e\.|m\.a\."
                    r"|pgdm|pgdbm|m\.?\s*pharm\.?|m\.\s*arch\.?|m\.\s*ed\.?"
                    r"|pg\s*diploma|post\s*graduate"
                    r"))"
                    r"|\bMS\b(?:\s+(?:in|of|degree|–|-|:)\s+[A-Za-z\s&]+|\s*\([A-Za-z\s&]+\)|\s*,\s*(?!USA\b|[A-Z]{2}\b)[A-Za-z\s&]+|\b(?!\s*,\s*[A-Z]{2}\b))"
                    r"|\b(?:ME|MA)\b(?:\s+(?:in|of|degree|–|-|:)\s+[A-Za-z\s&]+|\s*\([A-Za-z\s&]+\))"
                    r"|\b(?:LLM|MFA|MEd|MArch|MPharm|PGDM|PGDBM)\b(?:\s+(?:in|of|degree|–|-|:)\s+[A-Za-z\s&]+|\s*\([A-Za-z\s&]+\)|\s*,\s*(?!USA\b|[A-Z]{2}\b)[A-Za-z\s&]+|\b(?!\s*,\s*[A-Z]{2}\b))"
                ),
                "master",
            ),
            (
                re.compile(
                    r"(?i:\b("
                    r"bachelor(?:'?s)?\s+(?:degree|in\s+[a-z\s&]+|of\s+(?:science|arts|engineering|technology|business|computer|commerce|information|applied|studies|architecture|fine\s+arts|law)\b)"
                    r"|b\.?\s*sc\.?|bsc"
                    r"|b\.?\s*tech\.?|btech"
                    r"|b\.?\s*c\.?\s*a\.?|bca"
                    r"|b\.?\s*com\.?|bcom"
                    r"|b\.e\.|b\.a\.|b\.s\."
                    r"|bba|bbm|bms|bfa|llb|ll\.?b\.?|b\.?\s*pharm\.?|b\.\s*arch\.?|b\.\s*ed\.?"
                    r"|undergraduate"
                    r"))"
                    r"|\b(?:BE|BA|BS)\b(?:\s+(?:in|of|degree|–|-|:)\s+[A-Za-z\s&]+|\s*\([A-Za-z\s&]+\)|\s*,\s*(?!USA\b|[A-Z]{2}\b)[A-Za-z\s&]+|\b(?!\s*,\s*[A-Z]{2}\b))"
                    r"|\b(?:BBA|BBM|BMS|BFA|LLB|BEd|BPharm|BArch)\b(?:\s+(?:in|of|degree|–|-|:)\s+[A-Za-z\s&]+|\s*\([A-Za-z\s&]+\)|\s*,\s*(?!USA\b|[A-Z]{2}\b)[A-Za-z\s&]+|\b(?!\s*,\s*[A-Z]{2}\b))"
                ),
                "bachelor",
            ),
            (re.compile(r"\b(diploma|associate(?:'?s)?)\b", re.IGNORECASE), "diploma"),
        ]

        # For unsegmented resumes: full phrases and dotted degrees only (no bare abbreviations)
        self._general_text_education_patterns = [
            (
                re.compile(
                    r"\b(ph\.?d\.?|doctorate|doctoral|doctor\s+of\s+[a-z\s]+)\b",
                    re.IGNORECASE,
                ),
                "phd",
            ),
            (
                re.compile(
                    r"(?i:\b("
                    r"master(?:'?s)?\s+(?:degree|in\s+[a-z\s&]+|of\s+(?:science|arts|engineering|technology|business|computer|philosophy|studies|applied|management|education|administration|data|analytics|finance)\b)"
                    r"|m\.?\s*sc\.?|msc"
                    r"|m\.?\s*tech\.?|mtech"
                    r"|m\.s\.|m\.e\.|m\.a\."
                    r"|m\.?\s*pharm\.?|m\.\s*arch\.?|m\.\s*ed\.?|pgdm|pgdbm|mfa|llm"
                    r"|pg\s*diploma|post\s*graduate"
                    r"))"
                    r"|\b(?:PGDM|PGDBM|LLM|MFA|MArch|MPharm)\b",
                ),
                "master",
            ),
            (
                re.compile(
                    r"(?i:\b("
                    r"bachelor(?:'?s)?\s+(?:degree|in\s+[a-z\s&]+|of\s+(?:science|arts|engineering|technology|business|computer|commerce|information|applied|studies|architecture|fine\s+arts|law)\b)"
                    r"|b\.?\s*sc\.?|bsc"
                    r"|b\.?\s*tech\.?|btech"
                    r"|b\.?\s*c\.?\s*a\.?|bca"
                    r"|b\.?\s*com\.?|bcom"
                    r"|b\.e\.|b\.a\.|b\.s\."
                    r"|bba|bbm|bms|bfa|llb|b\.?\s*pharm\.?|b\.\s*arch\.?|b\.\s*ed\.?"
                    r"|undergraduate"
                    r"))"
                    r"|\b(?:BBA|BBM|BMS|BFA|LLB|BPharm|BArch)\b",
                ),
                "bachelor",
            ),
            (re.compile(r"\b(diploma|associate(?:'?s)?)\b", re.IGNORECASE), "diploma"),
        ]

        self._institution_regex = re.compile(
            r"\b(university|college|institute|school|academy|polytechnic)\b",
            re.IGNORECASE,
        )
        self._edu_year_regex = re.compile(
            r"\b(?:19|20)\d{2}\s*(?:-|–|—|to)\s*(?:(?:19|20)\d{2}|present|current)\b|\b(?:19|20)\d{2}\b",
            re.IGNORECASE,
        )

    def extract_name(self, text: str) -> str:
        """Extract candidate name from header lines using heuristic filtering."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines[:6]:
            # Skip obvious header labels, emails, phones, or URLs
            line_lower = line.lower()
            if any(
                bad in line_lower
                for bad in [
                    "resume", "curriculum", "vitae", "email", "phone", "contact",
                    "page", "github.com", "linkedin.com", "http", "@",
                ]
            ):
                continue

            # A valid name line is typically 2-4 words, letters/periods only
            words = line.split()
            if 2 <= len(words) <= 4:
                clean_name = re.sub(r"[^A-Za-z\s\.\-]", "", line).strip()
                if len(clean_name) >= 3 and clean_name.replace(" ", "").isalpha():
                    return clean_name.title()

        return "Candidate"

    def extract_contact_info(self, text: str) -> tuple[str | None, str | None]:
        """Extract email address and phone number from text."""
        email_match = self._email_regex.search(text)
        email = email_match.group(0).lower() if email_match else None

        phone_match = self._phone_regex.search(text)
        phone = phone_match.group(0).strip() if phone_match else None

        return email, phone

    def segment_sections(self, text: str) -> dict[str, str]:
        """Split resume into functional sections: summary, experience, projects, education, skills."""
        section_headers = {
            "experience": [
                "experience",
                "work experience",
                "employment history",
                "professional experience",
                "work history",
                "internships",
                "internship experience",
                "practical experience",
                "industry experience",
            ],
            "projects": [
                "projects",
                "technical projects",
                "personal projects",
                "key projects",
                "academic projects",
            ],
            "education": [
                "education",
                "academic background",
                "academics",
                "academic qualifications",
                "educational qualifications",
                "education & training",
                "education and training",
                "qualifications",
            ],
            "skills": [
                "skills",
                "technical skills",
                "core competencies",
                "technologies",
                "skills & expertise",
            ],
            "summary": [
                "summary",
                "professional summary",
                "profile",
                "about me",
                "objective",
            ],
        }

        sections: dict[str, list[str]] = {
            "summary": [],
            "experience": [],
            "projects": [],
            "education": [],
            "skills": [],
            "other": [],
        }

        current_section = "summary"
        lines = text.splitlines()

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            line_lower = line_clean.lower().strip(":# -*•")

            # Check if line is a section header
            matched_header = None
            if len(line_lower) < 35:
                for sec_name, headers in section_headers.items():
                    if line_lower in headers or any(
                        line_lower.startswith(f"{h}:") or line_lower == h for h in headers
                    ):
                        matched_header = sec_name
                        break

            if matched_header:
                current_section = matched_header
            else:
                sections[current_section].append(line_clean)

        return {
            sec: "\n".join(lines).strip()
            for sec, lines in sections.items()
            if any(line_str.strip() for line_str in lines)
        }

    def _parse_single_date(self, token: str, is_end: bool = False) -> date:
        """Parse date token into a datetime date object."""
        token_clean = token.strip()
        if re.search(r"present|current|now|ongoing|till", token_clean, re.IGNORECASE):
            return date.today()

        # Month and year ("Jan 2020", "01/2020")
        parts = re.split(r"[\s/\-]+", token_clean)
        if len(parts) >= 2:
            first, second = parts[0].lower(), parts[1]
            month = MONTH_MAP.get(first[:3])
            if not month and first.isdigit():
                month = int(first)
            year = int(second) if second.isdigit() else 2020
            month = month if month and 1 <= month <= 12 else (12 if is_end else 1)
            day = 28 if is_end else 1
            return date(year, month, day)

        # Only year ("2020")
        if token_clean.isdigit() and len(token_clean) == 4:
            year = int(token_clean)
            return date(year, 12, 31) if is_end else date(year, 1, 1)

        return date.today() if is_end else date(2020, 1, 1)

    def extract_experience_intervals(self, text: str) -> list[tuple[date, date]]:
        """Extract and parse all chronological date intervals from experience text."""
        intervals: list[tuple[date, date]] = []

        # Target experience section specifically, with fallback to full text
        for line in text.splitlines():
            # Check for "Jan 2020 - Mar 2023"
            m1 = self._date_range_regexes[0].search(line)
            if m1:
                start_str = f"{m1.group(1)} {m1.group(2)}"
                end_str = m1.group(3)
                start_date = self._parse_single_date(start_str, is_end=False)
                end_date = self._parse_single_date(end_str, is_end=True)
                if start_date <= end_date:
                    intervals.append((start_date, end_date))
                continue

            # Check for "01/2020 - 03/2023"
            m2 = self._date_range_regexes[1].search(line)
            if m2:
                start_str = f"{m2.group(1)}/{m2.group(2)}"
                end_str = m2.group(3)
                start_date = self._parse_single_date(start_str, is_end=False)
                end_date = self._parse_single_date(end_str, is_end=True)
                if start_date <= end_date:
                    intervals.append((start_date, end_date))
                continue

            # Check for "2019 - 2022"
            m3 = self._date_range_regexes[2].search(line)
            if m3:
                start_str = m3.group(1)
                end_str = m3.group(2)
                # Ignore graduation year ranges if in education context
                if "gpa" not in line.lower() and "degree" not in line.lower():
                    start_date = self._parse_single_date(start_str, is_end=False)
                    end_date = self._parse_single_date(end_str, is_end=True)
                    if start_date <= end_date:
                        intervals.append((start_date, end_date))

        return intervals

    def parse_roles_from_experience(
        self,
        text: str,
        experience_section: str = "",
    ) -> list[dict[str, Any]]:
        """Parse discrete roles with titles, dates, and bullets from experience or text."""
        target_text = experience_section if experience_section.strip() else text
        lines = target_text.splitlines()
        roles: list[dict[str, Any]] = []
        current_role: dict[str, Any] | None = None

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            intervals = self.extract_experience_intervals(line_clean)
            if intervals:
                if current_role:
                    roles.append(current_role)
                start_d, end_d = intervals[0]
                current_role = {
                    "header": line_clean,
                    "start_date": start_d.isoformat() if hasattr(start_d, "isoformat") else str(start_d),
                    "end_date": end_d.isoformat() if hasattr(end_d, "isoformat") else str(end_d),
                    "lines": [line_clean],
                }
            else:
                if current_role:
                    current_role["lines"].append(line_clean)

        if current_role:
            roles.append(current_role)

        return roles

    def extract_years_of_experience(self, text: str, experience_section: str) -> float:
        """Extract total years of experience, merging any overlapping intervals."""
        # Search experience section first; if empty, search full text
        intervals = self.extract_experience_intervals(experience_section)
        if not intervals:
            intervals = self.extract_experience_intervals(text)

        merged = merge_date_intervals(intervals)
        return calculate_total_years(merged)

    def extract_education_level(self, text: str, education_section: str = "") -> str:
        """Determine highest education level found.

        Degree abbreviations (MS, ME, MA, BE, BA, MBA, MCA) match as standalone
        tokens inside an education section, or in raw text on lines containing an
        institution keyword (university/college/institute/school) or year range.
        """
        sec = education_section.strip()
        if sec:
            for pattern, level in self._education_patterns:
                if pattern.search(sec):
                    return level
            return "none"

        # No header at all: allow abbreviations on lines with university/college/institute/school
        # keyword or a year range, plus full-phrase degree patterns anywhere.
        found_levels: list[str] = []
        for line in text.splitlines():
            line_clean = line.strip()
            if not line_clean:
                continue
            has_institution = bool(self._institution_regex.search(line_clean))
            has_year = bool(self._edu_year_regex.search(line_clean))
            if has_institution or has_year:
                for pattern, level in self._education_patterns:
                    if pattern.search(line_clean):
                        found_levels.append(level)
                        break

        for pattern, level in self._general_text_education_patterns:
            if pattern.search(text):
                found_levels.append(level)
                break

        if not found_levels:
            return "none"

        rank_order = {"phd": 4, "master": 3, "bachelor": 2, "diploma": 1, "none": 0}
        return max(found_levels, key=lambda lvl: rank_order.get(lvl, 0))

    def extract_job_titles(self, experience_text: str) -> list[str]:
        """Extract relevant job titles from experience section."""
        title_patterns = [
            re.compile(
                r"\b((?:Senior|Lead|Principal|Staff|Junior|Associate)?\s*(?:Software|Backend|Frontend|Full\s*Stack|Data|DevOps|Systems|Cloud|ML|AI)?\s*(?:Engineer|Developer|Architect|Consultant|Specialist|Scientist|Programmer))\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b((?:Engineering|Technical|Project|Product)\s+Manager)\b",
                re.IGNORECASE,
            ),
        ]

        titles: list[str] = []
        for line in experience_text.splitlines():
            for p in title_patterns:
                matches = p.findall(line)
                for match in matches:
                    title_clean = match.strip().title()
                    if title_clean and title_clean not in titles and len(title_clean) > 4:
                        titles.append(title_clean)
        return titles[:5]

    def extract_skills(self, text: str, skills_section: str = "") -> list[str]:
        """Extract canonical and open-vocabulary candidate skills.

        Supports comma-separated and bulleted lines under a SKILLS / TECHNOLOGIES
        heading, retaining open-vocabulary items not in taxonomy while using
        canonical names for recognized skills.
        """
        seen: set[str] = set()
        skills: list[str] = []

        if skills_section:
            # Join hard-wrapped lines that don't start with bullet and previous line didn't end with delimiter
            raw_lines = [line.strip() for line in skills_section.splitlines() if line.strip()]
            joined_lines: list[str] = []
            for line in raw_lines:
                is_bullet = bool(re.match(r"^(?:[-*•]+|\d+[\.\)])\s*", line))
                if joined_lines and not is_bullet and not joined_lines[-1].endswith((",", ";", ":", "|")):
                    joined_lines[-1] = f"{joined_lines[-1]} {line}"
                else:
                    joined_lines.append(line)

            for line in joined_lines:
                line_clean = re.sub(r"^(?:[-*•]+|\d+[\.\)])\s*", "", line).strip()
                if not line_clean:
                    continue
                # Split by comma, semicolon, pipe, or slash with spaces
                parts = re.split(r"[,;|]|\s+/\s+", line_clean)
                for p in parts:
                    token = p.strip().strip("-*• \t")
                    if not token or len(token) < 2 or len(token) > 45:
                        continue
                    token = re.sub(r"\s+", " ", token)
                    canonical = self.skills_service.get_canonical_name(token)
                    val = canonical if canonical else token
                    if val.lower() not in seen:
                        seen.add(val.lower())
                        skills.append(val)

        # Also extract any canonical taxonomy skills mentioned in experience/summary
        full_text_skills = self.skills_service.extract_skills(text)
        for s in full_text_skills:
            if s.lower() not in seen:
                seen.add(s.lower())
                skills.append(s)

        return skills

    def extract_resume(
        self,
        text: str,
        filename: str = "resume.pdf",
    ) -> dict[str, Any]:
        """Perform comprehensive deterministic extraction on resume text."""
        sections = self.segment_sections(text)
        name = self.extract_name(text)
        email, phone = self.extract_contact_info(text)
        skills = self.extract_skills(text, sections.get("skills", ""))
        roles = self.parse_roles_from_experience(text, sections.get("experience", ""))
        total_years = self.extract_years_of_experience(text, sections.get("experience", ""))
        education_level = self.extract_education_level(text, sections.get("education", ""))
        job_titles = self.extract_job_titles(sections.get("experience", ""))

        is_failed = False
        error_msg = None
        if not text or not text.strip():
            is_failed = True
            error_msg = "Document contains no extractable text."
        elif not skills and total_years == 0.0 and not roles and (name in ["Candidate", "Unknown", "Obj"] or not name):
            is_failed = True
            error_msg = "No detectable name, skills, or experience found in document."

        return {
            "filename": filename,
            "name": name,
            "email": email or "not_provided@example.com",
            "phone": phone or "N/A",
            "skills": skills,
            "roles": roles,
            "total_experience_years": total_years,
            "education_level": education_level,
            "job_titles": job_titles,
            "sections": sections,
            "raw_text": text,
            "status": "failed" if is_failed else "parsed",
            "error": error_msg,
        }


_resume_extractor_instance: ResumeExtractor | None = None


def get_resume_extractor() -> ResumeExtractor:
    """Return singleton instance of ResumeExtractor."""
    global _resume_extractor_instance
    if _resume_extractor_instance is None:
        _resume_extractor_instance = ResumeExtractor()
    return _resume_extractor_instance
