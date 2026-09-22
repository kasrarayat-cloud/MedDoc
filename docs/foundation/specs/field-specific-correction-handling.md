# Field-specific correction handling — specification and regression matrix

**Status:** SPECIFICATION ONLY. Nothing here is implemented.
**Written:** 2026-09-21, against `eb37c784` plus the candidate-review change (Option C).
**Verification class:** OFFLINE. Every number below came from calling the validators directly with
synthetic notes. **No provider call was made and none is authorized** — the §1e allowance is spent.
Live AI qualification is a separate, later exercise and nothing here substitutes for it.

> ⚠️ **OPTION C DOES NOT SOLVE THIS.** Option C keeps a candidate visible when the scope validator
> holds it for review, so a doctor can accept it in one click instead of retyping it. It does not
> change *when* the validator holds an answer, and the measurements below are the reason that
> question needs its own release.

---

## 1 · The rule as it stands today, measured

Scope is computed **once per note** and applied to **every field in it**. Both contracts do this,
and they do it differently, so the same note gets opposite treatment depending on the form.

**Legacy contract** (`validate_selections`, `generation.py:377`):

```python
scoped_lines = all((parsed := labelled_value(line, labels)) and parsed[1] for line in lines)
inherited_context = len(lines) > 1 and not scoped_lines
```

Every non-empty line must parse as `<a question label>: <value>`. One line that does not — a
disclaimer, a sign-off, an administrative remark — makes **every answer in the note**
review-required.

**Tab contract** (`source_units`, `generation.py:213`): a single `inherited` boolean is raised by any
line that ends in `:`, matches `UNSCOPED_NEGATIVE_HEADING`, contains a quotation mark
(`QUOTED_SOURCE`), matches `INHERITED_SCOPE`, or — in a multi-line note — is an unpunctuated line
that does not parse as a recognized label. Once raised it applies to every field.

### Measured behaviour — identical notes, both contracts

Three questions (`Referring physician`, `Extent of examination`, `Indication for procedure`), three
correctly documented labelled lines, plus one extra line.

| # | the extra line | legacy | tab |
|---|---|---|---|
| — | *(none — baseline)* | supported ×3 | supported ×3 |
| A1 | `Fictional software test only.` (leading) | **conflict ×3** | supported ×3 |
| A2 | `Dictated and not read.` (trailing) | **conflict ×3** | supported ×3 |
| A3 | `Copy sent to the referring office.` | **conflict ×3** | supported ×3 |
| B1 | `The following findings are denied:` (leading) | **conflict ×3** | **conflict ×3** |
| C1 | `Correction: the extent was the splenic flexure.` | **conflict ×3** | **supported ×3** ⚠️ |
| C2 | `…zero millilitres; correction, less than one millilitre.` | **conflict ×3** | supported ×3 |
| C3 | `The extent above should be amended.` | **conflict ×3** | **conflict ×3** |
| D1 | `If bleeding recurs we would repeat the study.` | **conflict ×3** | **conflict ×3** |
| D2 | `The patient said "it hurts here".` | **conflict ×3** | **conflict ×3** |

**Read the A rows and the C1 row together.** The legacy contract blanks three correct answers
because a doctor signed off their note. The tab contract keeps three answers `supported` after the
doctor wrote a correction that changes one of them. Neither is field-specific; they fail in
opposite directions.

### 1.1 · What actually caused §1e, measured

The §1e first pass returned three correct answers and the validator blanked all three. The cause was
**not** the opening disclaimer. It was this, in `source_units`:

```python
if not re.search(r'[.!?]["\')\]]?$', stripped) and not (parsed and parsed[1]):
    inherited = inherited or multiline
```

