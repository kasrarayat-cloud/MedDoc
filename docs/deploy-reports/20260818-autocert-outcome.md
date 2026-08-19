# Auto-certification — deployed, and the observed outcome is REFUSED

**Deployed:** `506626af` (three deploys: `f6f145b8` auto-certification + F12-c,
`3e3a589f` the jobId fix, `506626af` its declaration).
**Backfill run:** 2026-08-18 `23:19:01Z`, production, `--commit`, 1 of 1 enqueued.

## THE OUTCOME, VERBATIM

    [template-twin:certify] BLOCKED compiled=617d6de9… template=cmsxip5f9000901nadsggo2l1:
      fillCoverage=false (7 filled, need >= 10 — the synthetic encounter must
      exercise a realistic fill, or the certificate attests a template whose
      fill path is dead)

Audit row, read back from `audit_logs`:

    TEMPLATE_TWIN_CERTIFY_FAILED  {"auto": true, "stage": "certify",
      "reason": "Confirm every field, clear blocking structure, and verify a
                 synthetic DOCX using the current mappings."}

**The template is NOT certified and its state is intact:** `NEEDS_CONFIRMATION`,
**80 mappings CERTIFIED, 0 pending** (was 74/6). The doctor does not redo that
work. `certified_versions` stayed `0`, exactly as the declaration allowed.

## WHAT THIS PROVES WORKED — measured, not asserted

| observation | evidence |
|---|---|
| the job is enqueued and consumed | `enqueued 1 of 1`, worker ran it at `23:19:04Z` |
| the AI confirms its own proposals | `confirmedCount: 80, declinedCount: 0` |
| provenance is honest | `{"model": 69, "structural": 6, "blank_by_design": 5}` — sums to 80, and **no mapping is attributed to a human** |
| the ruled audit signal is real | `"proposedByModel": "claude-sonnet-4-6"` |
| ⚠️ **the round-trip proof PASSED** | `TEMPLATE_TWIN_SYNTHETIC_TESTED {"verified": true, "fieldCount": 80, "outputSha256": "722c3f0a…"}` |
| fail-closed is LEGIBLE, not a crash | `TEMPLATE_TWIN_CERTIFY_FAILED` with `stage:"certify"` — the catch added after the QA walk |
| fill-time laterality enforcement is live | `[template-twin:bridge] cell left blank … reason=laterality_mismatch` |

⚠️ **THE SYNTHETIC TEST VERIFYING IS NEW.** Before the evidence-gate fix it
could not pass anywhere, by any path, because `VERIFICATION_ENCOUNTER` carried
no explicit synthetic marker and the gate throws on that **before any model
call**. A synthetic DOCX was produced and verified in production for the first
time.

## THE ONE REMAINING GATE, AND IT IS THE NEXT FIX'S SPEC

`VERIFICATION_ENCOUNTER` fills **7** of this form's fields. The lifecycle gate
requires **≥10**, and a measurement CELL among them. The encounter is a generic
bilateral venous-reflux dictation; the owner's form is an 80-field Venous Duplex
report whose table cells want vessel-by-vessel diameters and reflux times.

Four cells were left blank with reasons the bridge printed:
`no_supporting_fact` ×3 and `laterality_mismatch` ×1.

**The fix is to make the verification encounter exercise the form it is
certifying** — either a richer standing encounter, or one derived per template
from the compiled field set. It is NOT to lower the threshold: a certificate
over a dead fill path is exactly what that gate exists to refuse, and weakening
it would buy a green tick with a template nobody proved.

## WHAT IS NOT CLAIMED

- No template is certified. No `fill_manifest` exists in production (still `0`).
- No visit was run, no export rendered, nothing signed. A real doctor's visit is
  never a smoke target.
- ⚠️ **The owner has NOT been told the letterhead is automatic**, because it is
  not. He is told the exact reason and that his mappings are done.

## DEFECTS FOUND, IN ORDER, ALL BY RUNNING THINGS

1. **`VERIFICATION_ENCOUNTER` failed its own evidence gate** — deterministic,
   pre-model, and shared with the MANUAL path. No template could certify by any
   route, in any environment. Found by the QA walk.
2. **A lifecycle refusal escaped as an unhandled throw** — a failed worker job
   with no audit row and no reason. Found by the QA walk.
3. **The upload could hang on an unreachable Redis** — ioredis retries forever,
   so the surrounding catch never ran. Found by the unit suite.
4. **`jobId: autocert:<id>` — BullMQ refuses a colon at `add()`** — the enqueue
   always threw, so auto-certification was inert everywhere. **The same file
   already documented this failure ~100 lines below the line that reintroduced
   it.** Found by running the real backfill.

Every one was invisible to a mocked test. Three of the four were found only by
executing the real path.
