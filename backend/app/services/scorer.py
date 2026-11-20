"""Deterministic resume-to-JD matching and scoring engine.

Implements the 5-component scoring formula:
FinalScore = 0.40*SkillScore + 0.25*SemanticScore + 0.20*ExperienceScore
           + 0.10*EducationScore + 0.05*ProjectScore

Features:
- Two-Tier Partial Skill Credit:
  1. Curated RELATED_SKILLS map in taxonomy with explicit credit values (e.g. FastAPI <-> Flask/Django 0.6).
  2. Embedding fallback ONLY when cosine >= 0.75 (SKILL_EMBED_THRESHOLD).
- Keyword-Stuffer Defense: Skills found only in lists get 0.5 credit vs 1.0 for demonstrated skills.
- Calibrated Semantic Similarity: Rescaled from actual distribution [0.28, 0.78].
- Project Score: Requires technical taxonomy skills in sentences and caps fallback experience deliverables at 70%.
"""

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.config import get_settings
from app.services.embeddings import get_embedding_service
from app.services.resume_extractor import calculate_relevant_and_total_years
from app.services.skills import get_skills_service

settings = get_settings()


@dataclass
class MatchResult:
    """Encapsulates the complete scoring output and granular evidence for a candidate."""

    candidate_name: str
    filename: str
    final_score: float
    skill_score: float
    semantic_score: float
    experience_score: float
    education_score: float
    project_score: float
    relevant_years: float = 0.0
    total_years: float = 0.0
    matched_skills: list[str] = field(default_factory=list)
    partial_skills: list[dict[str, Any]] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    matched_skills_details: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    possible_keyword_stuffing: bool = False


