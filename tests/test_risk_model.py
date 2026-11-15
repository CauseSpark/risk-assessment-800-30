import csv
from pathlib import Path

import pytest

import risk_model as rm

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "data" / "risk_scenarios.csv"
SOURCES = ROOT / "data" / "threat_sources.csv"


# --- Table G-5 and I-2 transcriptions -------------------------------------

@pytest.mark.parametrize("init,adverse,expected", [
    ("Very High", "Very High", "Very High"),
    ("Very High", "Moderate", "High"),
    ("Very High", "Very Low", "Low"),
    ("High", "High", "High"),
    ("High", "Moderate", "Moderate"),
    ("Moderate", "Very High", "High"),
    ("Moderate", "Low", "Low"),
    ("Low", "Very High", "Moderate"),
    ("Low", "Very Low", "Very Low"),
    ("Very Low", "Very High", "Low"),
    ("Very Low", "Low", "Very Low"),
])
def test_table_g5_spot_checks(init, adverse, expected):
    assert rm.overall_likelihood(init, adverse) == expected


@pytest.mark.parametrize("likelihood,impact,expected", [
    ("Very High", "Very High", "Very High"),
    ("Very High", "Very Low", "Very Low"),
    ("High", "High", "High"),
    ("Moderate", "High", "Moderate"),
    ("Moderate", "Very High", "High"),
    ("Low", "Very High", "Moderate"),
    ("Low", "High", "Low"),
    ("Very Low", "High", "Low"),
    ("Very Low", "Moderate", "Very Low"),
])
def test_table_i2_spot_checks(likelihood, impact, expected):
    assert rm.risk_level(likelihood, impact) == expected


def test_tables_are_complete_5x5():
    for table in (rm.TABLE_G5, rm.TABLE_I2):
        assert set(table) == set(rm.LEVELS)
        for row in table.values():
            assert len(row) == 5
            assert all(v in rm.LEVELS for v in row)


@pytest.mark.parametrize("table", [rm.TABLE_G5, rm.TABLE_I2], ids=["G-5", "I-2"])
def test_tables_never_decrease(table):
    """Raising either input never lowers the result."""
    rank = rm.LEVELS.index
    for row_lvl in rm.LEVELS:
        row = [rank(v) for v in table[row_lvl]]
        assert row == sorted(row), f"row {row_lvl} decreases left to right"
    for j in range(5):
        col = [rank(table[lvl][j]) for lvl in rm.LEVELS]
        assert col == sorted(col), f"column {rm.LEVELS[j]} decreases bottom to top"


def test_i2_high_and_very_high_rows_match():
    # SP 800-30 Rev 1 Table I-2 gives the same results for High and Very High likelihood.
    assert rm.TABLE_I2["High"] == rm.TABLE_I2["Very High"]


def test_semi_quantitative_ranges_cover_0_to_100():
    covered = sorted(rng for rng, _ in rm.SEMI_QUANT.values())
    assert covered[0][0] == 0 and covered[-1][1] == 100
    for (lo1, hi1), (lo2, hi2) in zip(covered, covered[1:]):
        assert lo2 == hi1 + 1


def test_bad_level_is_rejected():
    with pytest.raises(rm.RegisterError, match="not one of"):
        rm.overall_likelihood("Medium", "High")
    with pytest.raises(rm.RegisterError):
        rm.risk_level("High", "Severe")


# --- The Acme register ----------------------------------------------------

@pytest.fixture(scope="module")
def risks():
    return rm.load_register(REGISTER, SOURCES)


def test_register_counts(risks):
    assert len(risks) == 15
    assert rm.count_by_level(risks) == {
        "Very High": 0, "High": 1, "Moderate": 5, "Low": 8, "Very Low": 1,
    }


def test_top_risk_is_phishing(risks):
    top = risks[0]
    assert top.risk_id == "R-01"
    assert (top.overall_likelihood, top.risk_level) == ("High", "High")


def test_ranking_is_sorted(risks):
    keys = [r.sort_key() for r in risks]
    assert keys == sorted(keys)


def test_response_rules_hold(risks):
    assert rm.check_response_rules(risks) == []


def test_every_sar_finding_is_in_the_register(risks):
    # The five findings in the RMF repo's SAR (AHR-2026-001 to -005) each map to a risk.
    findings = {r.row["sar_finding"] for r in risks if r.row["sar_finding"]}
    assert findings == {f"AHR-2026-00{i}" for i in range(1, 6)}


def test_sar_poams_line_up_with_rmf_package(risks):
    expected = {"AHR-2026-001": "POAM-0001", "AHR-2026-002": "POAM-0002",
                "AHR-2026-003": "POAM-0003", "AHR-2026-004": "POAM-0004"}
    got = {r.row["sar_finding"]: r.row["poam_id"] for r in risks if r.row["sar_finding"] in expected}
    assert got == expected


def test_poam_ids_are_unique(risks):
    ids = [r.row["poam_id"] for r in risks if r.row["poam_id"]]
    assert len(ids) == len(set(ids))


# --- Validation -----------------------------------------------------------

def _rows():
    with open(REGISTER, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_duplicate_id_rejected():
    rows = _rows()
    rows[1]["risk_id"] = rows[0]["risk_id"]
    with pytest.raises(rm.RegisterError, match="duplicate"):
        rm.score_rows(rows)


def test_bad_control_id_rejected():
    rows = _rows()
    rows[0]["related_controls"] = "IA-2(1);Access Control"
    with pytest.raises(rm.RegisterError, match="not a valid SP 800-53 control ID"):
        rm.score_rows(rows)


def test_bad_response_rejected():
    rows = _rows()
    rows[0]["response"] = "Ignore"
    with pytest.raises(rm.RegisterError, match="response"):
        rm.score_rows(rows)


def test_unknown_source_rejected():
    rows = _rows()
    rows[0]["source_id"] = "TS-99"
    with pytest.raises(rm.RegisterError, match="unknown source_id"):
        rm.score_rows(rows, rm.load_threat_sources(SOURCES))


def test_rule_flags_moderate_mitigate_without_poam():
    rows = _rows()
    for r in rows:
        if r["risk_id"] == "R-03":
            r["poam_id"] = ""
    problems = rm.check_response_rules(rm.score_rows(rows))
    assert problems == ["R-03: Moderate risk with Mitigate response has no POA&M"]


def test_rule_flags_accepted_high_risk():
    rows = _rows()
    rows[0]["response"] = "Accept"
    problems = rm.check_response_rules(rm.score_rows(rows))
    assert any("R-01" in p and "cannot be accepted" in p for p in problems)


def test_cli_success(capsys):
    assert rm.main(["risk_model.py", str(REGISTER)]) == 0
    out = capsys.readouterr().out
    assert "R-01  High" in out


def test_cli_usage_error(capsys):
    assert rm.main(["risk_model.py"]) == 2


def test_cli_missing_file(capsys, tmp_path):
    assert rm.main(["risk_model.py", str(tmp_path / "nope.csv")]) == 1
