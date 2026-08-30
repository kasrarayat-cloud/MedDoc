# JUDGEMENT — code-only deploy of `6debaadf`

**Judged against `docs/foundation/deploys/20260830-6debaadf.md`**, whose commit
timestamp precedes the act. Deployed 2026-08-30T09:22Z; judged immediately after.

## Verdict: 14 of 14

### MUST CHANGE — both moved

| quantity | declared | measured | verdict |
|---|---|---|---|
| image `transcribe-md` | `da45ff52886d` → must move | `986bcf335e0c` | ✓ |
| image `transcribe-md-worker` | `c1a48b03492a` → must move | `68293f2470ee` | ✓ |

### MUST NOT CHANGE — all twelve held

| quantity | declared | measured | verdict |
|---|---|---|---|
| migrations applied | 111 | 111 | ✓ |
| `AuditAction` enum labels | 153 | 153 | ✓ |
| visits | 54 | 54 | ✓ |
| signed visits | 36 | 36 | ✓ |
| patients (`transcribe_md_patients`) | 42 | 42 | ✓ |
| signed visits with E/M omitted | 21 | 21 | ✓ |
| note templates | 14 | 14 | ✓ |
| twin compiled versions | 3 | 3 | ✓ |
| twin certifications | 1 | 1 | ✓ |
| twin fill manifests | 2 | 2 | ✓ |
| owner confirmed mappings | 35 | 35 | ✓ |
| audit rows (may only GROW) | 12087 | 12087 (grew by 0) | ✓ |

All nine containers healthy; the two that moved report `Up About a minute`.

## Structural verification — and the instrument that had to be fixed first

⚠️ **THE FIRST BUNDLE CHECK WAS A BROKEN INSTRUMENT, NOT A FINDING.** It returned
**zero** for the new code AND zero for `past_medical_history`, which must be
present. Two zeroes with opposite meanings is one broken instrument. Cause: the
**worker container ships SOURCE, not a `.next` build**, so the grep addressed a
directory that does not exist there. Re-run per container, each with a positive
control:

| container | control | measured |
|---|---|---|
| worker (source) | file present | yes |
| worker | `ACCUMULATING_NARRATIVE_CONCEPTS` | 2 |
| worker | `canonicalConcept(raw.normalize` | 1 |
| worker | `lateralities.size > 1` | 1 |
| worker | OLD denylist in **code** (must be 0) | 0 |
| web (`.next`) | `past_medical_history` (control) | 8 files |
| web | `list_valued_narrative_joined` | 3 files |

## ⚠️ THE DEPLOY SUCCEEDED. THE OWNER'S FORM IS STILL NOT CERTIFIED.

Said plainly, because the two are separate claims and only the first is proved.

**What this deploy fixed, and it is proved:** his `Past Medical History` and
`Plan` no longer resolve as `FIELD_CONFLICT`. Driven through the REAL projector
and resolver against his real compiled state:

    past_medical_history  supported  "Hypertension; Type 2 diabetes mellitus"
    plan                  supported  "Continue current medications; Follow-up in three months"
    validateTemplateTwin  valid=true  blocking=0
    resolutions 35 / fields 35, every one legal under the renderer's own rules

**What now blocks, and it is a DIFFERENT gate:**

    [auto-certify] status=proof_failed confirmed=35
      reason=The document field resolutions are incomplete or invalid.
    [template-twin:pin] EXTRACTION FRESH encounterSha=392185bdbe88   (was 0210638e4ff4)

`FIELD_RESOLUTION_INVALID`, raised by `note-template-docx/renderer.ts` — the
DOCX render stage, downstream of everything this deploy touched. Two facts about
it, both measured:

- **The pinned encounter REGENERATED.** `encounterSha` moved `0210638e4ff4` →
  `392185bdbe88` because the mapping corrections invalidated the pin. So the
  proof now runs against a different synthetic encounter than the one that
  produced the original two conflicts.
- **The resolver and validator are NOT the cause.** Reproduced locally against
  his real IR, mappings and new pinned entities: 35 resolutions for 35 fields,
  validation `valid=true`, `blocking=0`, and no resolution violates any arm of
  the renderer's `assertResolutionStatus`. The failure is inside the render
  against the source artifact, which the local probe does not reach.

**This is a new item, not a regression of this deploy.** Nothing in the range
touches the renderer; the four changed files are the resolver, the validator,
the shared derivation module and one test.

## Held declaration — still held

`20260820-cba367fc` (F5-d(b)) was DEFERRED BY NAME in the declaration and is
**not** discharged here. It remains unjudged.
