# Declaration — multi-column question rows and mixed table/underline Word forms, September 21, 2026

This candidate adds real import, mapping and export support for two documented Word gaps, and
carries the clinical-path repairs the mandatory refutation gate found while proving it. It is
written **before** integration, against baseline
`875ee6e2a0836c37fcb293c228664186c1106291` — the source revision Tab 2 published as healthy
after recovering its admin-console activation (served release
`21809ef408a5f7b6691beb338a7640da82fcfb97`).

It authorizes **no** deployment, no migration, no public-asset move, no service start, no
payment and no provider call. Tab 2 remains the sole integration and deployment lead.

## Why this candidate has its own declaration

Tab 2's activation guard `scripts/activate-admin-console.py` is pinned to the range it actually
installed, and its allowlist is exhaustive for that range. Its own test states the consequence:

> *"A later, unrelated candidate must bring its own declaration; this allowlist stays
> exhaustive."*

⚠️ **The earlier collision is recorded here rather than dropped, because it is the reason this
file exists.** Before that recovery, `DeclaredSourceScope` diffed its baseline against the
branch under test, so this candidate's seven then-undeclared files made CI red on a guard that
was working exactly as designed on a tree it was never scoped for. The fix was theirs to make
and they made it. **Nothing in this candidate widens, relaxes, re-scopes or rewrites Tab 2's
guard or its historical declaration.** The instrument below is separate, and it refuses the same
protected classes on its own account.

## The declared source scope

Sixteen files. Exhaustive — anything not named here is not part of this candidate.

<!-- declared-source-scope -->

```text
docs/foundation/mutations/20260921-quillmd-word-multicolumn-mixed.md
rebuild/core/field_location.py
rebuild/core/generation.py
rebuild/core/tab_review.py
rebuild/core/tests/test_mapping_review_clarity.py
rebuild/core/tests/test_tab_form_policy.py
rebuild/core/tests/test_tab_independent_sections.py
rebuild/core/tests/test_unlabelled_source_scope.py
rebuild/core/views.py
rebuild/documents/engine.py
rebuild/documents/tab_form.py
rebuild/documents/test_multicolumn_and_mixed.py
rebuild/documents/test_tab_form.py
rebuild/documents/test_unmapped_areas.py
rebuild/ops/test_word_multicolumn_scope.py
scripts/ci/verify-fresh.sh
```

| file | what it carries |
|---|---|
| `documents/engine.py` | multi-column answer rows; mixed table + underline mapping; structural `validate_mapping`; the legacy-contract fallback at fill time |
| `documents/tab_form.py` | `also_changed`, so the tab writer emits the other writer's parts instead of the original bytes |
| `core/generation.py` | prompt version `extractive-v6-source-scope-attestation`; the consent/attestation guidance on **both** providers; the subject guards ported into the legacy validator |
| `core/tab_review.py` | a signature answer area is recognised by its label as well as its policy, wherever it sits on the form |
| `core/views.py` | `finalize` fills through the **stored** mapping, not a fresh inspection |
| `scripts/ci/verify-fresh.sh` | names the new documents module, because that list is explicit and an unnamed module is inert |
| `ops/test_word_multicolumn_scope.py` | this declaration's instrument |
| the six `test_*` modules | the proofs, including the ones that caught defects this candidate introduced |

## What is NOT declared, and is refused rather than merely absent

`rebuild/ops/test_word_multicolumn_scope.py` refuses each of these **against the declared set
itself**, so writing a path into this document is not a way past them:

| class | status |
|---|---|
| `rebuild/core/migrations/**` | **none.** No schema change. A migration needs its own reviewed act |
| `rebuild/static/**` | **none.** No public asset moves |
| `rebuild/ops/**` other than the instrument | **none.** No operations helper changes |
| `rebuild/deploy/**`, `deploy/**` | **none.** No service policy or unit changes |
| `.github/**` | **none.** No workflow changes |
| non-canonical or absolute paths | refused |

Each refusal is proved by a test that asserts it raises, alongside a positive control proving
the harness is not simply refusing everything, and a parse test proving an unreadable
declaration raises instead of quietly reading as the empty set.

## Preservation

Accounts, originals, stored mappings, finalized records, exports, audit history, credentials,
MFA, department isolation, inactive reviewer access, financial history and backups are
untouched. Legacy mappings created before this candidate fill **byte-identically** under the new
code, and the owner's colonoscopy template still exports byte-identically at 24 logical fields
over 28 physical anchors. A mapping matching neither contract is still refused. Settlements,
receipts and the pricing fingerprint are unaffected — `prompt_version` is not in the price
whitelist, and a queued job keeps its stored config.

## Known limitation, stated plainly

**This candidate does not establish universal Word compatibility, and must not be described as
doing so.** It adds support for two specific, unambiguous layouts: ordinary multi-column
question/answer tables where the answer cell is unambiguous, and forms combining supported
tables with underlined answer blanks. Genuinely ambiguous layouts remain **explicitly
unsupported** and are reported as omitted or unsupported answer areas rather than guessed at:
two or more blanks after one label, a blank in a label position, merged cells, content controls,
text boxes, legacy Word fields, tracked changes, and scanned forms.

## ⚠️ ONE ACCEPTED CAPABILITY CHANGE, ON EXISTING DATA — for the owner to revisit

