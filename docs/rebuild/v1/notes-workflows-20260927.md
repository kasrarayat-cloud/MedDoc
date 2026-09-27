# Ordinary sentence syntax and compound-question review

Prepared on isolated `v1/notes-workflows`, base
`4caa34431a60e6ce3409ecadbbb6989b50659d7b`. No shared-tree changes,
provider requests, paid counts, corpus campaign, activation or deployment.
Dedicated PostgreSQL `127.0.0.1:55706` and fixture mode were asserted before
workflow execution. Independent finished-diff clinical refutation is still required.

## Demonstrated repair

The actual D30 A35 source was `The patient attends an art class every Monday.`
The original question is one physical answer area containing three printed
questions about activities, conditional inactivity/risk, and disclosure support.
The retained original hold had **no governing context**: `attends` was simply
absent from `FINITE_STATEMENT_V3`. The exact original hold remains in
[evidence](notes-workflows-20260927/evidence/original-A35-hold.json).

A bounded local syntax reader now supplies the missing completeness check without
adding verbs to that list. It applies only when the existing finite-word proof is
absent and the deterministic source grammar already names Patient/The patient,
or the existing complete actor ledger establishes the unit. It accepts one
simple finite declarative clause with a subject, rejecting the sampled fragments,
embedded/relative/conditional/infinitival clauses, passive clauses and modal
auxiliaries. This statistical parser does **not** establish clinical relevance,
polarity, actor identity, destination or complete question coverage. Existing
context, correction, consent, side, duplicate-field, source-offset and option
rules still run; no source block becomes independent through this allowance.

The same completeness result is used by generation and stored draft governance
(page, save and finalization). A forced old-supported fragment or unresolved
subject remains held even with a review tick. Its original source stays visible.
Finalized records, original notes, evidence offsets and historical receipts are
not rewritten. Legacy generation and existing finite-word positive paths remain.

### Concrete results

| Check | Retained result |
| --- | --- |
| Exact base/current comparison | Six explicitly patient-worded sentences using attends, fell/hurt, developed, smokes, walks and sleeps move from held to exact source-supported text. Exact offsets retained. |
| Authenticated simple-question workflow | Four varied questions: actual upload/mapping confirmation, mocked-selection worker, review confirmation **without answer edit**, finalization and authenticated download. Exported text equals source; original bytes and export SHA verified. |
| Actual authorized D30 A35 | Original SHA `fdeafbee872f987325e544953ad930e8e8db8ed6bd30ccab0375f2b50ecbff2f`; complete original template used. Activities text is source-supported. Clinician adds that disclosure support is not documented: **compound completion remains assisted**. Actual worker/review/save/finalize/download passes, 5.836s final check. |
| Guard controls | Foreign father, quoted/relative/embedded attribution, hopes-to, might/could, conditional, correction, wrong named field and opposite side held. `never attends` stays the complete negative sentence, never a positive activity or option. |
| Forced stored drafts | Foreign-subject and incomplete statements shown held; direct finalization and save-with-review-only cannot finalize them. Explicit clinician decisions remain available. |
| Existing finite module coverage | First affected run: 198/199 pass, one changed fragment-display assertion. Corrected explanation/assertion; affected ordinary+syntax rerun 101 pass/44.897s. Other 98 unchanged checks reused. Final focused 11 pass/15.708s, final stored-route check 1 pass/2.975s, final syntax+modal check 7 pass/1.555s. These are overlapping finite checks, not a new campaign or combined denominator. |
| Retained ordinary evidence | Original note4 and picks: base/current status and text unchanged (3 supported, remaining5 held). All34 V selections inspected for syntax only; no reassignment or compatibility score. Original12/12 and26/77 results/denominators remain preserved. |

All worker provider results are explicitly simulated and charged zero. This is
not Sonnet5 behavior evidence. D30 remains the previously recorded failed
compatibility document: improving one answer does not close its other fields,
warning, rendering or native Word requirements.

## Compound-question review

The original printed segments are listed with **coverage not verified**, beside
the usable draft and source evidence. The existing per-field clinician review
checkbox explicitly includes every part and any unanswered information. No new
mapping requirement, automatic negative answer, invented subquestion coverage,
or extra per-part decision is introduced. Single questions are unchanged.
Finalized pages do not receive a new unreviewed-coverage claim.

The Refero skill was applied using its bundled craft/copy references and existing
app review/evidence patterns; live Refero tools were unavailable. The
[reference lock](notes-workflows-20260927/UI-REFERENCE-LOCK.md) is retained.
Actual authenticated fixture HTML with existing local CSS was rendered in
Chromium at desktop and390px mobile widths, network blocked. All three original
parts and the review control were visible, the control worked, and no horizontal
overflow occurred. Screenshots and assertions are retained. This visual check
supplements the authenticated server workflow; it is not a live production walk.

