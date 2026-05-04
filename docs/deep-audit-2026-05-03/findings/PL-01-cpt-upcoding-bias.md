# PL-01 — Slight CPT upcoding bias (single observation)

**Severity:** P2
**Domain:** AI pipeline (Layer 7b — CPT/E/M coding)
**File:** `apps/transcribe-md/src/worker/layers/07b-cpt-coding.ts` (prompt)

## What

In a controlled run of Scenario A (Cardiology F/U), the L7b layer
coded the encounter as **99215** (E/M level 5, established patient).
The clinically defensible level given the encounter's actual MDM
elements (one new prescription, one chronic-illness management,
one planned diagnostic test) is **99214** (level 4).

This is a single data point, not a pattern. But combined with the
PL-03 finding ("ordered" wording in the L7b reasoning JSON for
considered-not-yet-ordered work), it suggests the L7b prompt may
nudge encounter complexity upward.

## Why it matters

Persistent upcoding can flag a doctor for payer audit + recoupment.
CMS routinely recovers overpayments from clinicians flagged via
RAC audits. A patterned 99215 instead of 99214 across hundreds of
visits could trigger a 1–2 year audit costing the clinic significant
time and possibly refunds.

Even modest upcoding bias in an AI scribe affects every doctor using
the product — multiplying the legal/compliance risk across the user
base.

## Reproduction

1. Sign in as a verified test user (any specialty)
2. Create a visit with audio that has these MDM elements:
   - 1 new prescription start
   - 1 chronic-disease management adjustment
   - 1 planned (not performed today) diagnostic workup
3. Wait for pipeline → check the Codes tab → CPT code

Expected: 99214. Observed: 99215 (single sample).

## Risk if NOT fixed

- Per-visit upcoding × patient volume × audit-discovery probability
  = real dollars + clinician compliance burden.
- Brand reputation if a doctor gets caught and the AI is blamed.

## Proposed remediation

1. **Calibrate.** Run L7b against a 50-visit ground-truth set
   (human-coded encounters with known ICD/CPT). Measure
   over-coding / under-coding rate.
2. If over-coding rate > 5%, tune the L7b prompt with a
   "downward-pressure" instruction:
   > "When MDM elements are borderline between two levels, prefer
   > the LOWER level. The downstream Coding Coach allows the doctor
   > to upgrade with one click; the cost of forcing an upgrade is
   > one click. The cost of a payer audit triggered by AI-driven
   > upcoding is much higher."
3. Re-measure after prompt change.

## Effort
- Calibration set assembly: ~4 hours
- Prompt tune + re-measure: ~2 hours

## Risk to fix
LOW — prompt-only change, downstream Coding Coach + doctor review
catch any errors.

## Status
Plan-only. Do not auto-fix.
