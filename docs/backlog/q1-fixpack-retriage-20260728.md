# Q1 fix-pack — re-triage against current main (2026-07-28)

The original triage (`docs/audit-reports/q1-fixpack-triage-20260506T190348Z.md`)
was taken on 2026-05-06. Since then the app has been through the C3 redesign, the
document-first rewrite, the read-only-paper review screen, the chat editor, the
E/M rehome and the ultrasound specialty. **A backlog that predates three rewrites
is a list of guesses until it is re-validated**, so every item below was re-checked
against main by running the original evidence query again.

Six of sixteen were closed by later work and nobody had marked them.

> The source doc's section header says "STILL-OPEN (15)" but lists 16 bullets.
> Sixteen is right; the header is a typo carried since May.

## Re-triage

| # | Verdict | Evidence re-run against main |
|---|---|---|
| **01.2** L4 SOAP-gen is zero-shot | **STILL-VALID** | no `prompts/soap-exemplars.ts`; 0 exemplar/few-shot refs in `04-generate-soap.ts` |
| **01.3** L5 critique enumerates 3 red flags | **STILL-VALID** | still exactly the same 3 (chest pain / new-onset headache / pediatric fever); no `prompts/red-flags.ts` |
| **01.4** L3 entity prompt is specialty-blind | **STILL-VALID** | 0 `specialty` refs in `03-extract-entities.ts`; no PHQ-9 / NYHA / EF fields |
| **02.2** single-speaker monologue in conversation mode | **OBSOLETE** | `02-speaker-roles.ts:126` now branches on `samples.size === 1` — the short-circuit the audit proposed exists |
| **02.3** 3+ speakers / caregiver attribution | **STILL-VALID** | 0 caregiver/family refs in L4; no relation field in L3 |
| **02.4** code-switching EN ↔ ES/ZH | **SUPERSEDED** | L1 now carries 15 language refs **and** an interpreter flag; the visit wizard offers "With interpreter?" — the audit's Phase-1 "detect + flag" scope shipped as a product feature |
| **02.8** conflicting allergy information | **OBSOLETE** | `superseded` appears 11× in the L3 schema and a CONFLICT-RESOLUTION block appears 2× in the prompt |
| **02.9** negation / ROS polarity | **STILL-VALID** | 0 `polarity` refs in `03-extract-entities.ts` |
| **03.1** OB-GYN missing from the catalog | **OBSOLETE** | `packages/shared/src/specialties.ts` now has 14 SPECIALTIES entries and 9 `ob-gyn` refs |
| **03.3** cardiology structured outputs | **STILL-VALID (narrowed)** | 0 NYHA/EF fields in L3. **CPT half closed this pass** — see below |
| **03.4** pediatrics growth + developmental | **STILL-VALID (narrowed)** | 0 growth/developmental fields in L3. **CPT half closed this pass** |
| **03.7** allowlists are family-medicine-biased | **PARTIAL → CLOSED this pass** | ICD grew 119 → **566** codes (closed earlier, unrecorded). CPT gaps were all 16 still missing; **closed in this pass** |
| **05.1** L2 speaker-role prompt is unwrapped | **OBSOLETE** | `wrapAsData` now appears 2× in `02-speaker-roles.ts` |
| **06.2** L4 + L6 have no output validation | **OBSOLETE** | `soap-structure-validator.ts` exists and `04-generate-soap.ts` references it 2× |
| **07.1** L6 polish sees only draft + critique | **STILL-VALID (narrowed)** | `Layer6Input` gained `noteTemplate`, so the structure question is answered — but still no `entities`, `roleLabeledTranscript` or `specialty` |
| **09.1** refusals not categorised | **OBSOLETE** | `refusal` appears 9× in `packages/ai/src/anthropic.ts`; the `AI_REFUSAL` audit action exists |

**Tally:** 6 OBSOLETE · 1 SUPERSEDED · 1 closed this pass · 8 still valid.

## Added during the 2026-07-28 arc

