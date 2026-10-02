# Relations contract v4 and spoken headings — refutation and integration decision (2026-10-02)

Branch `fix/v2-relations-compact` (base `9238fb3e`): `bfa92cbe` contract v4 (each field's relations a partition of
the offered unit IDs), `1a05bc5a` a question's own spoken heading right before its answer no longer couples it,
`b75ffef1` another printed question's spoken heading right before an answer holds it. Refutation workflow
`wf_6b7cf609-85b`: five lenses told to refute, each finding reproduced by an independent verifier on its own
detached worktrees (22 agents, no provider call, no database outside the QA test server). Full findings:
`rebuild/.runtime/v1-sonnet55-20261001/refute-rv4/result.json` (synthetic, runtime only).

## Decision

| commit | decision | why |
|---|---|---|
| `bfa92cbe` contract v4 | **integrated** (`fdcc7db2`) | nothing found by the wire lens (below); the response is about a fifth of v3's per unit |
| `1a05bc5a` own-heading release | **not integrated** | confirmed MEDIUM adoptions the base holds; no measured benefit on the live evidence |
| `b75ffef1` another-question heading hold | **not integrated** | confirmed MEDIUM over-holds after statement labels common in procedure notes; no change on the measured evidence |

## v4 wire (lens: misattribution) — NOTHING FOUND

- 630,000 mutations (44 classes) of the 35 retained relations bodies translated into v4: 165,048 accepted, every one
  equal to an independently written oracle's expected selection and to the base v3 parser's reading of the same
  answer converted back; 0 non-validation crashes.
- 140,000 grammar-valid random answers (enum ids, duplicates, foreign options): 36,662 accepted, all equal to the
  oracle and to v3.
- 63,525 end-to-end field verdicts through `validated()` with partition and selection perturbations: 17,170 adopted
  fields, 0 violations (no conflict, contrary or unresolved unit adopted; only own selected units and own options).
- Positive controls planted in memory were detected (cross-list duplicate check removed: 391 flags; bool ids: 12;
  pooled options: 48).
- The branch's contract and batch suites: 46 tests OK.

## Spoken-heading release (`1a05bc5a`) — confirmed findings

With the model's worst-case answer (the right unit picked, every other unit called `independent`):

- **RV4H-2 (MEDIUM, confirmed).** 'Medications. The patient takes warfarin 5 mg daily. Warfarin has been switched to
  apixaban. Plan. …' adopts the warfarin sentence; likewise 'replaced by', 'changed to', 'on hold', 'withheld',
  a negative penicillin challenge and a cancelled plan. The base held each only because the heading coupled the
  block; the cessation floor reads 'stopped' and 'no longer takes' but none of these.
- **RV4H-3 (MEDIUM, confirmed).** A spoken 'Assessment.' is released to a question labelled 'Assessment' in another
  section ('Nursing review') when the form also has an Assessment section; the field context is read by neither
  heading reader.
- RV4H-1, RV4H-4, RV4H-5 (LOW, confirmed): a contradicting sentence, a pronoun ('has it as well') after a family
  history line, and a later 'Reassessment.' section are no longer held by the coupling.
- The commit's own analysis of the live ankle transcript (evidence 031): none of its five answers would be
  released by the heading rule, because other floors hold them (no patient subject, a contrary pain score,
  literal-facts opposition). The release has no measured benefit on live evidence.

## Another question's heading hold (`b75ffef1`) — confirmed findings

- **O1 (MEDIUM, confirmed).** A unit whose whole text is another printed label is read as that question's heading,
  so a statement label holds the next answer: 'Smoker.', 'Consent obtained.', 'Site marked.' (procedure
  checklists) — a false rejection that also re-holds drafts the base adopted. 'Nonsmoker.' does not hold.
- O2 (LOW): only the first unit after another question's heading is held. O3 (LOW): a typed labelled line after a
  'Label.' line is held on the relations path only. O4 (INFO): 0 differences across the 35 retained responses.
- The leak it closes is real and pre-existing (an answer under another question's spoken section is adopted on
  the model's `independent`), and stays open in the candidate as a recorded residual.

## Residuals carried (pre-existing in the candidate, not introduced by v4)

1. **Supersession is the model's judgment alone.** Without any heading, both the base and v4 adopt 'The patient
   takes warfarin 5 mg daily.' when the next sentence says it was switched, replaced, put on hold or withheld and
   the model calls that sentence `independent`; a negative allergy challenge and a cancelled plan likewise. Live
   5.5 has not been observed to do this (26-27 correct, 0 unsafe in the notes campaigns), but no floor stands
   behind it. Candidate repair: a hold-only supersession floor, refuted before integration.
2. Another question's spoken section: an answer picked from it is adopted on the model's `independent`.
3. Capacity under adaptive thinking (pricing lens P1, INFO): the one-response capacity test compares the answer's
   bound with the whole `max_tokens`, leaving thinking no reserved room. Fail-closed (a `max_tokens` stop is
   refused and correctly priced); the live standing profile is `between_tools` with 0 thinking tokens.

## Falsified tests (lens: false greens)

Mutants surviving the branch's heading tests (F-2 to F-6) and zero-width look-alikes of a label (F-7) concern the
two commits not integrated. They are recorded for whoever reopens the heading question.
