"""The written report must agree with the scored register."""

import re
from pathlib import Path

import pytest

import risk_model as rm

ROOT = Path(__file__).resolve().parent.parent
REPORT = (ROOT / "docs" / "risk_assessment_report.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def risks():
    return rm.load_register(ROOT / "data" / "risk_scenarios.csv")


def _section(title):
    start = REPORT.index(title)
    end = REPORT.find("\n### ", start + 1)
    return REPORT[start:end if end != -1 else None]


def test_level_counts_match(risks):
    table = _section("### Risk levels")
    for level, count in rm.count_by_level(risks).items():
        assert re.search(rf"\| {level} \| {count} \|", table), f"{level} should be {count}"
    assert f"| **Total** | **{len(risks)}** |" in table


def test_heat_map_matches(risks):
    table = _section("### Heat map")
    for like in rm.LEVELS:
        row = re.search(rf"\| \*\*{like}\*\* \|(.*)\|", table).group(1)
        cells = [c.strip() for c in row.split("|")]
        for j, impact in enumerate(rm.LEVELS):
            n = sum(1 for r in risks if r.overall_likelihood == like and r.row["impact"] == impact)
            assert cells[j] == (str(n) if n else ""), f"{like}/{impact}"


def test_moderate_and_higher_table_matches(risks):
    table = _section("### Risks rated Moderate or higher")
    rows = re.findall(r"\| (\d+) \| (R-\d{2}) \|", table)
    expected = [r.risk_id for r in risks if rm.level_rank(r.risk_level) >= 3]
    assert [rid for _, rid in rows] == expected
    assert [int(rank) for rank, _ in rows] == list(range(1, len(expected) + 1))
