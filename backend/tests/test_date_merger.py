"""Unit tests for date interval merging and experience calculation."""

from datetime import date

from app.services.resume_extractor import (
    calculate_total_years,
    merge_date_intervals,
)


def test_merge_disjoint_intervals():
    """Disjoint intervals should not be merged."""
    intervals = [
        (date(2018, 1, 1), date(2019, 1, 1)),
        (date(2020, 1, 1), date(2021, 1, 1)),
    ]
    merged = merge_date_intervals(intervals)
    assert len(merged) == 2
    assert merged[0] == (date(2018, 1, 1), date(2019, 1, 1))
    assert merged[1] == (date(2020, 1, 1), date(2021, 1, 1))


def test_merge_overlapping_intervals():
    """Overlapping intervals must merge into a single interval covering the union."""
    intervals = [
        (date(2020, 1, 1), date(2022, 6, 1)),
        (date(2021, 1, 1), date(2023, 1, 1)),  # Overlaps by 1.5 years
    ]
    merged = merge_date_intervals(intervals)
    assert len(merged) == 1
    assert merged[0] == (date(2020, 1, 1), date(2023, 1, 1))


def test_merge_subset_interval():
    """An interval fully contained within another interval should be swallowed."""
    intervals = [
        (date(2019, 1, 1), date(2023, 1, 1)),
        (date(2020, 5, 1), date(2021, 5, 1)),  # Sub-interval
    ]
    merged = merge_date_intervals(intervals)
    assert len(merged) == 1
    assert merged[0] == (date(2019, 1, 1), date(2023, 1, 1))


def test_merge_contiguous_intervals():
    """Consecutive jobs with no real gap should merge cleanly."""
    intervals = [
        (date(2020, 1, 1), date(2021, 12, 31)),
        (date(2022, 1, 1), date(2023, 12, 31)),
    ]
    merged = merge_date_intervals(intervals)
    assert len(merged) == 1
    assert merged[0] == (date(2020, 1, 1), date(2023, 12, 31))


def test_total_years_no_double_count():
    """Total years should match the union of days without double counting."""
    intervals = [
        (date(2020, 1, 1), date(2022, 1, 1)),  # 2 years
        (date(2020, 7, 1), date(2022, 7, 1)),  # Overlaps; union is 2020-01-01 to 2022-07-01 (~2.5 years)
    ]
    merged = merge_date_intervals(intervals)
    years = calculate_total_years(merged)
    assert years == 2.5