The submitted note used the doctor's own headings — `EXTENT:`, `INDICATION:`, `Referring
clinician:` — while the form's questions are worded differently. `labelled_value` only recognises
the **form's** wording, so each of those lines failed to parse, and because none of them ends in a
full stop each was counted as an unpunctuated fragment. Measured on the retained submitted text:

| field labels used | `inherited` | lines counted as fragments |
|---|---|---|
| the doctor's headings ARE the question labels | `False` | none |
| the form words its questions differently | **`True`** | all three labelled lines |

Adding a full stop to each heading line, or matching the form's wording exactly, makes the same note
pass. **That is template-specific syntax, and a doctor has no way to know either rule exists.**

---

## 2 · The rule this specifies

> **Scope is a property of the EVIDENCE, not of the note.**

An answer is held for review when something that governs **its own evidence** says so. A line that
governs nothing in particular still governs everything — the conservative default is retained, not
removed.

**The existing vocabulary is reused unchanged.** `INHERITED_SCOPE`, `UNSCOPED_NEGATIVE_HEADING`,
`QUOTED_SOURCE`, `FINITE_STATEMENT`, `SUBJECTS` and `INLINE_CORRECTION` remain the only detectors.
No new keyword list is introduced. `INHERITED_SCOPE`'s fourteen words are already split in code
into `SCOPE_POINTERS` and `SCOPE_REFRAMERS` (`generation.py`), with `INHERITED_SCOPE` rebuilt from
the halves and a test asserting the union still equals the original — so S2/S3 and S4/S5 have their
distinction available without adding a word. What changes is **binding and direction**, which are structural
properties of where a match sits — not new words.

**S1 · Self-scoped evidence.** An answer whose evidence is a line explicitly labelled with its own
question's label is not review-required merely because some *other* line is unlabelled. This
replaces the all-or-nothing `scoped_lines` test and is what fixes A1–A3.

> ⚠️ **BEFORE BUILDING S2 OR S3, READ THIS — IT IS THE MISTAKE THIS SPECIFICATION IS MOST LIKELY TO
> REPEAT.** `UNSCOPED_NEGATIVE_HEADING` carries a `^` anchor, is compiled **without `re.M`**, and its
> `[^:]*` **spans newlines**. Searching a whole note with it can therefore only ever match the span
> before the note's **first colon**. That is correct where `source_units` uses it — per quote, where
> `^` means the start of that sentence — and silently wrong anywhere else.
>
> The candidate-review release made exactly this error and it reached a signed document: with
> `Indication: screening colonoscopy` above `The following findings are denied:`, the heading became
> invisible and the denied finding was offered for one-click acceptance. The suite's own reference
> case passed, because it had no line above the heading. It failed the other way too — any note with
> `no`, `not` or `never` before its first colon was treated as a negative heading.
>
> **S2 and S3 are ENTIRELY about which lines a marker governs, so every detector they use must be
> applied at the scope its pattern was written for**, and a test for each must include a line above
> the marker and a line below it. An anchored pattern is a claim about position; applying it to a
> larger string silently changes what that claim means.

**S2 · Forward scope.** A line ending in `:`, or matching `UNSCOPED_NEGATIVE_HEADING`, or matching
`INHERITED_SCOPE` on a forward token (`following`, `these`, `those`, `below`, `listed`), governs the
lines **after** it until the next such line or the end of the note. An explicitly labelled line does
**not** end it — `The following findings are denied:` followed by `Symptoms: chest pain` must still
review. (B1 keeps its current outcome.)

**S3 · Backward scope.** `INHERITED_SCOPE` on a backward token (`above`, `listed`) in a line governs
the lines **before** it. (C3 keeps its current outcome, narrowed to preceding fields.)

**S4 · Self-referential modals.** `if`, `would`, `could`, `might`, `hypothetical`, `imagine`,
`suppose` describe the clause they sit in. They govern **their own sentence only**, so an answer
drawn from a different sentence is unaffected. (D1 narrows.)

> ⚠️ **S4 IS THE RISKIEST NARROWING IN THIS SPECIFICATION AND MUST BE BUILT LAST.** These words
> are `SCOPE_REFRAMERS` — the half of the vocabulary that changes POLARITY or ATTRIBUTION rather
> than leaving scope open. The candidate-review release already had to suppress its suggestion
> offer for exactly this half, because the first shape of that feature would have put a one-click
> Accept button under `The following findings are denied:` / `Finding: diabetes`. Three reviewed
> tests written by an earlier refutation pass caught it. **Narrowing a reframer's reach is a
> different and much more dangerous act than narrowing a pointer's**, and S4/S5 should not ship in
> the same release as S1–S3.

**S5 · Quotation.** `QUOTED_SOURCE` governs the unit containing it — reported speech is a fact about
that sentence. (D2 narrows.)

**S6 · Corrections bind by anchoring, and this is the one distinction that does real work.**
`INLINE_CORRECTION` already carries the token `correction`; the same token is read in two positions,
so there is one vocabulary and two anchorings:

- **inline** (`…; correction, X`) — already bound to its own unit via `correction_value`. Unchanged.
- **line-initial** (`Correction: …`) — bound to the field its text names, when it names one; when it
  names none, it is **unbound** and governs the whole note.

Both anchorings now exist in code: `CORRECTION` holds the token once and `INLINE_CORRECTION` and
`LINE_INITIAL_CORRECTION` are built from it. The candidate-review release reads the line-initial
form **only to suppress a one-click offer**, never to widen scope — a refutation lens drove
`Symptoms: no chest pain` / `Correction: the patient reports severe crushing chest pain.` to a
signed Word document in one click. **Suppression is available now; BINDING the correction to the
field it names is the work this specification schedules, and it is a strictly larger claim.**

**S7 · Unbound is whole-note.** Any scope or correction line that cannot be bound by S2–S6 governs
every field, exactly as today. **Narrowing is opt-in per established binding and can only move a
field from `conflict` to `supported` where a binding was positively demonstrated — never the
reverse.** That property is what makes this change auditable.

> ⚠️ **A NOTE ON AN EARLIER CONCLUSION OF MINE, CORRECTED.** While closing the §1e record I wrote
> that no syntactic rule could satisfy both the reviewed test in `test_question_labels.py` (a
> trailing `Correction:` line must flag) and §1e (a trailing `…; correction, …` must not flag other
> fields), because the word "correction" appears in both. **That was too strong.** The two differ in
> anchoring — line-initial versus inline — and `INLINE_CORRECTION` already encodes the inline form.
> S6 separates them without a new keyword. The earlier claim should not be relied on.

---

## 3 · The defect this specification is urgent for

> **C1 · A written correction does not reach the field it corrects, under the contract the owner's
> Word forms use.**

```
Extent of examination: the scope reached the cecum.
Correction: the extent was the splenic flexure.
```

Tab contract, measured today:

```
{'text': 'the scope reached the cecum.', 'status': 'supported'}
```

The superseded value is returned as a supported answer, with no review flag, and it is what
finalization would put in the document. The doctor wrote the correction in plain English in their
own note and nothing carried it.

**This is pre-existing — it is not introduced by Option C** — and it is live for tab-contract forms,
which is what the §1e encounter used. The candidate-review release does **not** repair it: it only
declines to offer a one-click answer when a line-initial correction is present, so the stale value
is still returned as `supported` and still reaches the document if the clinician approves it. The
gap is narrower and it is not closed. Under S6 the expected outcome is that `ext` is held for review
with the correction line as its evidence. It is recorded here rather than repaired in this release
because the repair belongs with the rest of S1–S7 and its own adversarial pass.

---

## 4 · Regression matrix — expected outcomes, declared before implementation

**These expectations are written now, against no implementation.** Any later run is judged against
this table as written; a row that must change is amended here with its reason and date, in a commit
that precedes the run.

Fields, unless a row says otherwise: `ref` = *Referring physician*, `ext` = *Extent of examination*,
`ind` = *Indication for procedure*, each documented on its own labelled line.

| # | note shape | expected `ref` | expected `ext` | expected `ind` | rule | changes today? |
|---|---|---|---|---|---|---|
| R1 | baseline, nothing extra | supported | supported | supported | — | no |
| R2 | `Fictional software test only.` leading | supported | supported | supported | S1 | **yes, legacy** |
| R3 | `Dictated and not read.` trailing | supported | supported | supported | S1 | **yes, legacy** |
| R4 | `Copy sent to the referring office.` trailing | supported | supported | supported | S1 | **yes, legacy** |
| R5 | doctor's own headings, no full stops | supported | supported | supported | S1 | **yes, tab** |
| R6 | `The following findings are denied:` leading | review | review | review | S2 | no |
| R7 | denial heading placed AFTER all three lines | supported | supported | supported | S2 | **yes** |
| R8 | `These are estimates only.` leading | review | review | review | S2 | no |
| R9 | `Correction: the extent was the splenic flexure.` | supported | **review** | supported | S6 | **yes, both** |
| R10 | `…; correction, less than one millilitre.` on its own sentence | supported | supported | supported | S6 | **yes, legacy** |
| R11 | `The extent above should be amended.` trailing | supported | **review** | supported | S3 | **yes** |
| R12 | `Correction: measurement is uncertain.` (names no field) | review | review | review | S7 | no |
| R13 | `If bleeding recurs we would repeat the study.` | supported | supported | supported | S4 | **yes** |
| R14 | `The patient said "it hurts here".` | supported | supported | supported | S5 | **yes** |
| R15 | an answer drawn FROM the quoted sentence in R14 | — | — | review | S5 | no |
| R16 | an answer drawn FROM the modal sentence in R13 | — | — | review | S4 | no |
| R17 | `Correction:` line with no following text | review | review | review | S7 | no |
| R18 | two corrections naming different fields | supported | review | review | S6 | **yes** |
| R19 | a correction naming a field the form does not have | review | review | review | S7 | no |
| R20 | single-line note, one unlabelled sentence, one question | — | — | supported | S1 | no |

### Rows that must NOT move — the existing reviewed expectations

| existing test | why it is here |
|---|---|
| `test_known_prewritten_label_does_not_hide_measurement_or_become_its_evidence` | its trailing `Correction: measurement is uncertain.` names no field → R12/S7 keeps it `conflict`. **This row is the reason S7 exists.** |
| `test_labelled_answer_values` | one unlabelled sentence answering the only question stays supported → R20. The comment at `generation.py:378` records that widening this was tried and reverted. |
| `test_tab_form_policy` | a bare value after a matching label keeps its subject from the label, not from the quote. Untouched: S1–S7 do not change the subject guards. |
| `test_candidate_suggestion` (Option C) | scope-uncertainty answers keep their suggestion. Narrowing scope reduces how often that path is taken; it must not change what it does when taken. |

### How each row is to be judged

Direct calls to `validate_selections` and `validate_tab_selections` with `fixture(...)` selections,
both contracts, every row run under both. **A row that cannot be expressed under one contract is
recorded as not-applicable with its reason — not silently dropped.** No provider call, no network,
no transcription. A positive control accompanies every negative assertion: a row asserting a field
is *not* held must be paired with a row where the same detector *does* hold it, or the assertion can
pass because the detector never ran.

---

## 5 · What this specification does not address

- **Choosing the wrong sentence for a question.** The validator cannot see it; it checks provenance
  and scope, not clinical relevance. `generation.py:381` says so, and it remains true.
- **Headings the form does not know.** S1 stops an unrecognised heading from blanking *other*
  answers. It does not make `EXTENT:` answer a question worded *Extent of examination* — that is
  label matching, a separate piece of work.
- **Live model behaviour.** Everything here judges the validator against fixed inputs. Whether a
  model selects the correction line as evidence is a question for live qualification.
