# Sample visit fixtures — spec for agent walks

The agent's first PASS B run (2026-05-06,
[`docs/qa-reports/20260506T005713Z.md`](../../../../docs/qa-reports/20260506T005713Z.md))
inserted a synthetic visit with a 122-character SOAP. That worked for
testing the override + sign-modal flows but **didn't exercise**:

- Bump CTA / bump modal / apply-additions flow (engine produced
  `bumpableTo: null` for the short SOAP).
- Section pulse hints / sage edge-glow on bump (no `sectionPulseHints`
  populated without bump gaps).
- Rx-warning **override** + sign-block flow (fixture lacked a
  `severity: "critical"` warning; only critical severity blocks signing
  per `apps/transcribe-md/src/app/visits/[id]/rx-tab.tsx:445`).

This file documents the visit shapes the agent **needs** for richer
sweeps. Fixtures themselves are not committed (per the agent's
read-only-DB rule) — they're inserted at run-time by walker setup
helpers + dropped at teardown.

## Fixture A — bump-eligible visit

**Goal:** SOAP rich enough to score 99213 with a `bumpableTo: 99214`
+ at least one gap criterion. Exercises:

- Bump CTA renders with the gap-count subtitle ("close 2 gaps · 30
  sec").
- Section pulse hints populate (Subjective + Plan if MDM gap is
  the lifter).
- Bump CTA click → `onHighlightCriteria(['hpi.elements'])` → soap-
  editor flips the sage edge-glow class on Subjective for ~2.5s.
- Bump modal opens; doctor edits the per-gap suggestions; "Apply &
  save" → POST `/em-score/apply-additions` → 200 + new tier + audit
  row `EM_BUMP_APPLIED`.

**Required SOAP shape** (rough — the engine recomputes; the fixture
needs to *look* like a real 99213):

- HPI: 4 elements (location, quality, duration, timing) named
  explicitly so the engine counts them.
- ROS: 2 systems noted (constitutional + the system relevant to the
  CC).
- PFSH: 1 category (PMH listed).
- Exam: 2 systems with findings (cardiac + respiratory if no contra-
  indication).
- MDM: 2 problems but BOTH at "low" complexity, plus moderate data
  review (e.g. "reviewed CBC + BMP from last week"), risk: low.
  → Engine produces 99213 + `bumpableTo: 99214` because adding 1 more
  problem-complexity step or 1 more risk element bridges the gap.

**Required ICD codes:** at least one — e.g. J06.9 (URI), I10
(hypertension). Both readily testable.

## Fixture B — Rx critical-warning visit

**Goal:** Rx draft with at least one `severity: "critical"` warning
that BLOCKS signing until overridden (Phase-E behavior — see
`tests/api/rx-warning-override.test.ts` if it exists; otherwise
audit `RX_OVERRIDE_RECORDED` + `RX_SIGN_BLOCKED_NO_OVERRIDE`).

**rxDrafts JSON shape:**

```json
{
  "warnings": [
    {
      "rx_drug": "Ibuprofen",
      "severity": "critical",
      "message": "Concurrent warfarin per PMH — major bleeding risk; document override before signing.",
      "evidence_quote": "PMH includes warfarin therapy"
    }
  ],
  "prescriptions": [
    { "drug": "Ibuprofen", "sig": "200mg q6h", "action": "new" }
  ]
}
```

**Walker assertions:**

- Rx tab renders the warning with a "BLOCKING" / "CRITICAL" pill (not
  "SERIOUS" — that's the major-severity rendering).
- Override button is visible on the warning row.
- Click override → opens the override-reason form.
- Submit reason → POST → `rx_warning_overrides` table gets a row +
  `RX_OVERRIDE_RECORDED` audit row fires.
- Sign attempt BEFORE override → POST `/sign` returns
  `RX_SIGN_BLOCKED_NO_OVERRIDE`-shape error.
- Sign attempt AFTER override → 200; visit signed.

## Fixture C — pediatric visit (Rx mg/kg validation)

**Goal:** patient with `dateOfBirth` < 18 years before the visit
date; an Rx draft with a weight-based dose. Exercises
`validateRxDose` mg/kg paths (pediatric patients have
weight-based dosing rules the AI pipeline applies).

**Patient shape:**

- Same `transcribe_md_patients` row but with
  `dateOfBirth: '2018-01-01'` (so the patient is ~8 yrs old at the
  visit date).

**rxDrafts JSON shape:**

```json
{
  "warnings": [
    {
      "rx_drug": "Amoxicillin",
      "severity": "major",
      "message": "Pediatric patient — verify mg/kg dose is appropriate for stated weight.",
      "evidence_quote": "Patient is 8 yrs old"
    }
  ],
  "prescriptions": [
    { "drug": "Amoxicillin", "sig": "250mg PO BID x 7d", "action": "new" }
  ]
}
```

**Walker assertions:**

- Rx tab shows the pediatric-warning pill (the agent confirms
  `severity: "major"` renders as "SERIOUS" not "CRITICAL").
- Sign is NOT blocked for major-severity (only critical blocks).

## Fixture D — non-clinical input refusal

**Goal:** rawTextInput is non-clinical text (e.g. a meeting agenda or
witness statement). The L5 critique pass refuses + L6 polish writes
a refusal banner instead of canonical S/O/A/P. Exercises Pattern C
parser/renderer mismatch detection.

**Visit shape:**

- `rawTextInput`: 1-2 paragraphs of non-medical content.
- `soapDraft` / `soapFinal`: a refusal banner like:

  ```
  ## Abstraction of Third-Party Medico-Legal / Witness Statement

  > This input was identified by the clinical-intake review as a
  > non-clinical document and was not written into a SOAP note.
  > See `docs/critique-policy.md` §3.
  ```

**Walker assertions:**

- The visit-ready page renders the refusal banner verbatim — NOT 4
  empty-state "[Section] is empty" messages. (That was the original
  Bug C from PR #131 / the Kasra smoke test.)
- The agent confirms the parser handled the non-canonical heading
  correctly per the post-fix `parseSoapSections`.

---

## How to insert / drop these fixtures

For now, walkers that need a richer fixture insert one inline via
`docker exec ... psql ...` in their setup block (mirror the inline
`INSERT INTO transcribe_visits` the first PASS B walk used) +
DELETE in their teardown. **Audit rows are append-only per HIPAA
design** — never truncate `audit_logs`.

A future iteration can centralise this into `scripts/lib/fixtures.mjs`
exposing `insertBumpEligibleVisit()`, `insertCriticalRxVisit()`, etc.
That's `v3` work; for `v2` each walker that needs a fixture can paste
the SQL inline so it's obvious what the walker exercises.

## Rules

- NEVER seed real PHI. Synthetic patient names + DOBs only.
- NEVER use OpenAI/Anthropic API keys to generate the SOAP — use the
  literal markdown templates above (the agent's job is to test the
  UI, not the pipeline).
- NEVER skip the cleanup step. Every fixture visit dropped at the
  end of the walk + audit rows preserved.
