# risk-assessment-800-30

[![tests](https://github.com/CauseSpark/risk-assessment-800-30/actions/workflows/tests.yml/badge.svg)](https://github.com/CauseSpark/risk-assessment-800-30/actions/workflows/tests.yml)

A system-level risk assessment done the **NIST SP 800-30 Rev 1** way: threat sources, threat
events, two-part likelihood, impact, and risk level. It produces a tested Python scoring model,
a **live Excel risk register with a heat map**, and a written risk assessment report.

The system is the fictional **Acme HR Portal** from my
[rmf-ato-package-templates](https://github.com/CauseSpark/rmf-ato-package-templates) repo, so
every finding from that package's Security Assessment Report shows up here as a scored risk.

> **Personal study material.** This is not official guidance from NIST or any agency, and it
> is not endorsed by them. Acme Defense Fabrication, the HR Portal, and every person, vendor,
> and finding are fictional. No real system data, CUI, or classified information is included.

## Purpose

Security teams find a lot of problems. Leadership has a limited budget and needs to know which
problems matter most. A risk assessment answers that question. I built this repo to practice the
whole workflow:

1. **Identify** what could go wrong: who or what causes it, how, and through which weakness
2. **Score** it consistently with the SP 800-30 tables instead of gut feel
3. **Rank** the results and pick a response for each one: accept, avoid, mitigate, share, or transfer
4. **Report** it in a form a system owner and an authorizing official can act on

## Versions referenced (checked November 2026)

| Source | Version | Used for |
|---|---|---|
| [NIST SP 800-30](https://csrc.nist.gov/pubs/sp/800/30/r1/final) | Rev 1, September 2012 (current) | Process, threat taxonomy, Tables G-5 and I-2 |
| [NIST SP 800-39](https://csrc.nist.gov/pubs/sp/800/39/final) | March 2011 | Risk tiers and the five risk responses |
| [NIST SP 800-53](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final) | Rev 5 | Related controls for each risk (RA-3 is the control this satisfies) |

## Quick start

```bash
git clone https://github.com/CauseSpark/risk-assessment-800-30.git
cd risk-assessment-800-30
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Score and rank the register
python src/risk_model.py data/risk_scenarios.csv

# Rebuild the Excel register from the CSV
python src/build_register.py

# Run the tests
pytest
```

Sample output:

```
15 risks scored with NIST SP 800-30 Rev 1 Tables G-5 and I-2

  Very High: 0  High: 1  Moderate: 5  Low: 8  Very Low: 1

  ID    Risk      Likelihood Impact    Response  Title
  R-01  High      High       High      Mitigate  Phished HR account used to bulk-download employee PII
  R-02  Moderate  Moderate   High      Mitigate  Known flaw in an application dependency exploited from the internet
  R-06  Moderate  Moderate   High      Share     Breach at the payroll provider exposes Acme pay statements
  R-08  Moderate  Moderate   High      Mitigate  Document upload bucket accidentally made public
  ...
```

The command exits with code 1 if a risk breaks a response rule, such as a High risk marked
Accept or a Moderate risk to be mitigated with no POA&M.

## The Excel risk register

[`output/acme_hr_portal_risk_register.xlsx`](output/acme_hr_portal_risk_register.xlsx) has seven sheets:

| Sheet | What it does |
|---|---|
| Instructions | Legend for input cells and formula cells, and how to add a risk |
| Risk Register | 15 scored risks plus 35 empty pre-formatted rows. Ratings are dropdowns, and overall likelihood and risk level are `INDEX/MATCH` formulas against the SP 800-30 tables |
| Heat Map | 5×5 `COUNTIFS` grid colored by Table I-2, so it redraws when a rating changes |
| Summary | Counts by risk level and response, plus two rule checks that turn red if they're not 0 |
| Threat Sources | The nine sources, with capability, intent, and targeting for adversarial ones |
| Scales | Plain-language versions of the SP 800-30 scales, with the 0–100 and 0–10 values |
| Lookup Tables | Tables G-5 and I-2, used by the formulas |

The workbook doesn't hard-code any scores. Change a likelihood rating in Excel and the risk level,
heat map, and summary update on their own. A test recalculates the workbook in LibreOffice and
checks that every formula result matches the Python model.

## What's in the repo

| Path | What it is |
|---|---|
| `data/risk_scenarios.csv` | The 15 risk scenarios: source, event, vulnerability, existing controls, ratings, rationale, response, owner, SAR finding, POA&M |
| `data/threat_sources.csv` | Nine threat sources across all four SP 800-30 types |
| `src/risk_model.py` | Tables G-5 and I-2, input validation, ranking, response rules, CLI |
| `src/build_register.py` | Builds the Excel workbook with formulas, dropdowns, and conditional formatting |
| `docs/risk_assessment_report.md` | The written report for the AO: executive summary, scope, results, recommendations |
| `docs/methodology.md` | How each SP 800-30 step and task maps to this repo, and the response rules |
| `output/` | The generated workbook |
| `tests/` | 52 pytest cases: every table cell rule, validation, the Acme results, the workbook, and report consistency |

## Results at a glance

| Rank | Risk | Level | Response |
|---|---|---|---|
| 1 | Phished HR account used to bulk-download employee PII | **High** | Mitigate: phishing-resistant MFA for HR roles and an export alert (POAM-0005) |
| 2 | Known flaw in an application dependency exploited from the internet | Moderate | Mitigate (POAM-0002) |
| 3 | Breach at the payroll provider exposes Acme pay statements | Moderate | Share: SOC 2 report review and contract terms |
| 4 | Document upload bucket accidentally made public | Moderate | Mitigate (POAM-0006) |
| 5 | Dormant account used to sign in after the owner left | Moderate | Mitigate (POAM-0001) |
| 6 | HR staff member browses or takes coworkers' records | Moderate | Mitigate (POAM-0007) |

## What this demonstrates

- **Risk assessment method:** two-part likelihood (initiation, then adverse impact), impact tied to
  the FIPS 199 categorization, and a written rationale for every rating
- **Excel skills:** lookup formulas, data validation, conditional formatting, a formula-driven
  heat map, and rule checks, built from code so they can be reproduced
- **Traceability:** every SAR finding maps to a risk, and every Moderate or higher risk to be
  mitigated has a POA&M item, which a test checks
- **Communication:** the report leads with what the AO needs to decide and what it costs

## Related repos

This is part 1 of a four-repo series on the same fictional system:

1. **risk-assessment-800-30** (this repo): what could go wrong and how bad it is
2. [control-audit-evidence-kit](https://github.com/CauseSpark/control-audit-evidence-kit): how the controls were tested and what evidence backs each result
3. [policy-and-poam-program](https://github.com/CauseSpark/policy-and-poam-program): the policies and the POA&M tracker that drives the fixes
4. [security-risk-briefings](https://github.com/CauseSpark/security-risk-briefings): how it's explained to leadership

## Disclaimer

This repository is personal study material created for learning and portfolio purposes:

- It is **not** affiliated with or endorsed by NIST, the DoD, or any employer or client.
- It does **not** represent an official risk assessment, an authorization, or legal or compliance advice.
- All names, systems, vendors, costs, and findings are fictional.

Scale descriptions are my own short paraphrases. Use the official publication for the
authoritative text.

## License

[MIT](LICENSE) © 2026 Peyton Seay
