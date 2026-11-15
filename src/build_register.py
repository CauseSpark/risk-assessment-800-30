"""Build the Excel risk register from the CSV inputs.

The workbook keeps the SP 800-30 logic live: overall likelihood and risk level are
INDEX/MATCH formulas against the lookup tables, so changing a rating in Excel
re-scores the risk, updates the heat map, and updates the summary counts.

    python src/build_register.py
    python src/build_register.py --out output/my_register.xlsx
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from risk_model import LEVELS, RESPONSES, SEMI_QUANT, TABLE_G5, TABLE_I2, load_register  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "output" / "acme_hr_portal_risk_register.xlsx"

FIRST_ROW = 5          # first data row on the Risk Register sheet
CAPACITY = 50          # formatted rows available for risks
LAST_ROW = FIRST_ROW + CAPACITY - 1

FONT = "Arial"
LEVEL_FILL = {
    "Very High": "8B0000",
    "High": "E06666",
    "Moderate": "FFD966",
    "Low": "B6D7A8",
    "Very Low": "D9EAD3",
}
LEVEL_FONT = {"Very High": "FFFFFF"}
HEADER_FILL = PatternFill("solid", fgColor="1F3864")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
CALC_FILL = PatternFill("solid", fgColor="F2F2F2")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# (header, width, kind) where kind is text, input or formula
COLUMNS = [
    ("Risk ID", 8, "text"),
    ("Risk Title", 34, "text"),
    ("Threat Source", 26, "text"),
    ("Source Type", 13, "formula"),
    ("Threat Event", 40, "text"),
    ("Vulnerability / Predisposing Condition", 40, "text"),
    ("Existing Controls", 32, "text"),
    ("Related SP 800-53 Controls", 18, "text"),
    ("Likelihood of Initiation / Occurrence", 15, "input"),
    ("Likelihood of Adverse Impact", 15, "input"),
    ("Overall Likelihood (Table G-5)", 15, "formula"),
    ("Impact", 12, "input"),
    ("Risk Level (Table I-2)", 13, "formula"),
    ("Risk Score (1-5)", 9, "formula"),
    ("Response", 12, "input"),
    ("Response Plan", 42, "text"),
    ("Owner", 22, "text"),
    ("SAR Finding", 14, "text"),
    ("POA&M", 11, "text"),
]
COL = {name: get_column_letter(i + 1) for i, (name, _, _) in enumerate(COLUMNS)}


def font(bold=False, color="000000", size=10, italic=False):
    return Font(name=FONT, bold=bold, color=color, size=size, italic=italic)


def write_title(ws, title, subtitle):
    ws["A1"] = title
    ws["A1"].font = font(bold=True, size=14, color="1F3864")
    ws["A2"] = subtitle
    ws["A2"].font = font(italic=True, color="595959")


def style_header(cell):
    cell.font = font(bold=True, color="FFFFFF")
    cell.fill = HEADER_FILL
    cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    cell.border = BORDER


def add_level_formatting(ws, rng):
    for level, color in LEVEL_FILL.items():
        ws.conditional_formatting.add(
            rng,
            CellIsRule(operator="equal", formula=[f'"{level}"'],
                       fill=PatternFill("solid", fgColor=color),
                       font=Font(name=FONT, color=LEVEL_FONT.get(level, "000000"), bold=True)),
        )


def build_lookup_sheet(wb):
    ws = wb.create_sheet("Lookup Tables")
    write_title(ws, "Lookup tables", "Source: NIST SP 800-30 Rev 1, Tables G-5 and I-2 (Sept 2012). Do not edit.")
    ws["B3"] = "Levels"
    ws["B3"].font = font(bold=True)
    for i, lvl in enumerate(LEVELS):
        ws.cell(row=4 + i, column=2, value=lvl).font = font()

    def matrix(top, title, row_label, col_label, table):
        ws.cell(row=top - 1, column=2, value=title).font = font(bold=True)
        ws.cell(row=top - 1, column=3, value=f"Rows: {row_label}. Columns: {col_label}.").font = font(italic=True, color="595959")
        corner = ws.cell(row=top, column=2, value="")
        style_header(corner)
        for j, lvl in enumerate(LEVELS):
            style_header(ws.cell(row=top, column=3 + j, value=lvl))
        for i, row_lvl in enumerate(LEVELS):
            r = top + 1 + i
            label = ws.cell(row=r, column=2, value=row_lvl)
            label.font = font(bold=True)
            label.border = BORDER
            for j, val in enumerate(table[row_lvl]):
                c = ws.cell(row=r, column=3 + j, value=val)
                c.font = font(color=LEVEL_FONT.get(val, "000000"))
                c.fill = PatternFill("solid", fgColor=LEVEL_FILL[val])
                c.border = BORDER
                c.alignment = Alignment(horizontal="center")

    # Rows are listed Very Low -> Very High so MATCH works on the same order as LEVELS.
    matrix(11, "Table G-5: Overall likelihood", "likelihood of initiation / occurrence",
           "likelihood of adverse impact", TABLE_G5)
    matrix(20, "Table I-2: Level of risk", "overall likelihood", "level of impact", TABLE_I2)

    ws["B28"] = "Risk responses (NIST SP 800-39)"
    ws["B28"].font = font(bold=True)
    for i, resp in enumerate(RESPONSES):
        ws.cell(row=29 + i, column=2, value=resp).font = font()

    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 34
    for c in "CDEFG":
        ws.column_dimensions[c].width = 14
    return ws


LEVEL_RANGE = "'Lookup Tables'!$B$4:$B$8"
G5_BODY, G5_ROWS, G5_COLS = "'Lookup Tables'!$C$12:$G$16", "'Lookup Tables'!$B$12:$B$16", "'Lookup Tables'!$C$11:$G$11"
I2_BODY, I2_ROWS, I2_COLS = "'Lookup Tables'!$C$21:$G$25", "'Lookup Tables'!$B$21:$B$25", "'Lookup Tables'!$C$20:$G$20"
RESPONSE_RANGE = "'Lookup Tables'!$B$29:$B$33"


def build_sources_sheet(wb, sources_path):
    ws = wb.create_sheet("Threat Sources")
    write_title(ws, "Threat sources considered", "Taxonomy follows NIST SP 800-30 Rev 1, Appendix D. Characteristics apply to adversarial sources only.")
    headers = ["Source ID", "Name", "Source Type", "Description", "Capability", "Intent", "Targeting", "Range of Effects"]
    widths = [10, 34, 14, 60, 12, 10, 11, 14]
    for j, (h, w) in enumerate(zip(headers, widths)):
        style_header(ws.cell(row=4, column=1 + j, value=h))
        ws.column_dimensions[get_column_letter(1 + j)].width = w
    with open(sources_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    keys = ["source_id", "name", "source_type", "description", "capability", "intent", "targeting", "range_of_effects"]
    for i, r in enumerate(rows):
        for j, k in enumerate(keys):
            c = ws.cell(row=5 + i, column=1 + j, value=r[k] or None)
            c.font = font()
            c.border = BORDER
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A5"
    return len(rows)


def build_register_sheet(wb, risks, source_names, n_sources):
    ws = wb.active
    ws.title = "Risk Register"
    write_title(ws, "Acme HR Portal: Risk Register",
                "FICTIONAL. Scored with NIST SP 800-30 Rev 1. Yellow cells are inputs; grey cells are formulas.")
    ws["A3"] = "Assessment date: 2026-11-13   |   Version 1.0   |   Prepared by Sam Okafor, ISSO (fictional)"
    ws["A3"].font = font(color="595959")

    for j, (header, width, _) in enumerate(COLUMNS):
        style_header(ws.cell(row=4, column=1 + j, value=header))
        ws.column_dimensions[get_column_letter(1 + j)].width = width
    ws.row_dimensions[4].height = 45

    src_last = 4 + n_sources
    src_names = f"'Threat Sources'!$B$5:$B${src_last}"
    src_types = f"'Threat Sources'!$C$5:$C${src_last}"

    for i in range(CAPACITY):
        r = FIRST_ROW + i
        risk = risks[i] if i < len(risks) else None
        row = risk.row if risk else {}
        values = {
            "Risk ID": row.get("risk_id"),
            "Risk Title": row.get("title"),
            "Threat Source": source_names.get(row.get("source_id")) if risk else None,
            "Threat Event": row.get("threat_event"),
            "Vulnerability / Predisposing Condition": row.get("vulnerability"),
            "Existing Controls": row.get("existing_controls"),
            "Related SP 800-53 Controls": row.get("related_controls", "").replace(";", ", ") or None,
            "Likelihood of Initiation / Occurrence": row.get("likelihood_initiation"),
            "Likelihood of Adverse Impact": row.get("likelihood_adverse_impact"),
            "Impact": row.get("impact"),
            "Response": row.get("response"),
            "Response Plan": row.get("response_plan"),
            "Owner": row.get("owner"),
            "SAR Finding": row.get("sar_finding") or None,
            "POA&M": row.get("poam_id") or None,
        }
        c, i_, j_, k, l, m = (COL["Threat Source"], COL["Likelihood of Initiation / Occurrence"],
                              COL["Likelihood of Adverse Impact"], COL["Overall Likelihood (Table G-5)"],
                              COL["Impact"], COL["Risk Level (Table I-2)"])
        values["Source Type"] = f'=IF({c}{r}="","",IFERROR(INDEX({src_types},MATCH({c}{r},{src_names},0)),""))'
        values["Overall Likelihood (Table G-5)"] = (
            f'=IF(OR({i_}{r}="",{j_}{r}=""),"",INDEX({G5_BODY},MATCH({i_}{r},{G5_ROWS},0),MATCH({j_}{r},{G5_COLS},0)))')
        values["Risk Level (Table I-2)"] = (
            f'=IF(OR({k}{r}="",{l}{r}=""),"",INDEX({I2_BODY},MATCH({k}{r},{I2_ROWS},0),MATCH({l}{r},{I2_COLS},0)))')
        values["Risk Score (1-5)"] = f'=IF({m}{r}="","",MATCH({m}{r},{LEVEL_RANGE},0))'

        for j, (header, _, kind) in enumerate(COLUMNS):
            cell = ws.cell(row=r, column=1 + j, value=values.get(header))
            cell.border = BORDER
            cell.alignment = Alignment(wrap_text=True, vertical="top",
                                       horizontal="center" if kind != "text" or header in ("Risk ID", "SAR Finding", "POA&M") else None)
            if kind == "input":
                cell.fill = INPUT_FILL
                cell.font = font(color="0000FF")
            elif kind == "formula":
                cell.fill = CALC_FILL
                cell.font = font()
            else:
                cell.font = font()

    last = LAST_ROW
    dv_level = DataValidation(type="list", formula1=LEVEL_RANGE, allow_blank=True,
                              showErrorMessage=True, errorTitle="Invalid rating",
                              error="Pick Very Low, Low, Moderate, High or Very High.")
    dv_resp = DataValidation(type="list", formula1=RESPONSE_RANGE, allow_blank=True,
                             showErrorMessage=True, errorTitle="Invalid response",
                             error="Pick Accept, Avoid, Mitigate, Share or Transfer.")
    dv_src = DataValidation(type="list", formula1=src_names, allow_blank=True,
                            showErrorMessage=True, errorTitle="Unknown source",
                            error="Add the source on the Threat Sources sheet first.")
    for dv in (dv_level, dv_resp, dv_src):
        ws.add_data_validation(dv)
    for name in ("Likelihood of Initiation / Occurrence", "Likelihood of Adverse Impact", "Impact"):
        dv_level.add(f"{COL[name]}{FIRST_ROW}:{COL[name]}{last}")
    dv_resp.add(f"{COL['Response']}{FIRST_ROW}:{COL['Response']}{last}")
    dv_src.add(f"{COL['Threat Source']}{FIRST_ROW}:{COL['Threat Source']}{last}")

    for name in ("Overall Likelihood (Table G-5)", "Risk Level (Table I-2)"):
        add_level_formatting(ws, f"{COL[name]}{FIRST_ROW}:{COL[name]}{last}")
    # Flag Moderate+ Mitigate risks that have no POA&M (methodology Section 6).
    poam, resp, score = COL["POA&M"], COL["Response"], COL["Risk Score (1-5)"]
    ws.conditional_formatting.add(
        f"{poam}{FIRST_ROW}:{poam}{last}",
        FormulaRule(formula=[f'AND(${resp}{FIRST_ROW}="Mitigate",${poam}{FIRST_ROW}="",N(${score}{FIRST_ROW})>=3)'],
                    fill=PatternFill("solid", fgColor="FF0000")))

    ws.freeze_panes = f"C{FIRST_ROW}"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(COLUMNS))}{last}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = "4:4"
    return ws


def reg_range(name):
    return f"'Risk Register'!${COL[name]}${FIRST_ROW}:${COL[name]}${LAST_ROW}"


def build_heatmap_sheet(wb):
    ws = wb.create_sheet("Heat Map")
    write_title(ws, "Risk heat map", "Each cell counts risks by overall likelihood and impact. Cell color is the Table I-2 risk level.")
    ws["B4"] = "Overall likelihood ↓   /   Impact →"
    style_header(ws["B4"])
    for j, lvl in enumerate(LEVELS):
        style_header(ws.cell(row=4, column=3 + j, value=lvl))
    like_rng, imp_rng = reg_range("Overall Likelihood (Table G-5)"), reg_range("Impact")
    for i, row_lvl in enumerate(reversed(LEVELS)):   # Very High at the top
        r = 5 + i
        label = ws.cell(row=r, column=2, value=row_lvl)
        style_header(label)
        for j, col_lvl in enumerate(LEVELS):
            col = get_column_letter(3 + j)
            c = ws.cell(row=r, column=3 + j, value=f"=COUNTIFS({like_rng},$B{r},{imp_rng},{col}$4)")
            level = TABLE_I2[row_lvl][j]
            c.fill = PatternFill("solid", fgColor=LEVEL_FILL[level])
            c.font = font(bold=True, size=14, color=LEVEL_FONT.get(level, "000000"))
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = BORDER
            c.number_format = '0;-0;""'   # hide zeros so populated cells stand out
        ws.row_dimensions[r].height = 42
    ws["B11"] = "Total plotted"
    ws["B11"].font = font(bold=True)
    ws["C11"] = "=SUM(C5:G9)"
    ws["C11"].font = font(bold=True)

    ws["B13"] = "Legend"
    ws["B13"].font = font(bold=True)
    for i, lvl in enumerate(reversed(LEVELS)):
        c = ws.cell(row=14 + i, column=2, value=lvl)
        c.fill = PatternFill("solid", fgColor=LEVEL_FILL[lvl])
        c.font = font(color=LEVEL_FONT.get(lvl, "000000"), bold=True)
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 34
    for c in "CDEFG":
        ws.column_dimensions[c].width = 14
    ws.page_setup.orientation = "landscape"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1


def build_summary_sheet(wb):
    ws = wb.create_sheet("Summary")
    write_title(ws, "Summary", "All figures are formulas over the Risk Register sheet.")
    level_rng, resp_rng = reg_range("Risk Level (Table I-2)"), reg_range("Response")
    id_rng, poam_rng, score_rng = reg_range("Risk ID"), reg_range("POA&M"), reg_range("Risk Score (1-5)")

    ws["B4"], ws["C4"] = "Risk level", "Count"
    style_header(ws["B4"]); style_header(ws["C4"])
    for i, lvl in enumerate(reversed(LEVELS)):
        r = 5 + i
        c = ws.cell(row=r, column=2, value=lvl)
        c.fill = PatternFill("solid", fgColor=LEVEL_FILL[lvl])
        c.font = font(bold=True, color=LEVEL_FONT.get(lvl, "000000"))
        ws.cell(row=r, column=3, value=f"=COUNTIF({level_rng},B{r})").font = font()
    ws["B10"] = "Total risks"
    ws["B10"].font = font(bold=True)
    ws["C10"] = f"=COUNTA({id_rng})"
    ws["C10"].font = font(bold=True)

    ws["E4"], ws["F4"] = "Response", "Count"
    style_header(ws["E4"]); style_header(ws["F4"])
    for i, resp in enumerate(RESPONSES):
        r = 5 + i
        ws.cell(row=r, column=5, value=resp).font = font()
        ws.cell(row=r, column=6, value=f"=COUNTIF({resp_rng},E{r})").font = font()

    ws["B13"], ws["C13"] = "Check", "Result"
    style_header(ws["B13"]); style_header(ws["C13"])
    checks = [
        ("Risks rated Moderate or higher", f'=COUNTIF({score_rng},">=3")'),
        ("Risks with a POA&M", f'=COUNTA({poam_rng})'),
        ("Moderate+ Mitigate risks missing a POA&M (should be 0)",
         f'=COUNTIFS({resp_rng},"Mitigate",{score_rng},">=3",{poam_rng},"")'),
        ("High+ risks marked Accept (should be 0)", f'=COUNTIFS({resp_rng},"Accept",{score_rng},">=4")'),
    ]
    for i, (label, formula) in enumerate(checks):
        r = 14 + i
        ws.cell(row=r, column=2, value=label).font = font()
        ws.cell(row=r, column=3, value=formula).font = font(bold=True)
    for r in (16, 17):
        ws.conditional_formatting.add(f"C{r}", CellIsRule(operator="greaterThan", formula=["0"],
                                      fill=PatternFill("solid", fgColor="FF0000"), font=Font(name=FONT, color="FFFFFF", bold=True)))
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 52
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 3
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 10


SCALE_TEXT = {
    # My own paraphrases of the SP 800-30 Rev 1 Appendix G and H scale intent.
    "initiation": {
        "Very High": "Adversary is almost certain to try; for non-adversarial events, it happens more than once a month.",
        "High": "Adversary is highly likely to try; event happens a few times a year to monthly.",
        "Moderate": "Adversary is somewhat likely to try; event happens about once a year or a few times over several years.",
        "Low": "Adversary is unlikely to try; event happens less than once a year but more than once a decade.",
        "Very Low": "Adversary is highly unlikely to try; event happens less than once a decade.",
    },
    "adverse": {
        "Very High": "If the event happens, harm is almost certain.",
        "High": "If the event happens, harm is highly likely.",
        "Moderate": "If the event happens, harm is somewhat likely.",
        "Low": "If the event happens, harm is unlikely.",
        "Very Low": "If the event happens, harm is highly unlikely.",
    },
    "impact": {
        "Very High": "Multiple severe or catastrophic effects on operations, assets, people, or the organization.",
        "High": "Severe effect: major loss of mission capability, major damage, or serious harm to individuals.",
        "Moderate": "Serious effect: significant degradation, significant damage or financial loss, or significant harm to individuals.",
        "Low": "Limited effect: noticeable degradation, minor damage or loss, or minor harm to individuals.",
        "Very Low": "Negligible effect.",
    },
}


def build_scales_sheet(wb):
    ws = wb.create_sheet("Scales")
    write_title(ws, "Assessment scales",
                "Plain-language summaries of NIST SP 800-30 Rev 1 Appendix G and H scales. Read the publication for the official wording.")
    headers = ["Level", "0-100 range", "0-10 value", "Likelihood of initiation / occurrence",
               "Likelihood of adverse impact", "Impact"]
    widths = [12, 12, 10, 52, 36, 52]
    for j, (h, w) in enumerate(zip(headers, widths)):
        style_header(ws.cell(row=4, column=1 + j, value=h))
        ws.column_dimensions[get_column_letter(1 + j)].width = w
    for i, lvl in enumerate(reversed(LEVELS)):
        r = 5 + i
        (lo, hi), ten = SEMI_QUANT[lvl]
        row = [lvl, f"{lo}-{hi}", ten, SCALE_TEXT["initiation"][lvl], SCALE_TEXT["adverse"][lvl], SCALE_TEXT["impact"][lvl]]
        for j, v in enumerate(row):
            c = ws.cell(row=r, column=1 + j, value=v)
            c.font = font(bold=(j == 0), color=LEVEL_FONT.get(lvl, "000000") if j == 0 else "000000")
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = BORDER
            if j == 0:
                c.fill = PatternFill("solid", fgColor=LEVEL_FILL[lvl])
        ws.row_dimensions[r].height = 42


def build_instructions_sheet(wb):
    ws = wb.create_sheet("Instructions", 0)
    write_title(ws, "How to use this workbook", "Acme HR Portal risk register. Fictional study material by Peyton Seay.")
    lines = [
        ("What this is", "A system-level (Tier 3) risk register for the fictional Acme HR Portal, scored with NIST SP 800-30 Rev 1."),
        ("Inputs (yellow, blue text)", "Likelihood of initiation / occurrence, likelihood of adverse impact, impact, and response. Pick values from the dropdowns."),
        ("Formulas (grey)", "Source type, overall likelihood (Table G-5), risk level (Table I-2), and risk score. Do not type over them."),
        ("Add a risk", "Fill in the next empty row on the Risk Register sheet. Rows through row 54 are pre-formatted with formulas and dropdowns."),
        ("Add a threat source", "Add a row on the Threat Sources sheet, then rebuild with src/build_register.py so the dropdown range includes it."),
        ("Heat Map and Summary", "Update automatically. The two checks at the bottom of Summary should both be 0."),
        ("Red POA&M cell", "A Moderate or higher risk with a Mitigate response must have a POA&M ID (methodology Section 6)."),
        ("Source of truth", "data/risk_scenarios.csv is the source; this file is generated from it. Change the CSV and rebuild for permanent edits."),
        ("Fictional data", "Acme Defense Fabrication, the HR Portal, and every person, vendor, and finding are invented. No real system data."),
    ]
    for i, (k, v) in enumerate(lines):
        r = 4 + i
        ws.cell(row=r, column=1, value=k).font = font(bold=True)
        c = ws.cell(row=r, column=2, value=v)
        c.font = font()
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 30
    ws["A15"] = "Example input cell"
    ws["A15"].font = font(bold=True)
    ws["B15"] = "Moderate"
    ws["B15"].fill = INPUT_FILL
    ws["B15"].font = font(color="0000FF")
    ws["A16"] = "Example formula cell"
    ws["A16"].font = font(bold=True)
    ws["B16"] = "Calculated by the workbook"
    ws["B16"].fill = CALC_FILL
    ws["B16"].font = font()
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 100


def build_workbook(register_csv: Path, sources_csv: Path, out: Path) -> Path:
    risks = load_register(register_csv, sources_csv)
    if len(risks) > CAPACITY:
        raise ValueError(f"register has {len(risks)} risks; the workbook holds {CAPACITY}")
    with open(sources_csv, newline="", encoding="utf-8") as f:
        source_names = {r["source_id"]: r["name"] for r in csv.DictReader(f)}

    wb = Workbook()
    build_lookup_sheet(wb)
    n_sources = build_sources_sheet(wb, sources_csv)
    build_register_sheet(wb, risks, source_names, n_sources)
    build_heatmap_sheet(wb)
    build_summary_sheet(wb)
    build_scales_sheet(wb)
    build_instructions_sheet(wb)
    order = ["Instructions", "Risk Register", "Heat Map", "Summary", "Threat Sources", "Scales", "Lookup Tables"]
    wb._sheets = [wb[name] for name in order]
    wb.active = 1
    wb.calculation.fullCalcOnLoad = True   # Excel computes every formula when the file opens
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--register", type=Path, default=ROOT / "data" / "risk_scenarios.csv")
    p.add_argument("--sources", type=Path, default=ROOT / "data" / "threat_sources.csv")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)
    out = build_workbook(args.register, args.sources, args.out)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
