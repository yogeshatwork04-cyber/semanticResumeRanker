"""Deterministic explanation generator using evidence templates.

Translates numerical sub-scores and granular match evidence directly into
clear, human-readable explanations, skill-source breakdowns, and recruiter insights.
"""

from typing import Any

from app.config import check_experience_cap, get_settings, get_status_label
from app.services.scorer import MatchResult

settings = get_settings()


class ScoreExplainer:
    """Generates deterministic, template-based natural language explanations from scoring evidence."""

    def explain(self, result: MatchResult) -> dict[str, Any]:
        """Generate full human-readable score explanation and summary points."""
        exp_ev = result.evidence.get("experience", {})
        cand_years = exp_ev.get("candidate_years", 0.0)
        req_years = exp_ev.get("required_years", 0.0)
        status_label, exp_cap_applied = check_experience_cap(
            result.final_score, candidate_years=cand_years, required_years=req_years
        )

        skill_ev = result.evidence.get("skills", {})
        is_keyword_stuffing = bool(
            result.possible_keyword_stuffing
            or skill_ev.get("possible_keyword_stuffing", False)
        )

        skill_reasons = self._explain_skills(result)
        semantic_reasons = self._explain_semantic(result)
        experience_reasons = self._explain_experience(result, exp_cap_applied=exp_cap_applied)
        education_reasons = self._explain_education(result)
        project_reasons = self._explain_projects(result)

        headline = self._generate_headline(result, status_label)

        bullet_points = [
            skill_reasons,
            experience_reasons,
            semantic_reasons,
            education_reasons,
        ]
        if project_reasons:
            bullet_points.append(project_reasons)
        if is_keyword_stuffing:
            bullet_points.append(
                "Possible keyword stuffing: Over 70% of matched skills appear only in a skills list without documented experience, and fewer than 2 demonstrated skills were found."
            )

        recommendation = self._generate_recommendation(result, status_label)

        return {
            "headline": headline,
            "status_label": status_label,
            "experience_cap_applied": exp_cap_applied,
            "possible_keyword_stuffing": is_keyword_stuffing,
            "summary": " ".join([headline, skill_reasons, experience_reasons]),
            "bullet_points": bullet_points,
            "skills_explanation": skill_reasons,
            "semantic_explanation": semantic_reasons,
            "experience_explanation": experience_reasons,
            "education_explanation": education_reasons,
            "project_explanation": project_reasons,
            "recommendation": recommendation,
        }

    def _generate_headline(self, result: MatchResult, status_label: str | None = None) -> str:
        """Create a punchy headline summarizing candidate standing using the single status function."""
        score = result.final_score
        name = result.candidate_name
        label = status_label or get_status_label(score)

        if label == "HIGH":
            return f"Top Match ({score:.1f}%): {name} strongly aligns with core requirements and technical stack."
        elif label == "MEDIUM":
            return f"Medium Match ({score:.1f}%): {name} meets primary qualifications with minor skill or experience gaps."
        else:
            return f"Low Match ({score:.1f}%): {name} does not meet the core profile or technical requirements."

    def _explain_skills(self, result: MatchResult) -> str:
        """Explain skill matches, partial rules (curated map vs embedding), and missing skills."""
        matched = result.matched_skills
        partial = result.partial_skills
        missing = result.missing_skills
        evidence = result.evidence.get("skills", {})

        matched_details = result.matched_skills_details or []
        if matched_details:
            matched_dem = sum(
                1 for m in matched_details if m.get("evidence_source") == "demonstrated"
            )
            matched_list = sum(
                1 for m in matched_details if m.get("evidence_source") == "listed"
            )
        else:
            matched_dem = min(len(matched), evidence.get("demonstrated_count", len(matched)))
            matched_list = max(0, len(matched) - matched_dem)

        total_jd_skills = len(matched) + len(partial) + len(missing)

        parts = []
        if matched:
            parts.append(
                f"Matched {len(matched)} of {total_jd_skills} JD skills: "
                f"{matched_dem} demonstrated in work history, {matched_list} listed only."
            )
        else:
            parts.append(f"Matched 0 of {total_jd_skills} JD skills.")

        if evidence.get("listed_only_count", 0) > 4 and evidence.get("demonstrated_count", 0) <= 2:
            parts.append(
                f"Notice: Skill-stuffing defense applied ({evidence.get('listed_only_count', 0)} skills received reduced credit because they appear only in a skills list without documented experience)."
            )

        if partial:
            p_details = []
            for p in partial[:3]:
                rule_name = (
                    "curated taxonomy map"
                    if p.get("rule") in {"curated", "curated_taxonomy"}
                    else "embedding similarity"
                )
                pct = int(p.get("similarity", 0.0) * 100)
                source = p.get("evidence_source", "demonstrated")
                p_details.append(
                    f"{p['jd_skill']} (via {p['matched_via']}, {pct}% credit via {rule_name}, {source})"
                )
            parts.append(f"{len(partial)} partial ({'; '.join(p_details)}).")

        if missing:
            parts.append(f"{len(missing)} missing: {', '.join(missing[:4])}.")
        else:
            parts.append("0 missing (all required skills covered).")

        return " ".join(parts)

    def _explain_semantic(self, result: MatchResult) -> str:
        """Explain semantic overlap of work history and project descriptions."""
        sem_score = result.semantic_score
        evidence = result.evidence.get("semantic", {})
        raw_cosine = evidence.get("raw_avg_cosine", 0.0)

        if sem_score >= settings.threshold_high:
            return f"High semantic alignment ({sem_score:.1f}%, calibrated from raw cosine {raw_cosine:.2f}) with JD responsibilities."
        elif sem_score >= settings.threshold_medium:
            return f"Moderate semantic overlap ({sem_score:.1f}%, calibrated from raw cosine {raw_cosine:.2f}) in responsibilities and tasks."
        else:
            return f"Low contextual alignment ({sem_score:.1f}%, raw cosine {raw_cosine:.2f}); work history does not reflect core job duties."

    def _explain_experience(self, result: MatchResult, exp_cap_applied: bool = False) -> str:
        """Explain total years vs relevant years, requirements, and role relevance."""
        evidence = result.evidence.get("experience", {})
        rel_years = evidence.get("relevant_years", evidence.get("candidate_years", 0.0))
        tot_years = evidence.get("total_years", rel_years)
        req_years = evidence.get("required_years", 0.0)
        ratio = evidence.get("ratio", 1.0)
        title_relevant = evidence.get("title_relevant", True)

        cfg = get_settings()
        cap_note = (
            f" Note: Relevant experience ({rel_years:.1f}y) is below {int(cfg.hard_req_experience_ratio_cap * 100)}% of stated requirement ({req_years:.1f}y); status is capped at LOW."
            if exp_cap_applied
            else ""
        )

        relevance_str = (
            "Past job titles align well with the target role."
            if title_relevant
            else "Past job titles differ from the target job title."
        )

        if req_years <= 0.0:
            return f"Candidate brings {tot_years:.1f} years total, {rel_years:.1f} relevant professional experience."

        percentage = int(ratio * 100)

        role_breakdown = evidence.get("role_breakdown", [])
        role_notes: list[str] = []
        if role_breakdown:
            for r in role_breakdown:
                title = r.get("header", "Role").split("|")[0].strip()
                tier = r.get("tier", r.get("relevance", 0.0))
                ev = r.get("evidence", "")
                if not ev:
                    skills = r.get("matched_skills", [])
                    if len(skills) >= 2:
                        ev = f">= 2 JD skills: {', '.join(skills)}"
                    elif len(skills) == 1:
                        ev = f"1 JD skill: {skills[0]}"
                    elif r.get("similarity", 0.0) >= 0.55:
                        ev = f"semantic match ({r.get('similarity', 0.0):.2f} >= 0.55)"
                    else:
                        ev = f"0 JD skills, cosine {r.get('similarity', 0.0):.2f} < 0.55"
                role_notes.append(f"{title} (Tier {tier:.1f}: {ev})")

        role_summary = (" Role breakdown: " + "; ".join(role_notes) + ".") if role_notes else ""

        if rel_years >= req_years:
            return (
                f"Meets/exceeds experience requirement with {rel_years:.1f} years vs {req_years:.1f} required "
                f"({tot_years:.1f} years total, {rel_years:.1f} relevant) (100%). "
                f"{relevance_str}{cap_note}{role_summary}"
            )
        else:
            return (
                f"Has {rel_years:.1f} years vs {req_years:.1f} required "
                f"({tot_years:.1f} years total, {rel_years:.1f} relevant) ({percentage}%). "
                f"{relevance_str}{cap_note}{role_summary}"
            )

    def _explain_education(self, result: MatchResult) -> str:
        """Explain degree qualification comparison."""
        evidence = result.evidence.get("education", {})
        cand_edu = evidence.get("candidate_education", "bachelor").title()
        req_edu = evidence.get("required_education", "bachelor").title()
        edu_score = result.education_score

        if edu_score == 100.0:
            return f"Education: {cand_edu} degree meets/exceeds requirement of {req_edu}."
        elif edu_score == 50.0:
            return f"Education: {cand_edu} is one tier below the preferred {req_edu} degree."
        else:
            return f"Education: {cand_edu} does not satisfy minimum requirement of {req_edu}."

    def _explain_projects(self, result: MatchResult) -> str:
        """Explain technical project deliverables and continuous score."""
        evidence = result.evidence.get("projects", {})
        has_dedicated = evidence.get("has_dedicated_projects", False)
        score = result.project_score
        raw_cos = evidence.get("raw_cosine", 0.0)

        if has_dedicated:
            return f"Projects ({score:.1f}%): Dedicated project section showcases relevant technical deliverables (cosine {raw_cos:.2f})."
        elif evidence.get("project_sentence_count", 0) > 0:
            return f"Projects ({score:.1f}%): Deliverables extracted from work experience (cosine {raw_cos:.2f}, capped at 70%)."
        else:
            return f"Projects ({score:.1f}%): No verifiable technical project portfolio or deliverable statements found."

    def _generate_recommendation(self, result: MatchResult, status_label: str | None = None) -> str:
        """Generate high-level hiring recommendation for recruiter."""
        score = result.final_score
        missing = result.missing_skills
        evidence = result.evidence.get("skills", {})
        listed_only = evidence.get("listed_only_count", 0)
        demonstrated = evidence.get("demonstrated_count", 0)
        label = status_label or get_status_label(score)

        if label == "HIGH":
            return "Strong Candidate: Advance directly to technical screening."
        elif label == "MEDIUM":
            if listed_only > 5 and demonstrated <= 2:
                return "Caution: Possible keyword stuffer. Verify claimed skills with a live coding challenge."
            if missing:
                return f"Viable Candidate: Screen specifically on missing skills ({', '.join(missing[:3])})."
            return "Viable Candidate: Recommended for hiring manager review."
        else:
            return "Not Recommended: Does not meet fundamental qualifications."


_explainer_instance: ScoreExplainer | None = None


def get_score_explainer() -> ScoreExplainer:
    """Return singleton instance of ScoreExplainer."""
    global _explainer_instance
    if _explainer_instance is None:
        _explainer_instance = ScoreExplainer()
    return _explainer_instance
