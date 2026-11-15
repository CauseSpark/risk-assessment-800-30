# Methodology

How the Acme HR Portal risk assessment was built, step by step, and where each step comes
from in NIST SP 800-30 Rev 1. Section and table numbers point to the publication; the wording
here is my own summary.

## 1. Where this fits

| Framework piece | How this repo uses it |
|---|---|
| SP 800-39 risk tiers | This is a **Tier 3 (information system)** assessment of one system |
| SP 800-37 Rev 2 (RMF) | Supports RA-3 and the Monitor step: the [ConMon plan](https://github.com/CauseSpark/rmf-ato-package-templates/blob/main/examples/acme-hr-portal/conmon_plan.md) calls for an annual security review each November |
| SP 800-53 Rev 5 | RA-3 (Risk Assessment) is the control this satisfies; every risk lists the controls that reduce it |
| SP 800-30 Rev 1 | The process (Chapter 3) and the scoring tables (Appendices D, G, H, I) |

## 2. The four steps, mapped to the repo

| SP 800-30 step | Task | Where it is in this repo |
|---|---|---|
| 1. Prepare | Purpose, scope, assumptions, information sources, risk model | `docs/risk_assessment_report.md` Sections 1–3 |
| 2. Conduct | 2-1 Identify threat sources | `data/threat_sources.csv` |
| | 2-2 Identify threat events | `threat_event` column |
| | 2-3 Identify vulnerabilities and predisposing conditions | `vulnerability` column |
| | 2-4 Determine likelihood | `likelihood_initiation`, `likelihood_adverse_impact`, Table G-5 |
| | 2-5 Determine impact | `impact`, `impact_rationale` |
| | 2-6 Determine risk | Table I-2 in `src/risk_model.py` and the workbook |
| 3. Communicate | Share results with decision makers | The report, the Excel register, and the [briefings repo](https://github.com/CauseSpark/security-risk-briefings) |
| 4. Maintain | Monitor risk factors and update | Section 7 below |

## 3. Threat sources (Task 2-1)

SP 800-30 sorts threat sources into four types: **adversarial, accidental, structural, and
environmental** (Appendix D). For adversarial sources I rated capability, intent, and targeting
(the Appendix D characteristics) to support the initiation rating. For the other three types
I rated the range of effects.

Nine sources were in scope. Insider and former-workforce sources are included because the
portal holds coworkers' pay and personal data.

## 4. Likelihood (Task 2-4)

Likelihood has two parts, rated separately and then combined with **Table G-5**:

1. **Likelihood of initiation or occurrence.** For adversarial events: how likely the source is
   to try, given capability, intent, and targeting (Table G-2). For other events: how often it
   happens (Table G-3).
2. **Likelihood of adverse impact.** If it happens, how likely it is to cause harm, given the
   vulnerability and existing controls (Table G-4).

Example: phishing of HR staff is attempted constantly (**Very High** initiation), and push MFA
stops most but not all attempts (**Moderate** adverse impact). Table G-5 gives **High** overall.

## 5. Impact and risk (Tasks 2-5 and 2-6)

Impact is rated on the Appendix H scale and anchored to the system's FIPS 199 categorization
(confidentiality **Moderate**, integrity **Moderate**, availability **Low**). A confidentiality
event that exposes all employees' SSNs is rated **High**, above the categorization, because
breach notification and credit monitoring costs make it severe for the organization.
Availability-only events are capped at **Low** to match the categorization.

**Table I-2** combines overall likelihood and impact into the risk level. The qualitative scale
is used throughout. The 0-100 and 0-10 semi-quantitative values are recorded on the workbook's
Scales sheet so the register can move to a numeric model later.

Ties are broken in this order: risk level, then impact, then likelihood, then risk ID.

## 6. Risk response rules (organization-defined)

Responses use the five options in SP 800-39 Section 3.3: **accept, avoid, mitigate, share, or
transfer**. Acme's (fictional) risk tolerance, set by the AO, adds two rules that the code and the
workbook both enforce:

1. A **Moderate or higher** risk with a **Mitigate** response must have a POA&M item.
2. A **High or Very High** risk cannot be accepted at the system level. Only the AO can accept it,
   in writing.

Low risks marked Mitigate are tracked as normal work tickets rather than POA&M items.

## 7. Maintaining the assessment (Step 4)

Re-score a risk, and update the register, when any of these happens:

- A POA&M item closes (the matching risk's adverse-impact likelihood should drop)
- The annual security review (each November)
- A significant change to the system, such as a new interconnection or a move to another hosting region
- A security incident involving the portal
- New threat intelligence about HR or payroll-targeting campaigns

## 8. Limits of this method

- Qualitative ratings depend on the assessor's judgment. Each rating has a written rationale so a
  reviewer can challenge it.
- Table I-2 is coarse: High and Very High likelihood produce the same risk level, and most
  scenarios land in Moderate or Low. Ranking ties by impact then likelihood keeps the list usable.
- Risks are scored one at a time. Combined scenarios, such as phishing followed by an unreviewed
  bulk export, are noted in the report but not scored separately.

## Official sources

- [NIST SP 800-30 Rev 1, Guide for Conducting Risk Assessments](https://csrc.nist.gov/pubs/sp/800/30/r1/final) (September 2012)
- [NIST SP 800-39, Managing Information Security Risk](https://csrc.nist.gov/pubs/sp/800/39/final)
- [NIST SP 800-37 Rev 2, Risk Management Framework](https://csrc.nist.gov/pubs/sp/800/37/r2/final)
- [NIST SP 800-53 Rev 5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)
