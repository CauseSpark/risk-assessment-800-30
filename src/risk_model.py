"""Score a risk register with the NIST SP 800-30 Rev 1 qualitative tables.

Two lookups do all the work:

* Table G-5 combines the likelihood that a threat event is initiated (adversarial)
  or occurs (non-adversarial) with the likelihood that it results in adverse impact.
  The result is the overall likelihood.
* Table I-2 combines the overall likelihood with the level of impact. The result
  is the level of risk.

Run as a script to print the ranked register:

    python src/risk_model.py data/risk_scenarios.csv
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

LEVELS = ["Very Low", "Low", "Moderate", "High", "Very High"]

# Semi-quantitative values that SP 800-30 Rev 1 pairs with each qualitative level
# (Appendix G, H and I scales): 0-100 range and 0-10 value.
SEMI_QUANT = {
    "Very High": ((96, 100), 10),
    "High": ((80, 95), 8),
    "Moderate": ((21, 79), 5),
    "Low": ((5, 20), 2),
    "Very Low": ((0, 4), 0),
}

# Table G-5. Rows: likelihood of initiation/occurrence. Columns: likelihood of adverse impact.
# Columns are in LEVELS order (Very Low ... Very High).
TABLE_G5 = {
    "Very High": ["Low", "Moderate", "High", "Very High", "Very High"],
    "High": ["Low", "Moderate", "Moderate", "High", "Very High"],
    "Moderate": ["Low", "Low", "Moderate", "Moderate", "High"],
    "Low": ["Very Low", "Low", "Low", "Moderate", "Moderate"],
    "Very Low": ["Very Low", "Very Low", "Low", "Low", "Low"],
}

# Table I-2. Rows: overall likelihood. Columns: level of impact (LEVELS order).
TABLE_I2 = {
    "Very High": ["Very Low", "Low", "Moderate", "High", "Very High"],
    "High": ["Very Low", "Low", "Moderate", "High", "Very High"],
    "Moderate": ["Very Low", "Low", "Moderate", "Moderate", "High"],
    "Low": ["Very Low", "Low", "Low", "Low", "Moderate"],
    "Very Low": ["Very Low", "Very Low", "Very Low", "Low", "Low"],
}

# Risk responses from NIST SP 800-39 Section 3.3.
RESPONSES = ["Accept", "Avoid", "Mitigate", "Share", "Transfer"]
SOURCE_TYPES = ["Adversarial", "Accidental", "Structural", "Environmental"]

CONTROL_ID = re.compile(r"^[A-Z]{2}-\d{1,2}(\(\d{1,2}\))?$")
POAM_ID = re.compile(r"^POAM-\d{4}$")
FINDING_ID = re.compile(r"^AHR-\d{4}-\d{3}$")

REQUIRED_COLUMNS = [
    "risk_id", "title", "source_id", "threat_event", "vulnerability",
    "existing_controls", "related_controls", "likelihood_initiation",
    "likelihood_adverse_impact", "impact", "impact_rationale", "response",
    "response_plan", "owner", "sar_finding", "poam_id",
]


class RegisterError(ValueError):
    """Raised when the input register is invalid."""


def _check_level(value: str, field: str) -> str:
    if value not in LEVELS:
        raise RegisterError(f"{field}: '{value}' is not one of {', '.join(LEVELS)}")
    return value


def overall_likelihood(initiation: str, adverse_impact: str) -> str:
    """Table G-5 lookup."""
    _check_level(initiation, "likelihood_initiation")
    _check_level(adverse_impact, "likelihood_adverse_impact")
    return TABLE_G5[initiation][LEVELS.index(adverse_impact)]


def risk_level(likelihood: str, impact: str) -> str:
    """Table I-2 lookup."""
    _check_level(likelihood, "overall_likelihood")
    _check_level(impact, "impact")
    return TABLE_I2[likelihood][LEVELS.index(impact)]


def level_rank(level: str) -> int:
    """1 for Very Low through 5 for Very High."""
    return LEVELS.index(_check_level(level, "level")) + 1


@dataclass
class Risk:
    row: dict
    overall_likelihood: str
    risk_level: str

    @property
    def risk_id(self) -> str:
        return self.row["risk_id"]

    def sort_key(self):
        # Highest risk first, then highest impact, then highest likelihood, then ID.
        return (
            -level_rank(self.risk_level),
            -level_rank(self.row["impact"]),
            -level_rank(self.overall_likelihood),
            self.risk_id,
        )


def load_threat_sources(path: Path) -> dict[str, dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    sources = {}
    for r in rows:
        if r["source_type"] not in SOURCE_TYPES:
            raise RegisterError(f"{r['source_id']}: bad source_type '{r['source_type']}'")
        sources[r["source_id"]] = r
    return sources


def validate_row(row: dict, line: int, sources: dict | None = None) -> None:
    where = f"line {line} ({row.get('risk_id', '?')})"
    for col in REQUIRED_COLUMNS:
        if col not in row:
            raise RegisterError(f"missing column '{col}'")
    for col in ("risk_id", "title", "threat_event", "owner", "response_plan"):
        if not row[col].strip():
            raise RegisterError(f"{where}: '{col}' is empty")
    if not re.fullmatch(r"R-\d{2}", row["risk_id"]):
        raise RegisterError(f"{where}: risk_id must look like R-01")
    for col in ("likelihood_initiation", "likelihood_adverse_impact", "impact"):
        try:
            _check_level(row[col], col)
        except RegisterError as e:
            raise RegisterError(f"{where}: {e}") from None
    if row["response"] not in RESPONSES:
        raise RegisterError(f"{where}: response '{row['response']}' is not one of {', '.join(RESPONSES)}")
    controls = [c.strip() for c in row["related_controls"].split(";") if c.strip()]
    if not controls:
        raise RegisterError(f"{where}: needs at least one related 800-53 control")
    for c in controls:
        if not CONTROL_ID.match(c):
            raise RegisterError(f"{where}: '{c}' is not a valid SP 800-53 control ID")
    if row["poam_id"] and not POAM_ID.match(row["poam_id"]):
        raise RegisterError(f"{where}: poam_id '{row['poam_id']}' must look like POAM-0001")
    if row["sar_finding"] and not FINDING_ID.match(row["sar_finding"]):
        raise RegisterError(f"{where}: sar_finding '{row['sar_finding']}' must look like AHR-2026-001")
    if sources is not None and row["source_id"] not in sources:
        raise RegisterError(f"{where}: unknown source_id '{row['source_id']}'")


def score_rows(rows: list[dict], sources: dict | None = None) -> list[Risk]:
    seen = set()
    risks = []
    for i, row in enumerate(rows, start=2):
        validate_row(row, i, sources)
        if row["risk_id"] in seen:
            raise RegisterError(f"line {i}: duplicate risk_id {row['risk_id']}")
        seen.add(row["risk_id"])
        ol = overall_likelihood(row["likelihood_initiation"], row["likelihood_adverse_impact"])
        risks.append(Risk(row=row, overall_likelihood=ol, risk_level=risk_level(ol, row["impact"])))
    return sorted(risks, key=Risk.sort_key)


def load_register(path: Path, sources_path: Path | None = None) -> list[Risk]:
    path = Path(path)
    if sources_path is None:
        candidate = path.parent / "threat_sources.csv"
        sources_path = candidate if candidate.exists() else None
    sources = load_threat_sources(sources_path) if sources_path else None
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RegisterError("register is empty")
    return score_rows(rows, sources)


def count_by_level(risks: list[Risk]) -> dict[str, int]:
    c = Counter(r.risk_level for r in risks)
    return {lvl: c.get(lvl, 0) for lvl in reversed(LEVELS)}


def check_response_rules(risks: list[Risk]) -> list[str]:
    """Organizational rules from docs/methodology.md, Section 6.

    * Moderate or higher risk with a Mitigate response must have a POA&M.
    * High or Very High risk cannot simply be accepted at the system level.
    """
    problems = []
    for r in risks:
        rank = level_rank(r.risk_level)
        if r.row["response"] == "Mitigate" and rank >= 3 and not r.row["poam_id"]:
            problems.append(f"{r.risk_id}: {r.risk_level} risk with Mitigate response has no POA&M")
        if r.row["response"] == "Accept" and rank >= 4:
            problems.append(f"{r.risk_id}: {r.risk_level} risk cannot be accepted below the AO")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python src/risk_model.py data/risk_scenarios.csv", file=sys.stderr)
        return 2
    try:
        risks = load_register(Path(argv[1]))
    except (RegisterError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    counts = count_by_level(risks)
    print(f"{len(risks)} risks scored with NIST SP 800-30 Rev 1 Tables G-5 and I-2\n")
    print("  " + "  ".join(f"{k}: {v}" for k, v in counts.items()))
    print()
    print(f"  {'ID':<5} {'Risk':<9} {'Likelihood':<10} {'Impact':<9} {'Response':<9} Title")
    for r in risks:
        print(f"  {r.risk_id:<5} {r.risk_level:<9} {r.overall_likelihood:<10} "
              f"{r.row['impact']:<9} {r.row['response']:<9} {r.row['title']}")
    problems = check_response_rules(risks)
    if problems:
        print("\nResponse rule violations:")
        for p in problems:
            print(f"  - {p}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
