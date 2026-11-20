"""Job Description (JD) extraction service.

Extracts required skills, preferred skills, minimum years of experience,
education requirements, and key responsibilities deterministically using
cue-phrase heuristics, regular expressions, and the canonical skills taxonomy.
Supports open-vocabulary skills and strict section-based prioritization.
"""

import re
from typing import Any

from app.services.skills import get_skills_service


class JDExtractor:
    """Deterministic extractor for Job Description requirements."""

    def __init__(self):
        self.skills_service = get_skills_service()

        # Regex patterns for experience requirements
        self._exp_patterns = [
            # "minimum 5 yrs", "at least 3 years", "min 2 yrs"
            re.compile(
                r"(?:minimum|at\s+least|min\.?)\s*(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs?)",
                re.IGNORECASE,
            ),
            # "3+ years", "4+ yrs"
            re.compile(r"(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?)", re.IGNORECASE),
            # "2-4 years", "3 to 5 yrs" -> captures lower bound
            re.compile(
                r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*\d+(?:\.\d+)?\s*(?:years?|yrs?)",
                re.IGNORECASE,
            ),
            # "3 years of experience", "4 yrs experience"
            re.compile(
                r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?)(?:\s+of)?\s+(?:relevant\s+)?experience",
                re.IGNORECASE,
            ),
        ]

        # Education degree mapping
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
                    r"\b("
                    r"master(?:'?s)?(?:\s+of\s+[a-z\s&]+)?"
                    r"|m\.?sc\.?|msc"
                    r"|m\.?tech\.?|mtech"
                    r"|m\.?b\.?a\.?|mba"
                    r"|m\.?c\.?a\.?|mca"
                    r"|m\.?e\.?|m\.?s\.?|m\.?a\.?"
                    r"|mfa|llm|ll\.?m\.?|pgdm|pgdbm|m\.?\s*pharm\.?|m\.\s*arch\.?|m\.\s*ed\.?"
                    r"|(?:ms|me|ma)\s+(?:in|of|degree)\b"
                    r"|pg\s*diploma|post\s*graduate"
                    r")\b"
                    r"|\b(?:LLM|MFA|MEd|MArch|MPharm|PGDM|PGDBM)\b",
                    re.IGNORECASE,
                ),
                "master",
            ),
            (
                re.compile(
                    r"\b("
                    r"bachelor(?:'?s)?(?:\s+of\s+[a-z\s&]+)?"
                    r"|b\.?sc\.?|bsc"
                    r"|b\.?tech\.?|btech"
                    r"|b\.?c\.?a\.?|bca"
                    r"|b\.?com\.?|bcom"
                    r"|b\.?e\.?|be"
                    r"|b\.?a\.?|ba"
                    r"|b\.?s\.?|bs"
                    r"|bba|bbm|bms|bfa|llb|ll\.?b\.?|b\.?\s*pharm\.?|b\.\s*arch\.?|b\.\s*ed\.?"
                    r"|undergraduate"
                    r")\b"
                    r"|\b(?:BBA|BBM|BMS|BFA|LLB|BEd|BPharm|BArch)\b",
                    re.IGNORECASE,
                ),
                "bachelor",
            ),
            (re.compile(r"\b(diploma|associate(?:'?s)?)\b", re.IGNORECASE), "diploma"),
        ]

        self._pref_degree_marker = re.compile(
            r"\b(plus|pluses|preferred|preference|desirable|advantage|nice\s+to\s+have|bonus|a\s+bonus|ideally|optional)\b",
            re.IGNORECASE,
        )

    def extract_min_experience(self, text: str) -> float:
        """Extract minimum years of experience stated in JD."""
        found_years: list[float] = []

        for pattern in self._exp_patterns:
            matches = pattern.findall(text)
            for m in matches:
                try:
                    val = float(m)
                    if 0.5 <= val <= 25.0:
                        found_years.append(val)
                except (ValueError, TypeError):
                    continue

        if found_years:
            return min(found_years)
        return 0.0

    def extract_education_level(self, text: str) -> str:
        """Identify required education level.

        Rule: ignore degrees mentioned with preference markers (plus, preferred,
        desirable, advantage, nice to have, a bonus, ideally); among remaining
        degrees in the qualification line, take the LOWEST level (since
        'Bachelor's or Master's' means either is acceptable).
        """
        rank_order = {"phd": 4, "master": 3, "bachelor": 2, "diploma": 1, "none": 0}

        # Split into clauses by newlines, semicolons, bullets, parentheses, and sentence periods
        clauses = [c.strip() for c in re.split(r"[\n;\r•*|()]|\.(?!\w)", text) if c.strip()]
        req_degrees: list[str] = []

        for clause in clauses:
            # Sub-split on comma if followed by a phrase containing preference or requirement words
            subclauses = [
                s.strip()
                for s in re.split(
                    r",(?=\s*(?:[A-Za-z\s]+(?:plus|preferred|desirable|advantage|nice|bonus|ideally|optional|required|must)))",
                    clause,
                    flags=re.IGNORECASE,
                )
                if s.strip()
            ]
            for sub in subclauses:
                is_pref = bool(self._pref_degree_marker.search(sub))
                found_levels: list[str] = []
                for pattern, level in self._education_patterns:
                    if pattern.search(sub):
                        found_levels.append(level)
                if not is_pref and found_levels:
                    req_degrees.extend(found_levels)

        if req_degrees:
            # Take the LOWEST level among remaining required degrees
            return min(req_degrees, key=lambda lvl: rank_order.get(lvl, 2))

        return "bachelor"  # Industry standard default if unstated

    def _clean_title(self, raw_title: str) -> str:
        """Strip leading 'Job Title:', 'Title:', 'Position:', or 'Role:' prefixes."""
        if not raw_title:
            return "Backend Engineer"
        cleaned = re.sub(
            r"^(?:job\s*title|position|title|role)\s*[:\-]\s*",
            "",
            raw_title.strip(),
            flags=re.IGNORECASE,
        ).strip()
        return cleaned or raw_title.strip()

    def _segment_sections(self, text: str) -> dict[str, list[str]]:
        """Segment JD into semantic sections."""
        section_headers = {
            "required_skills": [
                "required skills",
                "core skills",
                "mandatory skills",
                "must have",
                "core requirements",
                "required qualifications",
                "what you need",
            ],
            "preferred_skills": [
                "preferred skills",
                "nice to have",
                "good to have",
                "preferred qualifications",
                "plus",
                "pluses",
                "bonus",
                "desirable",
                "advantage",
                "advantages",
                "preferred qualifications (nice to have)",
            ],
            "responsibilities": [
                "responsibilities",
                "key responsibilities",
                "duties",
                "key duties",
                "job duties",
                "what you'll do",
                "what you will do",
            ],
            "about": [
                "about the role",
                "about us",
                "the role",
                "role overview",
                "who we are",
                "job summary",
                "company overview",
            ],
            "qualifications": [
                "qualifications",
                "requirements",
                "minimum qualifications",
                "education",
                "experience required",
            ],
        }

        sections: dict[str, list[str]] = {
            "about": [],
            "responsibilities": [],
            "required_skills": [],
            "preferred_skills": [],
            "qualifications": [],
            "other": [],
        }

        current_sec = "other"
        lines = text.splitlines()

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            line_lower = line_clean.lower().strip(":# -*•")

            # Check for section header match
            matched_header = None
            if len(line_lower) < 55:
                # Priority: preferred headers first, then required, responsibilities, about, qualifications
                for sec_name in ["preferred_skills", "required_skills", "responsibilities", "about", "qualifications"]:
                    headers = section_headers[sec_name]
                    if line_lower in headers or any(line_lower == h or line_lower.startswith(f"{h}:") for h in headers):
                        matched_header = sec_name
                        break

            if matched_header:
                current_sec = matched_header
            else:
                sections[current_sec].append(line_clean)

        return sections

    def _parse_skill_tokens_from_lines(self, lines: list[str]) -> list[str]:
        """Extract canonical and open-vocabulary skills from explicit bullet/list lines."""
        skills: list[str] = []
        seen: set[str] = set()

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            # Strip leading bullet/numbering
            clean_item = re.sub(r"^(?:[-*•]+|\d+[\.\)])\s*", "", line_clean).strip()
            if not clean_item:
                continue

            # Split by comma, semicolon, or slash with spaces (e.g. "Hibernate / JPA")
            # Do NOT split CI/CD, PL/SQL, TCP/IP
            tokens = re.split(r"[,;]|\s+/\s+", clean_item)
            for token in tokens:
                t = token.strip().strip("-*• \t")
                if not t or len(t) < 2 or len(t) > 45:
                    continue

                # Check canonical lookup
                canonical = self.skills_service.get_canonical_name(t)
                if canonical:
                    if canonical.lower() not in seen:
                        seen.add(canonical.lower())
                        skills.append(canonical)
                else:
                    # Check if PhraseMatcher extracts canonical skills
                    ext = self.skills_service.extract_skills(t)
                    if ext:
                        for s in ext:
                            if s.lower() not in seen:
                                seen.add(s.lower())
                                skills.append(s)
                    else:
                        # Open-vocabulary skill
                        if t.lower() not in seen:
                            seen.add(t.lower())
                            skills.append(t)

        return skills

    def extract_skills_by_priority(self, text: str) -> tuple[list[str], list[str]]:
        """Categorize skills into required and preferred based on explicit sections and cues.

        Source of Truth:
        1. If explicit 'Required Skills' and 'Preferred Skills' sections exist, use them.
        2. Skills found only in responsibilities may be added as preferred, never required.
        3. Do not turn 'such as X and Y' examples into separate required skills.
        4. If a skill appears in both lists, keep in required only.
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Check for explicit 'Required Skills' and 'Preferred Skills' section headings
        has_explicit_req_skills = any(re.match(r"^required\s+skills\b", line, re.IGNORECASE) for line in lines)
        has_explicit_pref_skills = any(re.match(r"^preferred\s+skills\b", line, re.IGNORECASE) for line in lines)

        if has_explicit_req_skills and has_explicit_pref_skills:
            req_lines: list[str] = []
            pref_lines: list[str] = []
            resp_lines: list[str] = []
            cur_sec = None

            for line in lines:
                line_lower = line.lower().strip(":# -*•")
                if line_lower.startswith("required skills"):
                    cur_sec = "req"
                elif line_lower.startswith("preferred skills"):
                    cur_sec = "pref"
                elif any(line_lower.startswith(h) for h in ["responsibilities", "key responsibilities", "duties", "what you'll do", "what you will do"]):
                    cur_sec = "resp"
                elif any(line_lower.startswith(h) for h in ["qualifications", "about the role", "about us", "who we are"]):
                    cur_sec = "other"
                else:
                    if cur_sec == "req":
                        req_lines.append(line)
                    elif cur_sec == "pref":
                        pref_lines.append(line)
                    elif cur_sec == "resp":
                        resp_lines.append(line)

            req = self._parse_skill_tokens_from_lines(req_lines)
            pref_raw = self._parse_skill_tokens_from_lines(pref_lines)
            req_set = {s.lower() for s in req}
            pref = [s for s in pref_raw if s.lower() not in req_set]
            pref_set = {s.lower() for s in pref}

            # Mask out 'such as ...' or 'e.g. ...' examples in responsibilities
            masked_resp = re.sub(
                r"\b(?:such\s+as|e\.g\.|for\s+example)\b[^.\n]*",
                "",
                "\n".join(resp_lines),
                flags=re.IGNORECASE,
            )
            resp_skills = self.skills_service.extract_skills(masked_resp)
            for s in resp_skills:
                if s.lower() not in req_set and s.lower() not in pref_set:
                    pref.append(s)
                    pref_set.add(s.lower())

            return req, pref
        else:
            # Fallback to general cue-based segmentation (for Python JD, etc.)
            preferred_cues = ["nice to have", "good to have", "preferred", "plus", "pluses", "bonus", "desirable"]
            required_cues = ["must have", "required", "essential", "mandatory", "qualifications", "requirements", "core skills"]
            current_mode = "required"
            req_text: list[str] = []
            pref_text: list[str] = []

            for line in lines:
                ll = line.lower()
                if any(c in ll for c in preferred_cues):
                    current_mode = "preferred"
                elif any(c in ll for c in required_cues):
                    current_mode = "required"

                if current_mode == "preferred":
                    pref_text.append(line)
                else:
                    req_text.append(line)

            req_raw = self.skills_service.extract_skills("\n".join(req_text))
            pref_raw = self.skills_service.extract_skills("\n".join(pref_text))
            req_lower = {s.lower() for s in req_raw}
            pref = [s for s in pref_raw if s.lower() not in req_lower]

            if not req_raw and not pref:
                req_raw = self.skills_service.extract_skills(text)

            return req_raw, pref

    def extract_responsibilities(self, text: str) -> list[str]:
        """Extract key responsibilities or duty statements.

        Joins hard-wrapped lines within responsibilities before splitting,
        takes sentences ONLY from the Responsibilities/Duties section (or lines
        starting with an action verb), and strictly excludes 'About the role'
        or introductory company text.
        """
        sections = self._segment_sections(text)
        resp_lines = sections.get("responsibilities", [])

        responsibilities: list[str] = []

        if resp_lines:
            # Join hard-wrapped lines: a line without bullet marker that follows a non-punctuated line
            joined: list[str] = []
            for line in resp_lines:
                line_str = line.strip()
                if not line_str:
                    continue

                is_bullet = line_str.startswith(("-", "*", "•")) or re.match(r"^\d+[\.\)]\s*", line_str)
                if joined and not is_bullet and not joined[-1].endswith((".", "!", "?", ":")):
                    # Hard-wrapped continuation of previous line
                    joined[-1] = f"{joined[-1]} {line_str}"
                else:
                    joined.append(line_str)

            for line_str in joined:
                clean = re.sub(r"^[-*•\d.]\s*", "", line_str).strip()
                if len(clean) >= 15:
                    responsibilities.append(clean)

        # Fallback if no explicit responsibilities section found:
        # Search lines starting with an action verb, skipping "about" sections and headers
        if not responsibilities:
            action_verb_pattern = re.compile(
                r"^\s*(?:[-*•\d.]\s*)?(?:design|build|develop|maintain|write|collaborate|troubleshoot|create|implement|manage|optimize|lead|architect|deploy|test|ensure|drive|scale|orchestrate|author)\b",
                re.IGNORECASE,
            )
            for line in text.splitlines():
                line_str = line.strip()
                line_lower = line_str.lower()
                # Exclude lines in "about the role", titles, etc.
                if any(bad in line_lower for bad in ["job title", "about the role", "about us", "who we are"]):
                    continue
                if action_verb_pattern.search(line_str) and len(line_str) >= 20:
                    clean = re.sub(r"^[-*•\d.]\s*", "", line_str).strip()
                    responsibilities.append(clean)
                    if len(responsibilities) >= 8:
                        break

        return responsibilities[:10]

    def extract_jd(self, text: str, title: str | None = None) -> dict[str, Any]:
        """Extract structured JD attributes from text.

        Returns:
            Dict containing title, required_skills, preferred_skills,
            min_experience_years, education_level, responsibilities, and raw_text.
        """
        req_skills, pref_skills = self.extract_skills_by_priority(text)
        min_exp = self.extract_min_experience(text)
        edu_level = self.extract_education_level(text)
        responsibilities = self.extract_responsibilities(text)

        # Detect job title if not provided
        inferred_title = title
        if not inferred_title:
            first_lines = [line.strip() for line in text.splitlines() if line.strip()]
            for line in first_lines[:4]:
                clean_candidate = self._clean_title(line)
                if re.search(
                    r"\b(engineer|developer|architect|lead|manager|analyst|scientist|consultant)\b",
                    clean_candidate,
                    re.IGNORECASE,
                ):
                    inferred_title = clean_candidate
                    break
            if not inferred_title and first_lines:
                inferred_title = self._clean_title(first_lines[0][:60])
            elif not inferred_title:
                inferred_title = "Backend Engineer"
        else:
            inferred_title = self._clean_title(inferred_title)

        return {
            "title": inferred_title,
            "required_skills": req_skills,
            "preferred_skills": pref_skills,
            "min_experience_years": min_exp,
            "education_level": edu_level,
            "responsibilities": responsibilities,
            "raw_text": text,
        }


_jd_extractor_instance: JDExtractor | None = None


def get_jd_extractor() -> JDExtractor:
    """Return singleton instance of JDExtractor."""
    global _jd_extractor_instance
    if _jd_extractor_instance is None:
        _jd_extractor_instance = JDExtractor()
    return _jd_extractor_instance
