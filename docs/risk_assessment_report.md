# Risk Assessment Report: Acme HR Portal

> **FICTIONAL.** Acme Defense Fabrication, the Acme HR Portal, and every person, vendor, and
> finding here are invented for study. The structure follows NIST SP 800-30 Rev 1, Appendix K,
> in my own words.

| Field | Value |
|---|---|
| System | Acme HR Portal (AHR) |
| Categorization | `SC Acme HR Portal = {(confidentiality, MODERATE), (integrity, MODERATE), (availability, LOW)}` |
| Assessment tier | Tier 3 (information system) |
| Assessment date / version | 2026-11-13, v1.0 |
| Prepared by | Sam Okafor, ISSO |
| Reviewed by | Priya Natarajan, ISSM |
| Delivered to | Morgan Lee, CIO and Authorizing Official; Dana Ruiz, System Owner |
| Register | [`output/acme_hr_portal_risk_register.xlsx`](../output/acme_hr_portal_risk_register.xlsx) (source: [`data/risk_scenarios.csv`](../data/risk_scenarios.csv)) |

## Executive summary

We assessed 15 risk scenarios against the HR Portal, which holds pay, tax, and benefits data for
about 1,200 employees. **One risk is High, five are Moderate**, and the rest are Low or Very Low.
None is Very High.

The High risk is a **phishing attack on an HR specialist that leads to a bulk download of
employee records**. Push-based MFA lowers the odds but does not stop modern phishing kits that
relay the login. Requiring phishing-resistant MFA for the 15 HR accounts, plus an alert on large
exports, would bring this risk down to Moderate (POAM-0005).

Four of the five Moderate risks have a funded fix in the POA&M. The fifth, a breach at the
payroll provider, is **shared** with the vendor through contract terms, because Acme cannot fix
it directly.

All five findings from the October 2026 Security Assessment Report appear in this register. The
assessment confirms the AO's decision to authorize the system with conditions, and it adds three
new POA&M items (POAM-0005, -0006, -0007).

## 1. Purpose

Support the November annual security review in the ConMon plan by giving the AO a current,
ranked view of risk to the HR Portal. It also tells the system owner where to spend remediation
effort next.

## 2. Scope

| In scope | Out of scope |
|---|---|
| Everything inside the authorization boundary: load balancer, two app VMs, managed PostgreSQL, admin jump host, upload bucket | The Enterprise Identity Service and SOC platform themselves (assessed under their own authorizations) |
| The three interconnections: payroll provider, benefits carrier, identity service | Employee endpoints and home networks |
| Adversarial, accidental, structural, and environmental threat sources | Organization-wide (Tier 1 and Tier 2) risks |

## 3. Assumptions and constraints

- Inherited controls (IdP MFA, provider physical security) work as their own authorizations say.
- SAR results from the 2026-09-28 to 2026-10-09 assessment are still accurate, except for
  remediation recorded in the POA&M since then.
- Ratings are qualitative and rely on the ISSO's judgment, reviewed by the ISSM. No incident data
  specific to the portal exists yet because the system is new.
- Threat information comes from public reporting on HR and payroll-targeting campaigns and from
  Acme SOC trends. No classified or vendor-restricted intelligence was used.

## 4. Approach

See [`methodology.md`](methodology.md). In short: nine threat sources, 15 threat events, two-part
likelihood combined with Table G-5, impact anchored to the FIPS 199 categorization, and risk from
Table I-2.

## 5. Results

### Risk levels

| Risk level | Count |
|---|---|
| Very High | 0 |
| High | 1 |
| Moderate | 5 |
| Low | 8 |
| Very Low | 1 |
| **Total** | **15** |

### Heat map (count of risks)

| Likelihood ↓ / Impact → | Very Low | Low | Moderate | High | Very High |
|---|---|---|---|---|---|
| **Very High** | | | | | |
| **High** | | | | 1 | |
| **Moderate** | | 4 | 2 | 3 | |
| **Low** | | | 4 | | |
| **Very Low** | | 1 | | | |

### Risks rated Moderate or higher

| Rank | ID | Risk | Likelihood | Impact | Risk | Response | POA&M |
|---|---|---|---|---|---|---|---|
| 1 | R-01 | Phished HR account used to bulk-download employee PII | High | High | **High** | Mitigate | POAM-0005 |
| 2 | R-02 | Known flaw in an application dependency exploited from the internet | Moderate | High | Moderate | Mitigate | POAM-0002 |
| 3 | R-06 | Breach at the payroll provider exposes Acme pay statements | Moderate | High | Moderate | Share | — |
| 4 | R-08 | Document upload bucket accidentally made public | Moderate | High | Moderate | Mitigate | POAM-0006 |
| 5 | R-03 | Dormant account used to sign in after the owner left | Moderate | Moderate | Moderate | Mitigate | POAM-0001 |
| 6 | R-04 | HR staff member browses or takes coworkers' records | Moderate | Moderate | Moderate | Mitigate | POAM-0007 |

The full register, including the eight Low and one Very Low risk, is in the workbook and the CSV.

### Traceability to the SAR

| SAR finding | Control | Risk | Risk level |
|---|---|---|---|
| AHR-2026-001 | AC-2(3) | R-03 | Moderate |
| AHR-2026-002 | SI-2 | R-02 | Moderate |
| AHR-2026-003 | CP-4 | R-07 | Low |
| AHR-2026-004 | AU-6 | R-05 | Low |
| AHR-2026-005 | CM-6 | R-09 | Low (accepted; corrected during the assessment) |

## 6. Recommendations

1. **Phishing-resistant MFA for HR roles (R-01).** Ask the identity team to require FIDO2
   security keys for the 12 HR specialists and 3 HR administrators. Estimated cost: about $750 in
   keys and two days of identity-team time. This is the most risk reduction per dollar in the
   register.
2. **Bulk-export alert (R-01, R-04).** One SOC correlation rule covers both the external-attacker
   and insider versions of the same harm.
3. **Tenant-level public access block (R-08).** A one-time setting that removes a whole class of
   mistakes.
4. **Finish the SAR POA&M items on schedule (R-02, R-03).** They are already funded and in progress.
5. **Vendor assurance (R-06).** Get Bayline's current SOC 2 Type II report and add a 72-hour
   breach-notification clause at the next renewal.

## 7. Combined scenario worth watching

R-01 (phished account) and R-05 (log review gaps) make each other worse. If an attacker exports
records slowly enough to stay under SOC thresholds, the weekly portal log review is the main
backstop, and it was recorded for only 5 of 12 weeks. POAM-0004 and the export alert in
POAM-0005 close this gap together.

## 8. Next update

At the next annual security review (November 2027), or sooner if a trigger in methodology
Section 7 occurs. The ISSO re-scores a risk whenever its POA&M item closes.

| Prepared by | Reviewed by | Date |
|---|---|---|
| /s/ Sam Okafor, ISSO (fictional) | /s/ Priya Natarajan, ISSM (fictional) | 2026-11-13 |