| # | Item | Verdict |
|---|---|---|
| **N1** | Spoken CPT 93970 did not reach PROCEDURES on a prod smoke | **STILL-VALID.** ⚠️ Not an allowlist gap — 93970 **is** allowlisted, and a test now pins that. The defect is upstream in L3 extraction / L7b coding, which is where the next investigation should start |
| **N2** | Speaker reassignment as a pre-pipeline capability | **DESIGN NOTE, not a defect.** Deleted deliberately (it mutated `speakerMap` without re-running the pipeline — the pretend-success class). If it returns it belongs BEFORE the pipeline runs, where re-deriving the note costs nothing |

## Ranked by pilot relevance

Pilot specialties are the axis: a gap that silently degrades a pilot doctor's own
notes outranks a general quality improvement.

| Rank | Item | Scope | Why here |
|---|---|---|---|
| 1 | **N1** — spoken CPT lost | **medium** | A procedure the doctor said aloud vanished from the note. Silent, clinical, and already observed once in production |
| 2 | **02.9** — ROS polarity | **medium** | "Denies chest pain" can read as chest pain. Wrong-direction clinical content, and it is the known noise source behind L5 red-flag false positives |
| 3 | **03.3** — cardiology structured outputs | **large** | Pilot specialty. CPT half done; the L3 schema half (NYHA, EF, structured cardiac exam) is a schema + prompt + eval change |
| 4 | **03.4** — pediatrics growth/developmental | **large** | Pilot specialty. Same shape as 03.3 |
| 5 | **01.4** — L3 specialty-blind | **large** | The parent of 03.3/03.4; doing it generally is bigger than doing either specifically |
| 6 | **07.1** — L6 context starvation | **small** | The data is already loaded for L4/L5; the plumbing is small. Narrowed by `noteTemplate` already landing |
| 7 | **01.3** — red-flag enumeration | **medium** | Safety-adjacent, but L5 is advisory — it does not gate signing |
| 8 | **02.3** — caregiver attribution | **medium** | Real misattribution risk, lower frequency in the pilot mix |
| 9 | **01.2** — few-shot exemplars | **medium** | Quality lift, no correctness claim. Wants the doctor-edit-pattern corpus first |

## Executed in this pass (small / mechanical tier)

**§03.7 CPT half + the CPT halves of §03.3 and §03.4.**

The allowlist is fail-closed: `07b-cpt-coding` drops any code not on it and emits
`CODING_COACH_REJECTED_INVALID_CPT`. So a MISSING code and a WRONG code are
indistinguishable to the doctor — their correctly-coded echo just does not appear,
with no explanation on screen. Two **pilot** specialties had none of their
commonest procedures.

Added 31 codes across cardiology, pediatrics, OB-GYN and pain management
(282 → 308 rows after removing 5 that already existed). All publicly documented in
CMS PFS RVU / AAPC references — the licensing rationale the file already carries.

Pinned by `packages/ai/src/__tests__/cpt-allowlist-coverage.test.ts`: every
audit-cited code allowed, each passing the real `isValidCpt` including the `-NN`
modifier path, 93970 explicitly pinned so the N1 investigation starts upstream,
and a no-duplicates guard with a non-vacuity check.

**Not executed in that pass, deliberately:** everything ranked above is medium
or large. Each needs an L3 schema change, a prompt change and eval coverage —
not a mechanical edit, and not something to batch into a pass whose brief was
the small tier.

---

# Built — 2026-07-28

The three items whose absence changes what a pilot doctor's own note SAYS. Each
was proved red first; each shipped with both negative controls.

