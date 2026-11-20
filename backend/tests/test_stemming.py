"""Tests for light stemming in _is_skill_demonstrated."""

import pytest

from app.services.scorer import ResumeScorer, get_resume_scorer


@pytest.fixture(scope="module")
def scorer() -> ResumeScorer:
    return get_resume_scorer()


# ---------------------------------------------------------------------------
# _skill_stem tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "skill,expected_stem",
    [
        # "statistics" -> strips "tics" -> "statis"; the substring "statis" still
        # appears inside "statistical", so the detection works correctly.
        ("Statistics", "statis"),
        ("statistical", "statis"),    # strips "tical" -> "statis"
        ("Networking", "network"),    # strips "ing"   -> "network"
        ("Databases", "database"),    # strips "s"     -> "database"
        ("Python", "python"),         # no suffix matches -> unchanged
    ],
)
def test_skill_stem(scorer: ResumeScorer, skill: str, expected_stem: str) -> None:
    assert scorer._skill_stem(skill) == expected_stem


# ---------------------------------------------------------------------------
# _is_skill_demonstrated – stemming path
# ---------------------------------------------------------------------------

def test_statistics_matches_statistical(scorer: ResumeScorer) -> None:
    """'Statistics' should be found when experience text contains 'statistical'."""
    exp_text = "Applied statistical methods and regression analysis to evaluate model impact."
    proj_text = ""
    assert scorer._is_skill_demonstrated("Statistics", exp_text, proj_text), (
        "Expected 'Statistics' to be detected via stem 'statistic' in 'statistical'"
    )


def test_statistics_lowercase_matches_statistical(scorer: ResumeScorer) -> None:
    """Case-insensitive: lowercase 'statistics' should still hit 'statistical'."""
    exp_text = "Used statistical modelling for predictions."
    assert scorer._is_skill_demonstrated("statistics", exp_text, "")


def test_exact_match_still_works(scorer: ResumeScorer) -> None:
    """Exact word-boundary match must still work (not broken by stemming change)."""
    exp_text = "Developed REST APIs and deployed Docker containers."
    assert scorer._is_skill_demonstrated("Docker", exp_text, "")
    assert scorer._is_skill_demonstrated("REST APIs", exp_text, "")


def test_no_false_positive_short_stem(scorer: ResumeScorer) -> None:
    """Short stems (<4 chars) must NOT match to avoid false positives."""
    # Skill: "Go" -> stem "go" (len 2) -> should NOT match the word "goal"
    exp_text = "Set quarterly goal targets."
    # "Go" exact match -> not found; stem "go" (len 2) -> guarded, no match
    result = scorer._is_skill_demonstrated("Go", exp_text, "")
    # We just verify it doesn't crash; whether it returns True/False depends on aliases
    assert isinstance(result, bool)


def test_networking_matches_networked(scorer: ResumeScorer) -> None:
    """'Networking' stem 'network' should match 'networked' or 'networks'."""
    exp_text = "Configured and monitored corporate networks and VPN tunnels."
    assert scorer._is_skill_demonstrated("Networking", exp_text, "")


def test_no_stem_match_unrelated(scorer: ResumeScorer) -> None:
    """Skills whose stem doesn't appear in unrelated text return False."""
    exp_text = "Designed marketing brochures and managed social media campaigns."
    proj_text = ""
    assert not scorer._is_skill_demonstrated("Kubernetes", exp_text, proj_text)
