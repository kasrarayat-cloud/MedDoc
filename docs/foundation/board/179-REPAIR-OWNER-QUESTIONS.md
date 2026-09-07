# ⚠️ #179 REPAIR — SIX OWNER-CLASS ITEMS, AND ONE OF THEM IS AN AUTHORITY THAT DOES NOT EXIST

**Filed 2026-09-07 by the custom-file session, from ruling #190's owed fan-out
and an eleven-lens investigation over its findings.** Every claim below is
measured, with the command beside it. Nothing here is decided; each item is
surfaced with the reasoning attached, per the standing-authority table.

**None of these blocks the repair.** The recommended fixes are chosen so the
work proceeds under a stated assumption and the owner's answer changes a
declaration, not a rebuild. Where an item *does* gate something, it says so.

---

## ⚠️ 1 · `#179(6)` IS CITED AS THE AUTHORITY FOR A CLINICAL MATCHING RULE, AND IT HAS NO CONTENT — class (a)

`validation/index.ts:221` states:

> *"⚠️ AND A NULL MAPPING TEMPORALITY MEANS `current`, NOT `any` — #179(6)."*

**That part number has no recorded content anywhere.** Measured, with a control
that discriminates:

| token | files in the ledger (head + every archive) | hits |
|---|---|---|
| `laterality` | 3 | **17** |
| `scaffolded` | 7 | **36** |
| `unmentionedPolicy` | 6 | **11** |
| `conceptScope` | 2 | **3** |
| **`temporality`** | **0** | **0** |

`grep -ril <token> docs/foundation/RULINGS.md docs/foundation/rulings/` — the
instrument works, and the zero is real. **`temporality` appears in no ruling, in
any file, ever.** It is also 0 in #179's own body on this branch.

⚠️ **AND #179's BODY SAYS SO ITSELF**, at `docs/foundation/rulings/2026-09-04.md:346`:

> *"Parts **4** and **6** are not described here because this session was not
> given their content. An empty row is honest; a plausible one written to make
> the table look complete would be a fabrication wearing a ledger's authority."*

That honesty is exactly right, and it is what makes this visible. **Then code was
built on part 6 anyway** — `#179(6)` is cited 3 times in shipped source, 5 with
its `(6a)`/`(6b)` sub-parts.

**THE QUESTION: did you rule that a null mapping temporality means `current`?**

It matters because the two readings produce **opposite documents from the same
dictation**:

- `any` (main, and the resolver and bridge on this branch) — a dictated
  *"history of hypertension"* FILLS a Past Medical History field.
- `current` (the validator on this branch) — the same dictation makes the
  validator reject the resolver's own citation, and **the doctor's Word document
  is not produced at all**.

**What I am doing meanwhile, and why it is safe:** restoring `any` everywhere —
main's proven behaviour, which loses nothing anyone currently has — and removing
the citation rather than keeping a rule whose authority cannot be produced. If
you did rule (6), the correct implementation is **not** the one on this branch
either: it belongs as an explicit `temporality: 'current'` on the ROS scaffold
clause mappings, which achieves *"denies chest pain must not be satisfied by 2019
chest pain"* without touching every other field in every template.

---

## 2 · THE CAPABILITY THAT CHANGES HANDS ON THE TEMPORALITY AXIS — class (b)

If you confirm (6) in any form, somebody loses something. Measured end to end
through the real chain, mapping temporality null + fact historical + concept
matching:

| | outcome |
|---|---|
| `origin/main` | field **FILLED**, document renders |
| this branch | field filled and cited, then **WHOLE DOCUMENT WITHHELD** (`renderer.ts:94-98`) |
| after the recommended fix | field **BLANK** with reason `temporality_not_approved`, document renders |

**Blank-and-rendered is better than withheld and worse than filled.**

⚠️ **NOT REACHABLE IN PRODUCTION TODAY, AND I CORRECTED MYSELF ON THIS.** I first
reported *"every PMH and family-history field on every template"*. That is
**wrong**: 0 of 185 prod certified mappings can reach it — all 20 PMH/FH rows
declare `historical` explicitly, and all 11 null rows are `sourceType='manual'`,
which returns before any citation. **Filing it my way would have had somebody
hot-fixing a defect production does not have.** It is live in QA (29 of 57
compiled versions) and it breaks **every template's own certification self-test**,
because `verification-encounter.ts:356` dictates *"History of present illness…"*
and that phrase is stamped historical by the regex at `encounter-facts:239`.