**A stored encounter whose question is labelled `Signature` (or `Physician signature`,
`Signature of surgeon`, `Signed by`, and the like) can no longer be finalized until the
clinician reviews that field and either enters their own account name or leaves it blank.**

It is a deliberate consequence of the repair, not a side effect. The refutation pass measured
the alternative: `Signature` is the commonest signature label on a real Word form, and a name
lifted from the dictation reached the signature line of a finalized record with no check that
the finalizer was the person named. A pre-existing test asserted the old behaviour using that
exact label to stand for "an ordinary field"; it now asserts the new one and says why.

**The false-refusal direction was bounded deliberately.** `Signature date`, `Date of signature`
and `Attestation` are NOT treated as identity fields — they are date and free-text questions,
and demanding the clinician's name in them would block finalization for no safety gain. Nor is
any signature the label marks as somebody else's: `Patient signature`, `Signed by (witness)`,
`Guardian signature`, `Interpreter signature`.

**What is not known, and is not guessed:** how many stored encounters carry such a label. That
needs a read of the live database, which this candidate does not touch and which is Tab 2's to
perform during coordinated integration. The blast radius is stated as a predicate, not a count.

## Integration acceptance — six further repairs, 2026-09-21

Reviewed at merge time by the integration lead against the owner's acceptance list. Six defects
were reproduced by measurement and repaired here; all six were in this candidate or in the path
it touches.

| # | defect | evidence |
|---|---|---|
| 1 | **the two-column mapper erased a ticked checkbox** — the SHIPPED MAJORITY PATH still enumerated three tags while `cell_occupied`'s own docstring claimed one shared predicate. Measured: `Consent obtained \| ☑` mapped and the symbol was deleted from the export | now uses `usable_answer_cell`; the row is reported instead |
| 2 | **`Signature (date)` and `Signature (date and time)` were treated as clinician-signature fields** — the declared false-refusal bound, reachable by another spelling, because the qualifier arm is content-blind | the parenthetical alone is checked; `Signature/Date` stays recognised |
| 3 | the two copies of the trailing-punctuation set had **diverged on `,` and `;`** | aligned, and asserted character-for-character in both directions |
| 4 | four docstrings still asserted the superseded `fields != mapping` rule | annotated as superseded |
| 5 | `if __name__ == "__main__"` sat **before** two test classes, so a direct run skipped them silently | moved to the end |
| 6 | the declaration instrument's anti-vacuous control was **fail-OPEN on cannot-tell** and tautological | an unreachable baseline now FAILS; the assertion is `REQUIRED <= changed` |

**And three acceptance claims had no check.** The declaration asserted the owner's form "exports
byte-identically" and legacy mappings "fill byte-identically", while the tests asserted counts.
`AcceptanceForIntegration` now pins a **content digest** over the zip entries (not file bytes — a
`.docx` carries a timestamp, which produced a withdrawn false finding once), with a determinism
control, plus the ticked-checkbox regression and a placement regression for the renumbered-cell
hazard behind the finalize change.

## Measured signature impact on the live database

Read-only aggregate, counts only, no label or name printed: **227 fields, 23 template versions,
28 encounters. Identity fields before: 3. After: 3. Newly covered: 0. Coverage lost: 0.**
**Zero stored encounters need a clinician decision they did not already need.** The three
signature-bearing versions carry 1 draft, 2 review and 5 finalized encounters, and all three were
already protected by `answer_policy`. A positive control over synthetic fields moved three
verdicts, so the zero is a measurement and not a broken instrument.

## Activation conditions

1. Tab 2 coordinates integration. This candidate stays **unmerged and undeployed** until then.
2. One purposeful provider verification is held for the coordinated activation, scenario fixed
   in advance — see `HANDOFF.md` §1e. No repeat transcription, no new spending authority.
3. The clinical-generation review gate runs over the finished diff before merge, as standing
   authority requires, and its findings are repaired before the candidate is offered.

## What the review gate found on this diff

Four lenses, one sealed sandbox. **Eight findings survived independent re-measurement in a clean
tree** — re-measured rather than believed, because the lenses shared a sandbox and one of them
was authorised to mutate it. **All eight were defects in this candidate, and all eight are
repaired here.** Three concerned answer PLACEMENT on multi-column rows, and closing them
narrowed the feature: a part-filled pairs row and every odd-width row are now reported as
unmapped rather than guessed at, because nothing in such a row distinguishes a question from
ordinary data. Nothing shipped is lost by that — the narrowed shapes are ones this unmerged
candidate introduced.

**A second round over the repaired diff found ten more; six survived re-measurement and are
also repaired here.** They were: the abbreviations `DD`/`DT` disarming the date guard from the
other side; `Signed by (witness)` claimed as the finalizing clinician's own signature; the
declaration guard refusing `rebuild/ops/` while this repository keeps its activation scripts,
merge wrapper, mutation runner and push hook under `scripts/`; a declaration list that could be
read from the wrong fenced block; the version gate tested only at v4 when v5 is what will be in
the queue; and `also_changed` having no test that could fail without it.

⚠️ **And the ninth was in the instrument below.** It located this candidate by matching the
declared set, so a declaration that went out of date matched no tip, SKIPPED, and printed OK.
It happened on the first real occasion, one commit after the instrument was written. It now
anchors on the declaration file itself — nothing else adds it — and a mismatch FAILS, naming
the offending path in both directions.
