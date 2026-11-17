"""Build the Excel risk register from the CSV inputs.

The workbook keeps the SP 800-30 logic live: overall likelihood and risk level are
INDEX/MATCH formulas against the lookup tables, so changing a rating in Excel
re-scores the risk, updates the heat map, and updates the summary counts.

    python src/build_register.py
    python src/build_register.py --out output/my_register.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from risk_model import LEVELS, RESPONSES, SEMI_QUANT, TABLE_G5, TABLE_I2, load_register, load_threat_sources

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

# (header, width, kind, CSV column) where kind is text, input or formula
COLUMNS = [
    ("Risk ID", 8, "text", "risk_id"),
    ("Risk Title", 34, "text", "title"),
    ("Threat Source", 26, "text", "source_name"),
    ("Source Type", 13, "formula", None),
    ("Threat Event", 40, "text", "threat_event"),
    ("Vulnerability / Predisposing Condition", 40, "text", "vulnerability"),
    ("Existing Controls", 32, "text", "existing_controls"),
    ("Related SP 800-53 Controls", 18, "text", "related_controls"),
    ("Likelihood of Initiation / Occurrence", 15, "input", "likelihood_initiation"),
    ("Likelihood of Adverse Impact", 15, "input", "likelihood_adverse_impact"),
    ("Overall Likelihood (Table G-5)", 15, "formula", None),
    ("Impact", 12, "input", "impact"),
    ("Risk Level (Table I-2)", 13, "formula", None),
    ("Risk Score (1-5)", 9, "formula", None),
    ("Response", 12, "input", "response"),
    ("Response Plan", 42, "text", "response_plan"),
    ("Owner", 22, "text", "owner"),
    ("SAR Finding", 14, "text", "sar_finding"),
    ("POA&M", 11, "text", "poam_id"),
]
COL = {name: get_column_letter(i + 1) for i, (name, *_rest) in enumerate(COLUMNS)}
CENTERED_TEXT = ("Risk ID", "SAR Finding", "POA&M")
LEVEL_COLS = "CDEFG"   # one column per level on the matrix sheets


def font(bold=False, color="000000", size=10, italic=False):
    return Font(name=FONT, bold=bold, color=color, size=size, italic=italic)


def put(ws, ref, value, **style):
    """Write a value in the workbook font and return the cell."""
    cell = ws[ref]
    cell.value = value
    cell.font = font(**style)
    return cell


def write_title(ws, title, subtitle):
    put(ws, "A1", title, bold=True, size=14, color="1F3864")
    put(ws, "A2", subtitle, italic=True, color="595959")


def header(ws, ref, text):
    cell = put(ws, ref, text, bold=True, color="FFFFFF")
    cell.fill = HEADER_FILL
    cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    cell.border = BORDER
    return cell


def header_row(ws, row, names, widths=None, first=1):
    for j, name in enumerate(names):
        letter = get_column_letter(first + j)
        header(ws, f"{letter}{row}", name)
        if widths:
            ws.column_dimensions[letter].width = widths[j]


def shade(cell, level, **style):
    """Give a cell the fill and font colour of a risk level."""
    cell.fill = PatternFill("solid", fgColor=LEVEL_FILL[level])
    cell.font = font(color=LEVEL_FONT.get(level, "000000"), **style)
    return cell


def set_widths(ws, **columns):
    for letter, width in columns.items():
        ws.column_dimensions[letter].width = width


def span(name):
    return f"{COL[name]}{FIRST_ROW}:{COL[name]}{LAST_ROW}"


def reg_range(name):
    return f"'Risk Register'!${COL[name]}${FIRST_ROW}:${COL[name]}${LAST_ROW}"


def fit_landscape(ws, pages_tall):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = pages_tall
    ws.sheet_properties.pageSetUpPr.fitToPage = True


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
    put(ws, "B3", "Levels", bold=True)
    for r, lvl in enumerate(LEVELS, start=4):
        put(ws, f"B{r}", lvl)

    def matrix(top, title, row_label, col_label, table):
        put(ws, f"B{top - 1}", title, bold=True)
        put(ws, f"C{top - 1}", f"Rows: {row_label}. Columns: {col_label}.", italic=True, color="595959")
        header_row(ws, top, ["", *LEVELS], first=2)
        for r, row_lvl in enumerate(LEVELS, start=top + 1):
            put(ws, f"B{r}", row_lvl, bold=True).border = BORDER
            for letter, val in zip(LEVEL_COLS, table[row_lvl]):
                c = shade(put(ws, f"{letter}{r}", val), val)
                c.border = BORDER
                c.alignment = Alignment(horizontal="center")

    # Rows are listed Very Low -> Very High so MATCH works on the same order as LEVELS.
    matrix(11, "Table G-5: Overall likelihood", "likelihood of initiation / occurrence",
           "likelihood of adverse impact", TABLE_G5)
    matrix(20, "Table I-2: Level of risk", "overall likelihood", "level of impact", TABLE_I2)

    put(ws, "B28", "Risk responses (NIST SP 800-39)", bold=True)
    for r, resp in enumerate(RESPONSES, start=29):
        put(ws, f"B{r}", resp)
    set_widths(ws, A=3, B=34, **dict.fromkeys(LEVEL_COLS, 14))


LEVEL_RANGE = "'Lookup Tables'!$B$4:$B$8"
G5_BODY, G5_ROWS, G5_COLS = "'Lookup Tables'!$C$12:$G$16", "'Lookup Tables'!$B$12:$B$16", "'Lookup Tables'!$C$11:$G$11"
I2_BODY, I2_ROWS, I2_COLS = "'Lookup Tables'!$C$21:$G$25", "'Lookup Tables'!$B$21:$B$25", "'Lookup Tables'!$C$20:$G$20"
RESPONSE_RANGE = "'Lookup Tables'!$B$29:$B$33"


def build_sources_sheet(wb, sources):
    ws = wb.create_sheet("Threat Sources")
    write_title(ws, "Threat sources considered", "Taxonomy follows NIST SP 800-30 Rev 1, Appendix D. Characteristics apply to adversarial sources only.")
    header_row(ws, 4, ["Source ID", "Name", "Source Type", "Description", "Capability", "Intent", "Targeting", "Range of Effects"],
               widths=[10, 34, 14, 60, 12, 10, 11, 14])
    keys = ["source_id", "name", "source_type", "description", "capability", "intent", "targeting", "range_of_effects"]
    for r, source in enumerate(sources, start=5):
        for j, k in enumerate(keys):
            c = put(ws, f"{get_column_letter(1 + j)}{r}", source[k] or None)
            c.border = BORDER
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A5"


def build_register_sheet(wb, risks, sources):
    ws = wb.active
    ws.title = "Risk Register"
    write_title(ws, "Acme HR Portal: Risk Register",
                "FICTIONAL. Scored with NIST SP 800-30 Rev 1. Yellow cells are inputs; grey cells are formulas.")
    put(ws, "A3", "Assessment date: 2026-11-13   |   Version 1.0   |   Prepared by Sam Okafor, ISSO (fictional)", color="595959")
    header_row(ws, 4, [c[0] for c in COLUMNS], widths=[c[1] for c in COLUMNS])
    ws.row_dimensions[4].height = 45

    src_last = 4 + len(sources)
    src_names = f"'Threat Sources'!$B$5:$B${src_last}"
    src_types = f"'Threat Sources'!$C$5:$C${src_last}"
    c, i_, j_, k, l, m = (COL["Threat Source"], COL["Likelihood of Initiation / Occurrence"],
                          COL["Likelihood of Adverse Impact"], COL["Overall Likelihood (Table G-5)"],
                          COL["Impact"], COL["Risk Level (Table I-2)"])
    formulas = {
        "Source Type": lambda r: f'=IF({c}{r}="","",IFERROR(INDEX({src_types},MATCH({c}{r},{src_names},0)),""))',
        "Overall Likelihood (Table G-5)": lambda r: (
            f'=IF(OR({i_}{r}="",{j_}{r}=""),"",INDEX({G5_BODY},MATCH({i_}{r},{G5_ROWS},0),MATCH({j_}{r},{G5_COLS},0)))'),
        "Risk Level (Table I-2)": lambda r: (
            f'=IF(OR({k}{r}="",{l}{r}=""),"",INDEX({I2_BODY},MATCH({k}{r},{I2_ROWS},0),MATCH({l}{r},{I2_COLS},0)))'),
        "Risk Score (1-5)": lambda r: f'=IF({m}{r}="","",MATCH({m}{r},{LEVEL_RANGE},0))',
    }

    for i in range(CAPACITY):
        r = FIRST_ROW + i
        row = {}
        if i < len(risks):
            row = dict(risks[i].row, source_name=sources[risks[i].row["source_id"]]["name"],
                       related_controls=risks[i].row["related_controls"].replace(";", ", "))
        for j, (name, _, kind, key) in enumerate(COLUMNS):
            cell = put(ws, f"{get_column_letter(1 + j)}{r}", formulas[name](r) if kind == "formula" else row.get(key) or None,
                       color="0000FF" if kind == "input" else "000000")
            cell.border = BORDER
            cell.alignment = Alignment(wrap_text=True, vertical="top",
                                       horizontal="center" if kind != "text" or name in CENTERED_TEXT else None)
            if kind != "text":
                cell.fill = INPUT_FILL if kind == "input" else CALC_FILL

    dropdowns = [  # (list source, error title, error message, columns)
        (LEVEL_RANGE, "Invalid rating", "Pick Very Low, Low, Moderate, High or Very High.",
         ("Likelihood of Initiation / Occurrence", "Likelihood of Adverse Impact", "Impact")),
        (RESPONSE_RANGE, "Invalid response", "Pick Accept, Avoid, Mitigate, Share or Transfer.", ("Response",)),
        (src_names, "Unknown source", "Add the source on the Threat Sources sheet first.", ("Threat Source",)),
    ]
    for source, error_title, error, names in dropdowns:
        dv = DataValidation(type="list", formula1=source, allow_blank=True,
                            showErrorMessage=True, errorTitle=error_title, error=error)
        ws.add_data_validation(dv)
        for name in names:
            dv.add(span(name))

    for name in ("Overall Likelihood (Table G-5)", "Risk Level (Table I-2)"):
        add_level_formatting(ws, span(name))
    # Flag Moderate+ Mitigate risks that have no POA&M (methodology Section 6).
    poam, resp, score = COL["POA&M"], COL["Response"], COL["Risk Score (1-5)"]
    ws.conditional_formatting.add(
        span("POA&M"),
        FormulaRule(formula=[f'AND(${resp}{FIRST_ROW}="Mitigate",${poam}{FIRST_ROW}="",N(${score}{FIRST_ROW})>=3)'],
                    fill=PatternFill("solid", fgColor="FF0000")))

    ws.freeze_panes = f"C{FIRST_ROW}"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(COLUMNS))}{LAST_ROW}"
    fit_landscape(ws, pages_tall=0)
    ws.print_title_rows = "4:4"


def build_heatmap_sheet(wb):
    ws = wb.create_sheet("Heat Map")
    write_title(ws, "Risk heat map", "Each cell counts risks by overall likelihood and impact. Cell color is the Table I-2 risk level.")
    header_row(ws, 4, ["Overall likelihood ↓   /   Impact →", *LEVELS], first=2)
    like_rng, imp_rng = reg_range("Overall Likelihood (Table G-5)"), reg_range("Impact")
    for r, row_lvl in enumerate(reversed(LEVELS), start=5):   # Very High at the top
        header(ws, f"B{r}", row_lvl)
        for letter, level in zip(LEVEL_COLS, TABLE_I2[row_lvl]):
            c = shade(put(ws, f"{letter}{r}", f"=COUNTIFS({like_rng},$B{r},{imp_rng},{letter}$4)"), level, bold=True, size=14)
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = BORDER
            c.number_format = '0;-0;""'   # hide zeros so populated cells stand out
        ws.row_dimensions[r].height = 42
    put(ws, "B11", "Total plotted", bold=True)
    put(ws, "C11", "=SUM(C5:G9)", bold=True)

    put(ws, "B13", "Legend", bold=True)
    for r, lvl in enumerate(reversed(LEVELS), start=14):
        shade(put(ws, f"B{r}", lvl), lvl, bold=True)
    set_widths(ws, A=3, B=34, **dict.fromkeys(LEVEL_COLS, 14))
    fit_landscape(ws, pages_tall=1)


def build_summary_sheet(wb):
    ws = wb.create_sheet("Summary")
    write_title(ws, "Summary", "All figures are formulas over the Risk Register sheet.")
    level_rng, resp_rng = reg_range("Risk Level (Table I-2)"), reg_range("Response")
    id_rng, poam_rng, score_rng = reg_range("Risk ID"), reg_range("POA&M"), reg_range("Risk Score (1-5)")

    header_row(ws, 4, ["Risk level", "Count"], first=2)
    for r, lvl in enumerate(reversed(LEVELS), start=5):
        shade(put(ws, f"B{r}", lvl), lvl, bold=True)
        put(ws, f"C{r}", f"=COUNTIF({level_rng},B{r})")
    put(ws, "B10", "Total risks", bold=True)
    put(ws, "C10", f"=COUNTA({id_rng})", bold=True)

    header_row(ws, 4, ["Response", "Count"], first=5)
    for r, resp in enumerate(RESPONSES, start=5):
        put(ws, f"E{r}", resp)
        put(ws, f"F{r}", f"=COUNTIF({resp_rng},E{r})")

    header_row(ws, 13, ["Check", "Result"], first=2)
    checks = [
        ("Risks rated Moderate or higher", f'=COUNTIF({score_rng},">=3")'),
        ("Risks with a POA&M", f'=COUNTA({poam_rng})'),
        ("Moderate+ Mitigate risks missing a POA&M (should be 0)",
         f'=COUNTIFS({resp_rng},"Mitigate",{score_rng},">=3",{poam_rng},"")'),
        ("High+ risks marked Accept (should be 0)", f'=COUNTIFS({resp_rng},"Accept",{score_rng},">=4")'),
    ]
    for r, (label, formula) in enumerate(checks, start=14):
        put(ws, f"B{r}", label)
        put(ws, f"C{r}", formula, bold=True)
    for r in (16, 17):
        ws.conditional_formatting.add(f"C{r}", CellIsRule(operator="greaterThan", formula=["0"],
                                      fill=PatternFill("solid", fgColor="FF0000"), font=Font(name=FONT, color="FFFFFF", bold=True)))
    set_widths(ws, A=3, B=52, C=10, D=3, E=14, F=10)


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
    header_row(ws, 4, ["Level", "0-100 range", "0-10 value", "Likelihood of initiation / occurrence",
                       "Likelihood of adverse impact", "Impact"], widths=[12, 12, 10, 52, 36, 52])
    for r, lvl in enumerate(reversed(LEVELS), start=5):
        (lo, hi), ten = SEMI_QUANT[lvl]
        row = [lvl, f"{lo}-{hi}", ten, SCALE_TEXT["initiation"][lvl], SCALE_TEXT["adverse"][lvl], SCALE_TEXT["impact"][lvl]]
        for j, v in enumerate(row):
            c = put(ws, f"{get_column_letter(1 + j)}{r}", v)
            if j == 0:
                shade(c, lvl, bold=True)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = BORDER
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
    for r, (k, v) in enumerate(lines, start=4):
        put(ws, f"A{r}", k, bold=True)
        put(ws, f"B{r}", v).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 30
    put(ws, "A15", "Example input cell", bold=True)
    put(ws, "B15", "Moderate", color="0000FF").fill = INPUT_FILL
    put(ws, "A16", "Example formula cell", bold=True)
    put(ws, "B16", "Calculated by the workbook").fill = CALC_FILL
    set_widths(ws, A=26, B=100)


def build_workbook(register_csv: Path, sources_csv: Path, out: Path) -> Path:
    risks = load_register(register_csv, sources_csv)
    if len(risks) > CAPACITY:
        raise ValueError(f"register has {len(risks)} risks; the workbook holds {CAPACITY}")
    sources = load_threat_sources(sources_csv)

    wb = Workbook()
    build_lookup_sheet(wb)
    build_sources_sheet(wb, sources.values())
    build_register_sheet(wb, risks, sources)
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
