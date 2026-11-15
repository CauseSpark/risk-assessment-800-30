"""Checks on the generated Excel risk register."""

import shutil
import subprocess
from pathlib import Path

import pytest
from openpyxl import load_workbook

import build_register as br
import risk_model as rm

ROOT = Path(__file__).resolve().parent.parent
COMMITTED = ROOT / "output" / "acme_hr_portal_risk_register.xlsx"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("xl") / "register.xlsx"
    br.build_workbook(ROOT / "data" / "risk_scenarios.csv", ROOT / "data" / "threat_sources.csv", out)
    return out


def test_sheets_in_order(built):
    wb = load_workbook(built)
    assert wb.sheetnames == ["Instructions", "Risk Register", "Heat Map", "Summary",
                             "Threat Sources", "Scales", "Lookup Tables"]


def test_scores_are_formulas_not_values(built):
    ws = load_workbook(built)["Risk Register"]
    k = br.COL["Overall Likelihood (Table G-5)"]
    m = br.COL["Risk Level (Table I-2)"]
    for r in range(br.FIRST_ROW, br.LAST_ROW + 1):
        assert str(ws[f"{k}{r}"].value).startswith("=IF(")
        assert "INDEX(" in str(ws[f"{m}{r}"].value)


def test_inputs_have_dropdowns(built):
    ws = load_workbook(built)["Risk Register"]
    covered = " ".join(str(dv.sqref) for dv in ws.data_validations.dataValidation)
    for name in ("Likelihood of Initiation / Occurrence", "Likelihood of Adverse Impact",
                 "Impact", "Response", "Threat Source"):
        assert f"{br.COL[name]}{br.FIRST_ROW}:" in covered, name


def test_lookup_tables_match_python(built):
    ws = load_workbook(built)["Lookup Tables"]
    for top, table in ((11, rm.TABLE_G5), (20, rm.TABLE_I2)):
        for i in range(5):
            row_lvl = ws.cell(row=top + 1 + i, column=2).value
            got = [ws.cell(row=top + 1 + i, column=3 + j).value for j in range(5)]
            assert got == table[row_lvl]


def test_register_rows_follow_ranking(built):
    ws = load_workbook(built)["Risk Register"]
    ids = [ws[f"A{r}"].value for r in range(br.FIRST_ROW, br.FIRST_ROW + 15)]
    expected = [r.risk_id for r in rm.load_register(ROOT / "data" / "risk_scenarios.csv")]
    assert ids == expected
    assert ws[f"A{br.FIRST_ROW + 15}"].value is None


def test_committed_workbook_is_current():
    """The committed workbook must hold the same risks, in the same order, as the CSV."""
    ws = load_workbook(COMMITTED)["Risk Register"]
    expected = rm.load_register(ROOT / "data" / "risk_scenarios.csv")
    for i, risk in enumerate(expected):
        r = br.FIRST_ROW + i
        assert ws[f"A{r}"].value == risk.risk_id
        assert ws[f"{br.COL['Impact']}{r}"].value == risk.row["impact"]


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice not installed")
def test_formulas_compute_same_answers_as_python(built, tmp_path):
    """Recalculate with LibreOffice and compare every formula result with risk_model.py."""
    subprocess.run(["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(tmp_path), str(built)],
                   check=True, capture_output=True, timeout=120)
    ws = load_workbook(tmp_path / built.name, data_only=True)["Risk Register"]
    for i, risk in enumerate(rm.load_register(ROOT / "data" / "risk_scenarios.csv")):
        r = br.FIRST_ROW + i
        assert ws[f"{br.COL['Overall Likelihood (Table G-5)']}{r}"].value == risk.overall_likelihood
        assert ws[f"{br.COL['Risk Level (Table I-2)']}{r}"].value == risk.risk_level
