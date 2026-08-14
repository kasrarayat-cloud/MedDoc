# Gastroenterology — named open items, recorded 2026-08-14

Recorded at the owner's instruction alongside the GI specialty rollout:
*"The procedure-note E/M-suppression question and colonoscopy CPT procedure
coding are RECORDED as named open items — not built tonight, not forgotten."*

Both are written against **measured** evidence, not intent. Every file:line
below was read during the GI enumeration. Where a claim is inherited it says so.

---

## GI-OPEN-1 — Procedure notes and the office-visit E/M level

**Status:** OPEN. Not built 2026-08-14, deliberately.
**Trigger to build:** the GI pilot produces operative notes that a biller
rejects, OR the owner confirms procedure notes must carry no E/M level.

### The question

An office-visit E/M level is meaningful for a GI **clinic** visit and
meaningless for a **colonoscopy operative note**. Today GI carries E/M for
both, because E/M applicability is decided per-SPECIALTY and never per-ENCOUNTER.

That is the correct behaviour for tonight — E/M stays ON for GI, per the brief,
because GI clinics bill office visits and turning it off wholesale would break
the shape that actually pays.

### ⚠️ THE TRAP — READ THIS BEFORE WRITING A LINE

**The obvious one-line fix moves every GI note to the ultrasound prompt
builder and deletes the note.**

`packages/shared/src/specialties.ts:103`

    export function emAppliesToSpecialty(id) {
      return !(ultrasoundSpecialtyEnabled() && isImagingReportSpecialty(id));
    }

That function is NAMED for the E/M question. It is USED as the report-shape
switch:

`apps/transcribe-md/src/worker/layers/04-generate-soap.ts:94-95`

    const isUltrasoundReport = !emAppliesToSpecialty(input.specialty);

and at `:265-267` that boolean selects `buildUltrasoundSystemPrompt` over
`buildSoapSystemPrompt`, at `:100` it suppresses `specialtyGuidance`, and at
`:112-118` it swaps the resolved template.

So adding `'gastroenterology'` to `isImagingReportSpecialty` — the natural way
to express *"a GI procedure note has no office E/M level"* — would ALSO:

| consequence | site |
|---|---|
| route GI to the IMAGING prompt builder | `04-generate-soap.ts:265-267` |
| discard GI's specialty guidance | `04-generate-soap.ts:100` |
| swap the resolved template | `04-generate-soap.ts:112-118` |
| suppress L7b CPT coding | `worker.ts:964` |
| enable the venous measurement reconciler | `worker.ts:934` |

**One line, whole-note consequence, and nothing in the name warns you.** This is
AGENTS.md's *"a check whose TITLE is narrower than what it MEASURES"* arriving
in a predicate rather than a gate. Found 2026-08-14 by the RC-1 session
(meddoc-pro-46) during its adversarial pass; independently re-read and confirmed
here at `04-generate-soap.ts:94`.

### The shape of a correct fix

**Split report-shape from E/M-applicability before changing either.** They are
one boolean today and agree only because `ultrasound` is the sole member of both
sets. Then decide E/M per ENCOUNTER (the template's shape / the visit's
encounter type), not per SPECIALTY — a GI doctor produces both shapes on the
same day, so a specialty-level answer cannot be right for both.

Also in scope when this is done:
- the two BARE `isImagingReportSpecialty` calls at `worker.ts:934` and `:964`
  skip `ultrasoundSpecialtyEnabled()`, unlike all ten `emAppliesToSpecialty`
  sites — a pre-existing inconsistency in the ULTRASOUND path. Verified by
  reading. Left alone deliberately in the GI change.
- `scripts/check-imaging-em-artifacts.sh:52,:68` are scoped to
  `specialty='ultrasound'`. If procedure notes become a report shape, that
  script's green becomes true-and-worthless until its watched set is widened.
- the E2E matrix `tests/e2e/helpers/seedReviewDocVisit.ts:276` is a hand-kept
  TWO-member `REVIEW_DOC_CLASSES` with a binary ternary at `:513`.

**Do NOT convert `emAppliesToSpecialty` into an allowlist to "make GI explicit".**
There is exactly one opt-OUT string and no opt-IN list anywhere; an allowlist
would silently turn E/M OFF for every specialty nobody remembered to add.

---

## GI-OPEN-2 — Colonoscopy CPT procedure codes are dropped from billing output

**Status:** OPEN. Not built 2026-08-14, per instruction.
**Severity: higher than it looks, and it is NOT a new feature.** See below.
**Trigger to build:** the first GI pilot colonoscopy — i.e. immediately on
pilot start, not on a schedule.

### Measured, not assumed

`packages/ai/src/data/cpt-allowlist.ts` is a HAND-CURATED allowlist (deliberately
so — full CPT is AMA-licensed and the repo has no agreement at pre-pilot scale).
Grepped 2026-08-14 with a positive control:

| code | meaning | in allowlist |
|---|---|---|
| 45378 | colonoscopy, diagnostic | **0** |
| 45380 | colonoscopy with biopsy | **0** |
| 45385 | colonoscopy with snare polypectomy | **0** |
| 45390 | colonoscopy with EMR | **0** |
| 43235 | EGD, diagnostic | **0** |
| 43239 | EGD with biopsy | **0** |
| G0105 | screening colonoscopy, high risk | **0** |
| G0121 | screening colonoscopy, not high risk | **0** |
| *99213 / 99214 (control)* | *office visit* | *1 / 1 — the grep works* |

### What happens today

