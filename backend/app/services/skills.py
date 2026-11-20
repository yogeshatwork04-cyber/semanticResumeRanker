"""Skills taxonomy and extraction service using spaCy PhraseMatcher.

Loads canonical skills, aliases, and curated related-skill relationships,
mapping textual mentions directly to canonical entities deterministically.
"""

import json
from pathlib import Path

import spacy
from spacy.matcher import PhraseMatcher

from app.config import get_settings

settings = get_settings()


class SkillsService:
    """Manages skill taxonomy and extracts skills using spaCy PhraseMatcher."""

    def __init__(self, taxonomy_path: Path | None = None):
        if taxonomy_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            taxonomy_path = base_dir / "data" / "skills_taxonomy.json"

        self.taxonomy_path = taxonomy_path
        self._nlp = spacy.load(settings.spacy_model_name, disable=["ner", "parser"])
        self._matcher = PhraseMatcher(self._nlp.vocab, attr="LOWER")
        self._canonical_skills: dict[str, dict] = {}
        self._alias_to_canonical: dict[str, str] = {}
        self._related_skills: dict[str, dict[str, float]] = {}
        self._load_taxonomy()

    def _load_taxonomy(self) -> None:
        """Load skills from JSON taxonomy and configure PhraseMatcher patterns."""
        if not self.taxonomy_path.exists():
            raise FileNotFoundError(f"Skills taxonomy not found at {self.taxonomy_path}")

        with open(self.taxonomy_path, encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("skills", []):
            canonical = item["name"]
            category = item.get("category", "General")
            aliases = item.get("aliases", [])

            self._canonical_skills[canonical] = {
                "name": canonical,
                "category": category,
                "aliases": aliases,
            }

            self._alias_to_canonical[canonical.lower()] = canonical
            pattern_docs = [self._nlp.make_doc(canonical)]

            for alias in aliases:
                self._alias_to_canonical[alias.lower()] = canonical
                pattern_docs.append(self._nlp.make_doc(alias))

            self._matcher.add(canonical, pattern_docs)

        # Load curated related skills map
        self._related_skills = data.get("related_skills", {})

    def extract_skills(self, text: str) -> list[str]:
        """Extract all canonical skills present in the text, preserving order."""
        if not text:
            return []

        doc = self._nlp.make_doc(text)
        matches = self._matcher(doc)

        found_skills: list[str] = []
        seen = set()

        for match_id, _start, _end in matches:
            canonical_name = self._nlp.vocab.strings[match_id]
            if canonical_name not in seen:
                seen.add(canonical_name)
                found_skills.append(canonical_name)

        return found_skills

    def get_canonical_name(self, skill_mention: str) -> str | None:
        """Look up canonical name for a given skill mention or alias."""
        clean = skill_mention.strip().lower()
        return self._alias_to_canonical.get(clean)

    def get_skill_category(self, canonical_name: str) -> str:
        """Return category for a given canonical skill."""
        return self._canonical_skills.get(canonical_name, {}).get("category", "General")

    def get_all_canonical_skills(self) -> list[str]:
        """Return list of all recognized canonical skills."""
        return list(self._canonical_skills.keys())

    def get_curated_related_credit(self, jd_skill: str, cand_skill: str) -> float | None:
        """Check if candidate skill is a curated relation to jd_skill with explicit credit."""
        jd_canonical = self.get_canonical_name(jd_skill) or jd_skill
        cand_canonical = self.get_canonical_name(cand_skill) or cand_skill

        rel_map = self._related_skills.get(jd_canonical, {})
        if cand_canonical in rel_map:
            return rel_map[cand_canonical]
        return None


_skills_service_instance: SkillsService | None = None


def get_skills_service() -> SkillsService:
    """Return singleton instance of SkillsService."""
    global _skills_service_instance
    if _skills_service_instance is None:
        _skills_service_instance = SkillsService()
    return _skills_service_instance