---

## 3 · A MACHINE TOKEN PRINTS INTO YOUR SIGNED DOCUMENT — class (a)

A ROS narrative control renders the raw lexicon token — `early_satiety`,
`night_sweats`, `suicidal_ideation` — as `status=supported`, `valid=true`, **0
issues**. **72 tokens across 13 systems, 25 of them containing underscores.**

⚠️ **CORRECTED BASELINE, so it is not read as a regression:** at the merge base
no ROS fact could fill anything, so this diff **opens the path and tokenises the
value in one change**. Denials are unaffected.

**THE QUESTION: how should a symptom be worded in your form?** The doctor's own
word survives in the fact's evidence quote, so three answers are available —
render the quote, render a display map (`early_satiety` → *"early satiety"*), or
preserve the original at the schema seam. **How a finding is phrased in your
document is plausibly yours to say, not ours.**

---

## 4 · AN `Other:` ROS ROW WOULD PRINT THE LITERAL WORD "other" — class (a)

Related to 3 but a distinct decision. A symptom outside the closed list becomes
`other`, which is **deliberate and ruled** — #179's body says an outside symptom
*"must not be silently dropped"*. But if your form has an `Other:` row, today it
renders the string `other` rather than what the patient said.

---

## 5 · MAY THE MODEL PROPOSE A CONCEPT SCOPE? — class (a), two rulings pull opposite ways

- **#193** — the model schema OMITS a field the model must not author, because
  `ModelSemanticMappingSchema` extends the base schema and silently hands new
  fields to the model. Measured then: **11 of 11** proposals returned `keep` and
  a control printed *"Enter assessment"* into a note.
- **#179(3)**, written after it — the concept scope is *"proposed from the
  sentence's own words by the mapping proposer"*, i.e. **by the model**.

`conceptScope` is today a settable field on the mapping model's tool schema,
unmentioned in the prompt and unvalidated — the #193 shape exactly. ⚠️ **It is
latent, not live**: the value is dropped at all five persistence boundaries and
there is no column, so nothing reaches a document today.

---

## 6 · THE 53-CONTROL FORM IS GONE, AND I REBUILT IT — class (c)

**The form does not exist on this machine.** The only `.docx` here with more than
30 content controls is your 35-control original.

⚠️ **My first probe returned a FALSE ZERO** — written `for f in $(find …)`, it
word-split on the filename's spaces and reported *no form above 30 controls*
while looking straight at one. The null-delimited probe is what answers.

**It is mechanically derivable, and I rebuilt it**: 35 existing + 6 ROS clauses
(your GI-ROS paragraph is exactly six sentences) + 10 exam clauses + the
telehealth line + a second total-time render = **53**. All 18 edits assert their
own application.

**It compiles, through the shipped compiler, to exactly `fields=53
scaffolded=53 unsupported=0`** — reproducing the measurement recorded in
`compiler.ts:344` of the lost original.

⚠️ **BUT `kept_default` IS PROVED BY BYTE-IDENTITY**, so a reconstruction
differing by one space is a different document, and the clause boundaries inside
your ROS paragraph are **my reading of your prose**. **THE QUESTION: accept the
reconstruction, or re-upload your file?** Re-uploading settles it
authoritatively; nothing else can.

---

## ⚠️ AND ONE LEDGER CORRECTION I AM MAKING, NOT ASKING

`docs/foundation/rulings/2026-09-04-eleven-row-acceptance.md` still closes by
instructing the transfer to declare `unmentionedPolicy: 'keep'` on the six ROS
and ten exam controls, *"or rows 4, 5 and 6 cannot flip"*.

**Ruling #194 abolished `keep` entirely** — the policy collapsed to
`NULL | 'omit'`, with no `'keep'` value anywhere and `default_kept` retired. A
session following that tail today would build against a value the schema no
longer has. The correct form is **`omit` on telehealth only**, with rows 4 and 5
satisfied by the REVIEW-DEFAULTS human act. The amendment is appended and dated
rather than overwriting the superseded wording.