class ResumeScorer:
    """Deterministic scoring engine implementing the 5-factor weighted algorithm."""

    def __init__(self):
        self.settings = get_settings()
        self.embedding_service = get_embedding_service()
        self.skills_service = get_skills_service()

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into distinct non-empty sentences or meaningful clause chunks."""
        if not text:
            return []
        raw_chunks = re.split(r"(?<=[.!?\n])\s+", text)
        clean_chunks = [
            c.strip().strip("-*• ")
            for c in raw_chunks
            if len(c.strip()) >= 15
        ]
        return clean_chunks

    @staticmethod
    def _skill_stem(skill: str) -> str:
        """Return a lightweight stem for a skill name for inflected-form matching.

        Strips common English suffixes so e.g. "Statistics" matches "statistical".
        Only used as a secondary check after exact/alias matching fails.
        """
        s = skill.lower().strip()
        # Remove trailing common suffixes in order (longest first)
        for suffix in ("tical", "tics", "tical", "ing", "ics", "al", "ed", "s"):
            if s.endswith(suffix) and len(s) - len(suffix) >= 3:
                s = s[: len(s) - len(suffix)]
                break
        return s

    def _is_skill_demonstrated(
        self,
        skill_name: str,
        experience_text: str,
        projects_text: str,
    ) -> bool:
        """Check whether a skill is actively mentioned in work experience or project text.

        Checks (in order):
        1. Exact word-boundary match of the skill name.
        2. Word-boundary match of any taxonomy alias.
        3. Light-stem match: derived stem appears as a substring (e.g. "statistic"
           found in "statistical methods"), guarded to >=4-char stems only.
        """
        combined = f"{experience_text}\n{projects_text}".lower()
        if not combined.strip():
            return False

        # 1. Direct canonical skill check
        pattern = rf"\b{re.escape(skill_name.lower())}\b"
        if re.search(pattern, combined):
            return True

        # 2. Check all canonical aliases from taxonomy
        canonical = self.skills_service.get_canonical_name(skill_name) or skill_name
        aliases = self.skills_service._canonical_skills.get(canonical, {}).get("aliases", [])
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias.lower())}\b", combined):
                return True

        # 3. Light stemming: strip common inflection suffixes and check substring
        stem = self._skill_stem(skill_name)
        if len(stem) >= 4 and stem in combined:
            return True

        return False

    def compute_skill_score(
        self,
        jd_required: list[str],
        jd_preferred: list[str],
        candidate_skills: list[str],
        resume_sections: dict[str, str],
    ) -> tuple[float, list[str], list[dict[str, Any]], list[str], list[dict[str, Any]], dict[str, Any]]:
        """Evaluate candidate skills with curated map and strict >=0.75 embedding fallback.

        Rules:
        1. Exact / canonical alias match: credit = 1.0 * multiplier (demonstrated 1.0, listed 0.5).
        2. Curated taxonomy map: if candidate has related skill (e.g. Django for FastAPI = 0.60 credit).
        3. Embedding fallback: ONLY when cosine >= 0.75.
        4. Otherwise: missing.
        """
        all_jd_skills: list[tuple[str, float]] = []
        for s in jd_required:
            all_jd_skills.append((s, self.settings.required_skill_weight))
        for s in jd_preferred:
            all_jd_skills.append((s, self.settings.preferred_skill_weight))

        if not all_jd_skills:
            return 100.0, [], [], [], [], {"reason": "No skills required in JD"}

        candidate_skills_lower = {s.lower(): s for s in candidate_skills}
        exp_text = resume_sections.get("experience", "")
        proj_text = resume_sections.get("projects", "")

        matched: list[str] = []
        matched_details: list[dict[str, Any]] = []
        partial: list[dict[str, Any]] = []
        missing: list[str] = []

        total_weight = sum(w for _, w in all_jd_skills)
        earned_weight = 0.0

        demonstrated_count = 0
        listed_only_count = 0

        for skill, weight in all_jd_skills:
            skill_lower = skill.lower()
            canonical = self.skills_service.get_canonical_name(skill) or skill
            canonical_lower = canonical.lower()

            # 1. Exact match or recognized alias
            is_exact = (
                skill_lower in candidate_skills_lower
                or canonical_lower in candidate_skills_lower
            )

            if is_exact:
                matched_cand_name = (
                    candidate_skills_lower.get(skill_lower)
                    or candidate_skills_lower.get(canonical_lower)
                    or skill
                )
                demonstrated = self._is_skill_demonstrated(matched_cand_name, exp_text, proj_text)
                source = "demonstrated" if demonstrated else "listed"
                multiplier = 1.0 if demonstrated else self.settings.listed_only_credit

                if demonstrated:
                    demonstrated_count += 1
                else:
                    listed_only_count += 1

                credit = 1.0 * multiplier
                earned_weight += credit * weight

                matched.append(skill)
                matched_details.append(
                    {
                        "skill": skill,
                        "matched_via": matched_cand_name,
                        "rule": "exact" if skill.lower() == matched_cand_name.lower() else "alias",
                        "evidence_source": source,
                        "credit": round(credit, 2),
                        "weight": weight,
                    }
                )
                continue

            # 2. Curated RELATED_SKILLS map check
            best_curated_skill = None
            best_curated_val = 0.0

            for cand_s in candidate_skills:
                val = self.skills_service.get_curated_related_credit(skill, cand_s)
                if val is not None and val > best_curated_val:
                    best_curated_val = val
                    best_curated_skill = cand_s

            if best_curated_skill is not None and best_curated_val > 0.0:
                demonstrated = self._is_skill_demonstrated(best_curated_skill, exp_text, proj_text)
                source = "demonstrated" if demonstrated else "listed"
                multiplier = 1.0 if demonstrated else self.settings.listed_only_credit

                if demonstrated:
                    demonstrated_count += 1
                else:
                    listed_only_count += 1

                credit = best_curated_val * multiplier
                earned_weight += credit * weight

                partial.append(
                    {
                        "jd_skill": skill,
                        "matched_via": best_curated_skill,
                        "similarity": best_curated_val,
                        "rule": "curated",
                        "evidence_source": source,
                        "credit": round(credit, 3),
                        "weight": weight,
                    }
                )
                continue

            # 3. Embedding fallback ONLY when cosine >= skill_embed_threshold (0.75)
            skill_emb = self.embedding_service.get_embedding(skill)
            best_emb_sim = 0.0
            best_emb_skill = None

            for cand_s in candidate_skills:
                c_emb = self.embedding_service.get_embedding(cand_s)
                sim = self.embedding_service.cosine_similarity(skill_emb, c_emb)
                if sim > best_emb_sim:
                    best_emb_sim = sim
                    best_emb_skill = cand_s

            if best_emb_sim >= self.settings.skill_embed_threshold and best_emb_skill:
                demonstrated = self._is_skill_demonstrated(best_emb_skill, exp_text, proj_text)
                source = "demonstrated" if demonstrated else "listed"
                multiplier = 1.0 if demonstrated else self.settings.listed_only_credit

                if demonstrated:
                    demonstrated_count += 1
                else:
                    listed_only_count += 1

                credit = best_emb_sim * multiplier
                earned_weight += credit * weight

                partial.append(
                    {
                        "jd_skill": skill,
                        "matched_via": best_emb_skill,
                        "similarity": round(best_emb_sim, 3),
                        "rule": "embedding",
                        "evidence_source": source,
                        "credit": round(credit, 3),
                        "weight": weight,
                    }
                )
            else:
                missing.append(skill)

        skill_score = (earned_weight / total_weight) * 100.0
        skill_score = round(min(100.0, max(0.0, skill_score)), 2)

        total_matched = demonstrated_count + listed_only_count
        listed_share = (listed_only_count / total_matched) if total_matched > 0 else 0.0
        is_keyword_stuffing = (
            listed_only_count >= self.settings.stuffing_min_listed_only
            and listed_share >= self.settings.stuffing_min_listed_share
            and demonstrated_count < self.settings.stuffing_max_demonstrated
        )

        evidence = {
            "total_jd_skills": len(all_jd_skills),
            "matched_count": len(matched),
            "partial_count": len(partial),
            "missing_count": len(missing),
            "demonstrated_count": demonstrated_count,
            "listed_only_count": listed_only_count,
            "total_weight": total_weight,
            "earned_weight": round(earned_weight, 2),
            "listed_only_penalty_applied": listed_only_count > 0,
            "possible_keyword_stuffing": is_keyword_stuffing,
        }

        return skill_score, matched, partial, missing, matched_details, evidence

    def compute_semantic_score(
        self,
        jd_text: str,
        resume_sections: dict[str, str],
        full_resume_text: str,
    ) -> tuple[float, dict[str, Any]]:
        """Compute calibrated semantic overlap between JD requirements and resume experience/projects.

        Excludes 'About the role' or introductory company text to prevent dilution.
        """
        # Filter out 'About the Role' / 'About us' paragraphs
        cleaned_jd = re.sub(
            r"(?:about\s+(?:the\s+role|us)|who\s+we\s+are):?\s*.*?(?=(?:key\s+)?responsibilities|duties|requirements|qualifications|required\s+skills)",
            "",
            jd_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        jd_sentences = self._split_into_sentences(cleaned_jd if cleaned_jd.strip() else jd_text)
        # Filter out any lingering intro/title lines
        jd_sentences = [
            s for s in jd_sentences
            if not re.search(r"^(?:job\s*title|about\s+(?:the\s+role|us)|we\s+are\s+looking\s+for)\b", s, re.IGNORECASE)
        ]

        if not jd_sentences:
            return 50.0, {"reason": "Empty JD text for semantic comparison"}

        exp_text = f"{resume_sections.get('experience', '')}\n{resume_sections.get('projects', '')}"
        resume_chunks = self._split_into_sentences(exp_text)
        if not resume_chunks:
            resume_chunks = self._split_into_sentences(full_resume_text)

        if not resume_chunks:
            return 0.0, {"reason": "No extractable experience or project text in resume"}

        chunk_embeddings = self.embedding_service.get_embeddings_batch(resume_chunks)

        max_cosines: list[float] = []
        top_alignments: list[dict[str, Any]] = []

        for sentence in jd_sentences:
            sent_emb = self.embedding_service.get_embedding(sentence)
            best_chunk_sim = 0.0
            best_chunk_text = ""

            for chunk_text, chunk_emb in zip(resume_chunks, chunk_embeddings, strict=True):
                sim = self.embedding_service.cosine_similarity(sent_emb, chunk_emb)
                if sim > best_chunk_sim:
                    best_chunk_sim = sim
                    best_chunk_text = chunk_text

            max_cosines.append(best_chunk_sim)
            top_alignments.append(
                {
                    "jd_sentence": sentence[:80],
                    "best_chunk": best_chunk_text[:80],
                    "cosine": round(best_chunk_sim, 3),
                }
            )

        top_k = min(self.settings.semantic_top_k, len(max_cosines))
        sorted_cosines = sorted(max_cosines, reverse=True)
        top_k_cosines = sorted_cosines[:top_k]
        raw_avg = float(np.mean(top_k_cosines)) if top_k_cosines else 0.0

        min_c = self.settings.semantic_min_cosine
        max_c = self.settings.semantic_max_cosine
        scaled = ((raw_avg - min_c) / (max_c - min_c)) * 100.0
        final_semantic = round(min(100.0, max(0.0, scaled)), 2)

        top_alignments.sort(key=lambda x: x["cosine"], reverse=True)

        evidence = {
            "raw_avg_cosine": round(raw_avg, 3),
            "calibrated_range": [min_c, max_c],
            "top_k_used": top_k,
            "top_alignments": top_alignments[:3],
        }

        return final_semantic, evidence

    def _clean_bullet_line(self, line: str) -> str:
        """Strip CID artifacts, list bullets, numbers, and excess whitespace from a line."""
        c = re.sub(r"\(cid:\d+\)", "", line)
        c = re.sub(r"^(?:[-*•]+|\d+[\.\)])\s*", "", c).strip()
        return c

    def compute_experience_score(
        self,
        candidate_years: float,
        required_years: float,
        candidate_titles: list[str],
        jd_title: str,
        candidate_roles: list[dict[str, Any]] | None = None,
        jd_responsibilities: list[str] | None = None,
        jd_required_skills: list[str] | None = None,
        jd_preferred_skills: list[str] | None = None,
        jd_text: str = "",
        full_experience_text: str = "",
    ) -> tuple[float, dict[str, Any]]:
        """Calculate role-weighted relevant experience years using hybrid relevance and explainable matching.

        Hybrid role relevance:
        role_relevance = max(skill_overlap, semantic)
        - skill_overlap: share of JD required+preferred skills (weighted 2:1) found in role title/bullets,
          using exact/alias/curated/embedding logic (credit 1.0 if in bullets, 0.5 if only in header).
        - semantic: top-k mean cosine between the role's bullets and JD responsibility sentences,
          calibrated with config thresholds (< min_cosine -> 0.0, > max_cosine -> 1.0, linear in between).
        - Non-technical roles with no technical skills and low semantic score receive 0.0 relevance.
        - Overlapping role intervals are merged without double-counting (taking maximum active relevance).
        - ExperienceScore = min(relevant_years / required_years, 1.0) * 100.0.
        """
        jd_req = jd_required_skills or []
        jd_pref = jd_preferred_skills or []

        jd_resps = [r for r in (jd_responsibilities or []) if len(r.strip()) > 5]
        if not jd_resps and jd_text.strip():
            jd_resps = [s for s in self._split_into_sentences(jd_text) if len(s.strip()) > 15][:8]

        role_breakdown: list[dict[str, Any]] = []
        all_jd_skills = list(dict.fromkeys(jd_req + jd_pref))

        if candidate_roles and len(candidate_roles) > 0:
            for role in candidate_roles:
                header = role.get("header", "")
                raw_lines = role.get("lines", [])
                bullets = [
                    self._clean_bullet_line(line)
                    for line in raw_lines
                    if line != header and len(self._clean_bullet_line(line)) > 5
                ]
                if not bullets:
                    bullets = [self._clean_bullet_line(header)]

                role_full_text = f"{header}\n" + "\n".join(bullets)

                # 1. Demonstrated JD skills in role (exact, alias, or stem; NO curated-related skills)
                demonstrated_skills_in_role: list[str] = []
                seen_canonicals: set[str] = set()
                for s in all_jd_skills:
                    canonical = self.skills_service.get_canonical_name(s) or s
                    if canonical.lower() in seen_canonicals:
                        continue
                    if self._is_skill_demonstrated(s, role_full_text, ""):
                        seen_canonicals.add(canonical.lower())
                        demonstrated_skills_in_role.append(s)

                num_skills = len(demonstrated_skills_in_role)

                # 2. Semantic alignment: top-k mean cosine between bullets and JD responsibilities
                if jd_resps and bullets:
                    bullet_embs = self.embedding_service.get_embeddings_batch(bullets)
                    max_cosines: list[float] = []
                    for r_sent in jd_resps:
                        r_emb = self.embedding_service.get_embedding(r_sent)
                        sims = [
                            float(self.embedding_service.cosine_similarity(r_emb, b_emb))
                            for b_emb in bullet_embs
                        ]
                        if sims:
                            max_cosines.append(max(sims))

                    if max_cosines:
                        sorted_cos = sorted(max_cosines, reverse=True)
                        top_k = min(len(bullets), 3) if len(bullets) <= 3 else 3
                        top_k = max(1, top_k)
                        raw_sem = float(np.mean(sorted_cos[:top_k]))
                    else:
                        raw_sem = 0.0
                else:
                    raw_sem = 0.0

                # 3. Explainable 3-tier relevance:
                # - 1.0 if >= 2 JD skills demonstrated
                # - 0.5 if exactly 1 JD skill OR (0 skills and raw_sem >= semantic_threshold)
                # - 0.0 otherwise
                min_skills_full = self.settings.role_min_skills_full_credit
                sem_thresh = self.settings.role_semantic_threshold

                if num_skills >= min_skills_full:
                    tier = 1.0
                    evidence_desc = f">= {min_skills_full} JD skills: {', '.join(demonstrated_skills_in_role)}"
                elif num_skills == 1:
                    tier = 0.5
                    evidence_desc = f"1 JD skill: {demonstrated_skills_in_role[0]}"
                elif raw_sem >= sem_thresh:
                    tier = 0.5
                    evidence_desc = f"semantic match (cosine {raw_sem:.3f} >= {sem_thresh:.2f})"
                else:
                    tier = 0.0
                    evidence_desc = f"0 JD skills, cosine {raw_sem:.3f} < {sem_thresh:.2f}"

                role["relevance"] = tier
                role["tier"] = tier
                role["similarity"] = round(raw_sem, 3)
                role["matched_skills"] = demonstrated_skills_in_role
                role["evidence"] = evidence_desc

                role_breakdown.append(
                    {
                        "header": header,
                        "relevance": tier,
                        "tier": tier,
                        "similarity": round(raw_sem, 3),
                        "matched_skills": demonstrated_skills_in_role,
                        "evidence": evidence_desc,
                    }
                )

            rel_years, _ = calculate_relevant_and_total_years(candidate_roles)
            total_years = candidate_years
            relevant_years = min(rel_years, total_years)
        elif full_experience_text.strip():
            # Fallback if no discrete roles parsed
            demonstrated_skills_in_role = []
            seen_canonicals = set()
            for s in all_jd_skills:
                canonical = self.skills_service.get_canonical_name(s) or s
                if canonical.lower() in seen_canonicals:
                    continue
                if self._is_skill_demonstrated(s, full_experience_text, ""):
                    seen_canonicals.add(canonical.lower())
                    demonstrated_skills_in_role.append(s)

            num_skills = len(demonstrated_skills_in_role)

            jd_req_parts = [jd_title]
            if jd_resps:
                jd_req_parts.extend(jd_resps[:4])
            if jd_req:
                jd_req_parts.extend(jd_req)
            jd_req_text = " ".join(jd_req_parts)
            jd_req_emb = self.embedding_service.get_embedding(jd_req_text)
            exp_emb = self.embedding_service.get_embedding(full_experience_text)
            raw_sem = float(self.embedding_service.cosine_similarity(jd_req_emb, exp_emb))

            min_skills_full = self.settings.role_min_skills_full_credit
            sem_thresh = self.settings.role_semantic_threshold

            if num_skills >= min_skills_full:
                tier = 1.0
                evidence_desc = f">= {min_skills_full} JD skills: {', '.join(demonstrated_skills_in_role)}"
            elif num_skills == 1:
                tier = 0.5
                evidence_desc = f"1 JD skill: {demonstrated_skills_in_role[0]}"
            elif raw_sem >= sem_thresh:
                tier = 0.5
                evidence_desc = f"semantic match (cosine {raw_sem:.3f} >= {sem_thresh:.2f})"
            else:
                tier = 0.0
                evidence_desc = f"0 JD skills, cosine {raw_sem:.3f} < {sem_thresh:.2f}"

            total_years = candidate_years
            relevant_years = min(round(candidate_years * tier, 1), total_years)
            role_breakdown.append(
                {
                    "header": "Overall Experience",
                    "relevance": tier,
                    "tier": tier,
                    "similarity": round(raw_sem, 3),
                    "matched_skills": demonstrated_skills_in_role,
                    "evidence": evidence_desc,
                }
            )
        else:
            total_years = candidate_years
            relevant_years = candidate_years

        if required_years <= 0.0:
            exp_score = 100.0
            ratio = 1.0
        else:
            ratio = min(relevant_years / required_years, 1.0)
            exp_score = round(ratio * 100.0, 2)

        title_keywords = set(re.findall(r"\b\w{3,}\b", jd_title.lower()))
        cand_words = set(
            w
            for title in candidate_titles
            for w in re.findall(r"\b\w{3,}\b", title.lower())
        )
        overlap = title_keywords.intersection(cand_words)
        title_relevant = len(overlap) > 0 or not candidate_titles

        evidence = {
            "candidate_years": relevant_years,  # for check_experience_cap
            "relevant_years": relevant_years,
            "total_years": total_years,
            "required_years": required_years,
            "ratio": round(ratio, 2),
            "title_relevant": title_relevant,
            "candidate_titles": candidate_titles,
            "role_breakdown": role_breakdown,
        }

        return exp_score, evidence

    def compute_education_score(
        self,
        candidate_education: str,
        required_education: str,
    ) -> tuple[float, dict[str, Any]]:
        """Calculate education score based on hierarchical degree ranks."""
        ranks = self.settings.education_ranks
        cand_level = candidate_education.lower().strip()
        req_level = required_education.lower().strip()

        cand_rank = ranks.get(cand_level, 2)
        req_rank = ranks.get(req_level, 2)

        if cand_rank >= req_rank:
            score = 100.0
        elif cand_rank == req_rank - 1:
            score = 50.0
        else:
            score = 0.0

        evidence = {
            "candidate_education": candidate_education,
            "required_education": required_education,
            "candidate_rank": cand_rank,
            "required_rank": req_rank,
        }

        return score, evidence

    def compute_project_score(
        self,
        resume_sections: dict[str, str],
        jd_text: str,
    ) -> tuple[float, dict[str, Any]]:
        """Evaluate technical project deliverables and compute a continuous relevance score.

        Enforces meaningful technical content (must contain technical skills) and
        caps fallback experience-extracted project deliverables at fallback_project_cap (70%).
        """
        projects_text = resume_sections.get("projects", "").strip()
        has_dedicated_section = bool(projects_text and len(projects_text) > 30)

        project_sentences: list[str] = []

        if has_dedicated_section:
            for s in self._split_into_sentences(projects_text):
                # Check for technical taxonomy skills in sentence
                if self.skills_service.extract_skills(s) or len(s.split()) >= 6:
                    project_sentences.append(s)

        # Fallback to deliverable sentences in experience
        if not project_sentences:
            exp_text = resume_sections.get("experience", "").strip()
            action_verbs = re.compile(
                r"\b(architected|built|developed|engineered|implemented|designed|created|deployed|optimized|integrated|spearheaded|authored|containerized)\b",
                re.IGNORECASE,
            )
            for line in exp_text.splitlines():
                line_clean = line.strip().strip("-*• ")
                # Must contain an action verb AND at least one technical skill
                if len(line_clean) >= 25 and action_verbs.search(line_clean):
                    if len(self.skills_service.extract_skills(line_clean)) >= 1:
                        project_sentences.append(line_clean)

        if not project_sentences:
            return 10.0, {
                "status": "no_projects_or_deliverables_found",
                "has_dedicated_projects": False,
                "project_sentence_count": 0,
                "raw_cosine": 0.0,
            }

        proj_embeddings = self.embedding_service.get_embeddings_batch(project_sentences)
        jd_sentences = self._split_into_sentences(jd_text)

        sims: list[float] = []
        for p_emb in proj_embeddings:
            best_sim = 0.0
            for j_sent in jd_sentences[:6]:
                j_emb = self.embedding_service.get_embedding(j_sent)
                sim = self.embedding_service.cosine_similarity(p_emb, j_emb)
                if sim > best_sim:
                    best_sim = sim
            sims.append(best_sim)

        raw_avg_cosine = float(np.mean(sims)) if sims else 0.25

        # Rescale continuously from [project_min_cosine, project_max_cosine] to [0, 100]
        p_min = self.settings.project_min_cosine
        p_max = self.settings.project_max_cosine
        scaled = ((raw_avg_cosine - p_min) / (p_max - p_min)) * 100.0

        # Dedicated projects can earn up to 100. Fallback experience sentences are capped at fallback_project_cap (70%).
        if not has_dedicated_section:
            # Volume multiplier: candidates with only 1 brief sentence get discounted
            vol_mult = min(1.0, len(project_sentences) / 2.0)
            score = min(scaled * vol_mult, self.settings.fallback_project_cap)
        else:
            score = scaled

        score = round(min(100.0, max(0.0, score)), 2)

        evidence = {
            "status": "dedicated_section" if has_dedicated_section else "extracted_from_experience",
            "has_dedicated_projects": has_dedicated_section,
            "project_sentence_count": len(project_sentences),
            "raw_cosine": round(raw_avg_cosine, 3),
            "sample_deliverables": [s[:70] for s in project_sentences[:2]],
            "score_capped_at": self.settings.fallback_project_cap if not has_dedicated_section else 100.0,
        }

        return score, evidence

    def score_candidate(
        self,
        resume_data: dict[str, Any],
        jd_data: dict[str, Any],
    ) -> MatchResult:
        """Perform comprehensive deterministic multi-factor match between resume and JD."""
        # 1. Skill Score with Curated Map & >=0.75 Fallback
        skill_score, matched_skills, partial_skills, missing_skills, matched_details, skill_evidence = (
            self.compute_skill_score(
                jd_required=jd_data.get("required_skills", []),
                jd_preferred=jd_data.get("preferred_skills", []),
                candidate_skills=resume_data.get("skills", []),
                resume_sections=resume_data.get("sections", {}),
            )
        )

        # 2. Semantic Score with Calibrated Range
        semantic_score, semantic_evidence = self.compute_semantic_score(
            jd_text=jd_data.get("raw_text", ""),
            resume_sections=resume_data.get("sections", {}),
            full_resume_text=resume_data.get("raw_text", ""),
        )

        # 3. Experience Score with Role-Based Relevance
        exp_score, exp_evidence = self.compute_experience_score(
            candidate_years=resume_data.get("total_experience_years", 0.0),
            required_years=jd_data.get("min_experience_years", 0.0),
            candidate_titles=resume_data.get("job_titles", []),
            jd_title=jd_data.get("title", ""),
            candidate_roles=resume_data.get("roles", []),
            jd_responsibilities=jd_data.get("responsibilities", []),
            jd_required_skills=jd_data.get("required_skills", []),
            jd_preferred_skills=jd_data.get("preferred_skills", []),
            jd_text=jd_data.get("raw_text", ""),
            full_experience_text=resume_data.get("sections", {}).get("experience", ""),
        )

        # 4. Education Score
        edu_score, edu_evidence = self.compute_education_score(
            candidate_education=resume_data.get("education_level", "bachelor"),
            required_education=jd_data.get("education_level", "bachelor"),
        )

        # 5. Continuous Project Score with Fallback Cap
        proj_score, proj_evidence = self.compute_project_score(
            resume_sections=resume_data.get("sections", {}),
            jd_text=jd_data.get("raw_text", ""),
        )

        # Final Weighted Score Calculation (rounded ONCE to 1 decimal for consistency)
        final_score = (
            self.settings.weight_skills * skill_score
            + self.settings.weight_semantic * semantic_score
            + self.settings.weight_experience * exp_score
            + self.settings.weight_education * edu_score
            + self.settings.weight_project * proj_score
        )
        final_score = round(min(100.0, max(0.0, final_score)), 1)

        evidence = {
            "skills": skill_evidence,
            "semantic": semantic_evidence,
            "experience": exp_evidence,
            "education": edu_evidence,
            "projects": proj_evidence,
            "weights": {
                "skills": self.settings.weight_skills,
                "semantic": self.settings.weight_semantic,
                "experience": self.settings.weight_experience,
                "education": self.settings.weight_education,
                "projects": self.settings.weight_project,
            },
        }

        return MatchResult(
            candidate_name=resume_data.get("name", "Unknown Candidate"),
            filename=resume_data.get("filename", "resume"),
            final_score=final_score,
            skill_score=skill_score,
            semantic_score=semantic_score,
            experience_score=exp_score,
            education_score=edu_score,
            project_score=proj_score,
            relevant_years=exp_evidence.get("relevant_years", 0.0),
            total_years=exp_evidence.get("total_years", 0.0),
            matched_skills=matched_skills,
            partial_skills=partial_skills,
            missing_skills=missing_skills,
            matched_skills_details=matched_details,
            evidence=evidence,
            possible_keyword_stuffing=bool(skill_evidence.get("possible_keyword_stuffing", False)),
        )


_scorer_instance: ResumeScorer | None = None


def get_resume_scorer() -> ResumeScorer:
    """Return singleton instance of ResumeScorer."""
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = ResumeScorer()
    return _scorer_instance
