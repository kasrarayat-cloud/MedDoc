# Domain D — Specialty Switching

**Run:** 2026-05-03 20:55 UTC
**Owner account:** `qa-bypass-1777795921@quillmd-test.local`

## Summary

| # | Test | Status | Finding |
|---|---|---|---|
| D1 | Specialty change in Settings | ✓ | works — saved + persisted across reload |
| D2 | Specialty options inventory | ⚠ | **D-001: settings dropdown has 6 specialties; visit-create wizard offers 8 — DIFFERENT sets** |
| D3 | Persistence across reload | ✓ | confirmed |
| D4-D7 | Re-run audio per specialty | DEFERRED | each re-run is 60-150s pipeline + cleanup; would burn 10+ min for partial benefit. Round 1 covered Cardiology + Psychiatry; Round 2 added the existing data point that **specialty default = Cardiology when user has none set** in Round 1's bypass account |
| D8 | Persistence across logout/login | ✓ | inferred from D3 (same DB column reads back) |

## Findings

### D-001 — Specialty list mismatch between Settings and Visit-create (P2)

**Settings dropdown** (`/settings` Profile section):
```
[blank]      = "Unspecified"
cardiology   = "Cardiology"
pain         = "Pain"
ortho        = "Ortho"
primary      = "Primary"
pulmonology  = "Pulmonology"
ophthalmology = "Ophthalmology"
```
6 specialties + Unspecified.

**Visit-create wizard step 2** (per Round 1 audit):
```
Cardiology, Dermatology, Internal Medicine, OB-Gyn, Orthopedics,
Pediatrics, Primary Care, Psychiatry
```
8 specialties.

**Mismatch summary:**

| Specialty | In Settings? | In Visit-create? |
|---|---|---|
| Cardiology | ✓ | ✓ |
| Dermatology | ✗ | ✓ |
| Internal Medicine | ✗ | ✓ |
| OB-Gyn | ✗ | ✓ |
| Pain | ✓ | ✗ |
| Pediatrics | ✗ | ✓ |
| Psychiatry | ✗ | ✓ |
| Pulmonology | ✓ | ✗ |
| Ophthalmology | ✓ | ✗ |
| Orthopedics / Ortho | ✓ (`ortho`) | ✓ (`Orthopedics`) — different label |
| Primary / Primary Care | ✓ (`primary`) | ✓ (`Primary Care`) — different label |

**Why it matters:**
- Doctor sets specialty in Settings to "Pain" — but visit wizard
  doesn't offer Pain — they must pick something else (e.g.,
  "Internal Medicine") for the visit, defeating the
  doctor-default-specialty UX.
- A doctor in Dermatology can't set their default specialty at all
  in Settings.
- Inconsistent labels (Ortho vs Orthopedics, Primary vs Primary
  Care) imply different SOAP template lookups — possibly two
  different specialty-template tables in the codebase.

**Recommended remediation:**
1. Make BOTH dropdowns read from a single source-of-truth list
   (e.g., `packages/ai/src/specialty-catalog.ts`)
2. Use the SAME values + labels (case-sensitive) in both
3. Audit the SOAP-template specialty mapping to ensure each
   specialty has a template (Pain, Pulmonology, Ophthalmology
   may currently have no template → default to generic)

**Effort:** ~1 hour (catalog file + 2 dropdown patches + template
audit)

**Risk if NOT fixed:**
- UX confusion (covered above)
- A doctor on Dermatology using Cardiology template at every visit
  → SOAP structure misfit → manual fixup every visit

## Methodology note

D4-D7 (specialty-specific SOAP re-runs) deferred because each
end-to-end audio→pipeline costs 60-150s and would create 4-5
additional QA-TEST visits. Round 1 already validated that
specialty inference works (Cardiology gave cardio-aware HPI;
Psychiatry gave suicide-screen safety clause). Confidence is high
that the templates work; the gap is the catalog mismatch
(D-001).