`apps/transcribe-md/src/worker/layers/07b-cpt-coding.ts:295-312`

    const filteredProcedures = mergedProcedures.filter((p) => {
      const ok = isValidCpt(p.code);
      if (!ok) rejectedCodes.push(p.code);
      return ok;
    });
    if (rejectedCodes.length > 0) { void logAudit({ action: 'CODING_COACH_REJECTED_INVALID_CPT', … }) }

The code is **dropped from the billing output**. An audit row is written
fire-and-forget. **The doctor is shown nothing.** A correctly dictated
colonoscopy code reads to the doctor as a code that was never proposed.

### ⚠️ THIS EXACT FAILURE HAS ALREADY SHIPPED ONCE, TO ANOTHER PILOT SPECIALTY

`cpt-allowlist.ts:374-377`, verbatim:

> `// === Cardiology (2026-07-28, Q1 fix-pack §03.3/§03.7) ===`
> `// A pilot specialty whose commonest procedures were absent, so the 07b`
> `// validator dropped them and emitted CODING_COACH_REJECTED_INVALID_CPT —`
> `// a correctly-coded echo read as an invalid one.`

**GI is positioned to repeat Cardiology's documented failure, on day one of the
pilot.** The precedent fix was ~10 lines of data added to the same file.

### Why it was still deferred, and what the deferral costs

Deferred because the owner scoped it out of tonight explicitly. The cost is
bounded and recoverable: a **billing miss**, not a clinical-safety event. E/M
coding is unaffected (that path is separate and works). The doctor can add the
procedure code by hand.

**But the fix is data, not engineering** — an allowlist append with an exact
precedent in the same file — so if this is to be pulled forward, it is cheap.
That is a judgement for the owner; it is recorded here rather than decided here.

### Widened by the adversarial pass, 2026-08-14 — measured, and it is worse than eight codes

An independent lens executed `isValidCpt` against the real module. ALL of these
return **false**:

    45378 45380 45384 45385 45330 45331   (colonoscopy / sigmoidoscopy)
    43235 43239 43248 43450                (EGD / dilation)
    44388 91035 91110                      (stoma endoscopy, pH study, capsule)

⚠️ **AND THE ICD SIDE IS THE SAME SHAPE.** `07a-icd-coding.ts:447` applies
`isValidIcd10` and drops what fails. Measured absent: **K63.5** (colonic polyp —
the single commonest colonoscopy diagnosis there is), D12.x, K50.90, K51.90,
K64.0, K92.1, B96.81. So on a screening colonoscopy that finds a polyp, BOTH the
procedure code and the diagnosis code are dropped.

**ADJUDICATION NOTE, recorded because it changes who owns this.** Three
independent adjudicators confirmed the MECHANISM and REFUTED the attribution:
this is **pre-existing behaviour, not introduced by the GI change**. Adding the
catalog row does not make it worse for anyone who exists today — there are zero
GI production visits until the pilot doctor creates one. What the GI change does
is put a doctor in front of it. That is the trigger, and it is why the trigger
below is "the first pilot colonoscopy" rather than a date.

Also partial: `packages/ai/src/data/icd10-allowlist.ts` GI coverage. Partial
coverage is worse than none because it looks like coverage exists.
`packages/ai/src/__tests__/cpt-allowlist-coverage.test.ts:21` carries a
hand-kept per-specialty `AUDIT_GAPS` Record naming four specialties; a fifth is
silently uncovered. Adding a `gastroenterology` row there turns this open item
into a RED test instead of a paragraph.

---

## Recorded alongside, found during the GI enumeration (not owner-named)

These are NOT part of the two instructed items. They are written down because
they were measured tonight and would otherwise be rediscovered.

**GI-OPEN-3 — Four specialty-shaped sets, nothing diffs any pair.**
`SPECIALTIES` (packages/shared, 15 rows after GI) / `SPECIALTY_KEYS`
(specialty-keys.ts, ASR taxonomy) / `SPECIALTY_GUIDANCE` keys / `spec-chip.tsx`
`SpecialtyKind` (6 members, 0 JSX mounts). Partially addressed tonight: the GI
change adds the **cross-catalog gate** (every catalog id resolves to a non-empty
bundle, or a named exemption) in `deepgram-keyterm-builder.test.ts`. That covers
catalog↔ASR. It does NOT cover `spec-chip` or `KNOWN_SPECIALTIES`
(`visits/[id]/page.tsx:55`, dead — kept alive only by `void` at `:79`), both of
which read like live allowlists and are not.

**GI-OPEN-4 — `ultrasound` transcribes with ZERO specialty vocabulary.**
OWNED BY meddoc-pro-46 / RC-1; cross-referenced here, not duplicated. Its
exemption entry in the new cross-catalog gate points at it and the gate's
anti-stale arm goes RED when a bundle lands, forcing the exemption's removal.

**GI-OPEN-5 — "Adding a specialty" instruction is 2 of 8+ layers.**
`packages/shared/src/specialties.ts:14-19` says *"append a row, add the matching
guidance text in the worker, ship in one PR."* Corrected in the GI change to
name every layer. It is the first sentence anyone adding a specialty reads, and
it was the reason this rollout nearly missed the ASR and coding layers.

**GI-OPEN-6 — Slug→label converters that will break on the NEXT hyphenated slug.**
`gastroenterology` is a single word, so it renders correctly everywhere by luck.
Seven unsanctioned converters exist (e.g. `patients-roster.tsx:190` title-cases
to `Primary-Care`; `rounds/board.tsx:37` swaps hyphens for spaces; five render
the raw slug). The sanctioned pair is `findSpecialty(x).label` / `.id`. Not
touched tonight — nothing GI does exercises them.