## Dependency, license and operational boundary

This is a local syntax component, not the application's selected language model.
The application remains configured for Sonnet5. No clinical source is sent to
spaCy, a package host or any additional external processor.

- Library: **spaCy3.8.16**, MIT. [Official linguistic feature documentation](https://spacy.io/usage/linguistic-features), [release metadata](https://pypi.org/pypi/spacy/3.8.16/json).
- Model: **en_core_web_sm3.8.0**, MIT. [Official model page](https://spacy.io/models/en), [model metadata](https://raw.githubusercontent.com/explosion/spacy-models/master/meta/en_core_web_sm-3.8.0.json), [official compatibility manifest](https://raw.githubusercontent.com/explosion/spacy-models/master/compatibility.json).
- Exact library wheel SHA256: `8d0f63c3124d0a34a37e9b519d004cee1269744be07f91f843902e6c9f3e557a`.
- Exact model wheel SHA256: `1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85`.
- Installed model files have a committed SHA256 manifest, checked before load. Missing/mismatched package versions, altered model bytes, unavailable model or parser failure add no allowance. No runtime download/fallback model exists. The library/model licenses and bundled source notices are retained, including the model publisher's OntoNotes license attribution and WordNet notice.
- Requirements pin every newly resolved dependency; the model URL has its wheel hash. [Exact observed Linux CPython3.12 wheel lock](notes-workflows-20260927/evidence/syntax-wheels.lock) and [URLs/versions/hashes](notes-workflows-20260927/evidence/dependency-lock.json) permit reproduction after the existing application requirements: `python -m pip install --no-deps --require-hashes -r <syntax-wheels.lock>`. Production install remains `python -m pip install -r rebuild/requirements.txt`.
- Isolated `.venv` is an actual environment in this worktree; existing app packages were read via a `.pth` into the shared environment. Shared packages were not changed. Final isolated tree size296121587bytes. A fresh production build must install the full locked requirements; it must not rely on that development `.pth`.
- Cold model load+one parse1.125s; warm64 sentences0.080s; measured process peak163300KiB including Django. These are one-host observations, not production capacity guarantees. Parser limit64 eligible units/read,1000 characters/unit,128 tokens/unit; excess/complex units stay held. Only the parser instance is cached, never source text. Worker/web process memory must include this local model before cutover.
- Initial local audit found12 advisory entries in the venv scaffold's pip24.0 (with duplicates); pip was upgraded to the already-pinned application version26.2.1. Final installed-path audit: no known vulnerabilities in audited packages. The model is not on PyPI and is explicitly unauditable by that tool; its integrity/license checks are separate. Both audit results remain.

## Preserved failures and limits

The first generic parser allowance incorrectly released `Her father attends an
art class every Monday.`. It is preserved and repaired by requiring the existing
explicit source actor/ledger and retaining all governance. The first test pass
also had a duplicate synthetic-template name instrument error and an overbroad
`Sleep`-label positive assumption; no source guard was loosened to satisfy them.
The existing fixed-verb contract was not rewritten: unanchored He/She examples
remain held on the new fallback. The exact base/current comparison retains both
states, rather than presenting the first six-sentence experiment as final scope.

Existing finite paths can still retain complete source-qualified text such as
`Patient reports her father attends an art class every Monday.` and `The patient
is escorted to an art class by her father.`. The parser does not participate in
these paths and does not certify them as the patient's direct activity. Source
fidelity is not semantic applicability. The new parser is trained on general
English, not validated as a clinical meaning classifier. No broad ordinary-note
completion, contradiction detector, universal Word support or launch readiness
is claimed.

**B-G1 remains internal engineering.** The prior34 V/7 J/10 I among51/77 holds
are not reclassified as funding dependencies. Complete history block/destination
sharing, patient predicate evidence, SOAP roles, caregiver relationships,
encounter ownership and cross-question clinical context still need their stated
source contracts and proof. The retained note4 NKA/anaphylaxis/hypersensitivity
counterexample is not bypassed. This syntax slice repairs a reusable independent
cause; buying a provider call or changing a model name cannot close those
remaining deterministic gaps. See the unchanged
[remaining51 classification](patient-topics-20260927/REMAINING-51.md).

## Evidence and next action

Runtime: `/opt/meddoc-pro/.worktrees/v1-notes-workflows/rebuild/.runtime/notes-workflows-20260927/`.
Scripts, first failures, final logs, source hashes, package licenses, exact
comparisons and artifact hashes are copied into the report evidence directory.
Filled synthetic DOCX and full rendered pages remain in runtime, not fixtures.
No unknown paid attempt, reservation, deployment lock or pending activation was
created. Next safe action: independent finished-diff refutation, then lead-owned
reviewed union and only the missing union checks. Do not install/activate from
this isolated tree or infer Sonnet5 serving/launch status from these proofs.