| # | Item | PR | The proof |
|---|---|---|---|
| **N1** | A dictated CPT code reaches the note | #444 | 11 evals, 5 red. Root cause was NOT the allowlist: L7b's input is `{specialty, soapFinal, entitiesJson}` and never sees the dictation, while L4 correctly omits a billing instruction from clinical prose — so the sentence no longer existed by the time coding ran. Captured at L3, merged at L7b through the SAME fail-closed allowlist, `provenance` marked in one direction only |
| **07.1** | L6 polish sees the visit | #445 | 8 evals, 6 red. A DISAMBIGUATION source, never a content source — the L6b fidelity gate still measures against the draft alone, asserted by a test that fails if the transcript is ever passed to it. Non-vacuity is the mirrored fixture: same draft, same critique, opposite entities, the resolution must flip |
| **02.9** | ROS polarity as data | #446 | 11 evals, 11 red, in both directions — an affirmed symptom rendered denied (shared quote) AND a denied one rendered affirmed ("None at all" matches no charting token) — plus side collapse. Caught a live instance in the shipped sample fixture on its first run |

---

# Parked — with the trigger written down

Everything below is real. None of it is refuted and none of it is being closed.
It is parked because **the work is specialty-shaped and the pilot roster is not
confirmed**, which means building it now is building it for a guess.

**TRIGGER TO UN-PARK: the pilot roster confirms the specialty.** That is a
single checkable fact, not a feeling that there is time. When it lands, take the
rows whose specialty is on it, in the rank order already established, and leave
the rest until a later roster names them.

| # | Item | Scope | Why parked, specifically |
|---|---|---|---|
| **03.3** | Cardiology structured outputs (NYHA, EF, structured cardiac exam) | large | CPT half closed. The rest is an L3 schema + prompt + eval change **whose field list is only correct if cardiology is actually in the pilot**. A structured NYHA slot built for a roster with no cardiologist is dead schema that every future extraction still has to satisfy |
| **03.4** | Pediatrics growth + developmental | large | Identical shape, identical dependency. Growth percentiles also need a reference-table decision (CDC vs WHO) that a real paediatrician should make, not this backlog |
| **01.4** | L3 entity prompt is specialty-blind | large | The PARENT of 03.3 and 03.4. Doing it generally is strictly bigger than doing either specifically — and doing it generally FIRST means guessing the extension shape for every specialty at once. Two concrete extensions, once the roster names two specialties, will teach more about the right abstraction than designing the abstraction up front |
| **02.3** | 3+ speakers / caregiver attribution | medium | Real misattribution risk, and not specialty-shaped — but the fix (a `relation` field on L3 + attribution rules in L4) is materially different for a paediatric clinic, where a parent routinely speaks FOR the patient, than for an adult clinic where a caregiver occasionally attends. The roster decides which problem is being solved |
| **01.3** | L5 red-flag enumeration is 3 scenarios | medium | Safety-adjacent, which argues for doing it — but **L5 is advisory and does not gate signing**, so the honest severity is quality, not safety. The audit's own recommendation is a ~30-complaint shortlist, and a shortlist chosen without knowing the specialties is the same guess as 03.3. ⚠️ Do not let "safety-adjacent" alone promote this past the roster: the gate that actually stops an unsafe note is the critical-Rx typed override, and that one is live |
| **01.2** | L4 SOAP-gen is zero-shot (few-shot exemplars) | medium | The only row here with **no correctness claim at all** — a quality lift. It also has a prerequisite the others do not: the doctor-edit-pattern corpus, which does not exist until doctors have edited notes. Writing exemplars before the pilot means writing them from imagination, which is the opposite of what few-shot is for |

## What parking does NOT mean

- **Not low-value.** 03.3 and 03.4 are pilot-specialty items and will matter the
  day the roster names them.
- **Not stale evidence.** Every row was re-validated against `main` on
  2026-07-28, in the table at the top of this document.
- **Not "revisit when convenient".** The trigger is a fact about the roster.
  Nothing else un-parks them.

---

## Source of truth

**This document.** The original triage
(`docs/audit-reports/q1-fixpack-triage-20260506T190348Z.md`, shipped by PR #171)
now carries a SUPERSEDED banner pointing here and is kept verbatim as the
historical baseline.

Its `STILL-OPEN (15)` header, which had always listed 16 bullets, is corrected
to 16 in place rather than left for whoever counted next.

PR #171 is a **merged pull request**, not an open issue — there is nothing to
close or retitle. The reconciliation is entirely in the two documents.
