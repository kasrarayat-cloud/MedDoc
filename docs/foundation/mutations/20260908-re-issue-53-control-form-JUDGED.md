# JUDGEMENT — THE RE-ISSUE OF THE 53-CONTROL CONSULT FORM

**Act executed 2026-09-09T15:41:16Z through `scripts/run-ruled-mutation.sh
--in transcribe-md-worker`, under
`docs/foundation/mutations/20260908-re-issue-53-control-form.md`.**

    declaration committed : 50d00ca29327 at 2026-09-09T06:13:39Z
    act starting at       : 2026-09-09T15:41:16Z      <- 9h27m LATER
    container revision    : 4e4d8e7c…  ==  this tree's HEAD
    exit                  : 0

The commit time and the start time bracket the rows in the units the rows carry.
Every quantity below was fixed before the evidence existed.

## VERDICT — 🟢 **11 of 11 declared rows hold.** And one difference the
## declaration does not name, which is therefore the finding. It is below, and
## it is the OWNER'S to settle.

## ⚠️ FIRST: THIS ACT HAD ALREADY RUN ONCE, AND REFUSED

Judging production against the declaration before touching anything found
**zero** twin rows of any kind created after the declaration's commit — no
artifact, no compiled version, no field definition, no mapping, no
certification, no note template. The earlier attempt refused with

    TRANSFER_COUNT_MISMATCH  expected 43  actual 20

and wrote nothing, exactly as designed. The repair (#1087) was on `main` and
**not deployed**, so the runner's revision check would have refused the act
again — correctly, because a container carries the repository as of its build.
**The first unsatisfied post-condition was therefore the DEPLOY, not the act**,
and the deploy is judged in
`docs/foundation/deploys/20260909-7445308b-JUDGED.md`.

## MUST CHANGE

| row | declared | observed | |
|---|---|---|---|
| note templates for this practice | N → N+1 (8 → 9) | **9** | 🟢 |
| compiled versions | M → M+1 (5 → 6) | **6** | 🟢 |
| the new version's field definitions | 53 | **53** | 🟢 |
| its mappings `CERTIFIED` | 43 | **43** | 🟢 |
| its mappings NOT certified (re-proposed) | 10 | **10** | 🟢 |
| the new template's `status` | `draft` | **`draft`** | 🟢 |

    new note template   3877d5cf-ad03-4412-a322-6be0c7dcb3ff   (draft)
    new compiled ver    d2120cdd-74ae-43a3-85a3-1f185401e202   (NEEDS_CONFIRMATION)
    new artifact        89988a27-4165-4e59-8bc3-6517d74477bb
    source sha256       5367fd07…  (the pinned artifact, unchanged)

## MUST NOT CHANGE

| row | declared | observed | |
|---|---|---|---|
| the certified version's rows | not one | **53 fields / 53 CERTIFIED**, `max(updatedAt)` = 2026-09-07T08:55:31Z — **predates the act by two days** | 🟢 |
| `template_twin_fill_manifests` | 0 touched | **5**, `max(createdAt)` still 2026-09-04 | 🟢 |
| **visits** | unchanged | **58** | 🟢 |
| **patients** | unchanged | **46** | 🟢 |
| **signatures** | unchanged | **40** | 🟢 |
| nothing activated | — | active is still `939aa9ea` (the OLD template) | 🟢 |
| nothing certified | — | certifications **4**, `max(certifiedAt)` still 2026-09-07 | 🟢 |

## ⚠️ THE RECORDED MEASUREMENT — THE PREMISE IS SETTLED, AND IT IS 53

    w:tag attributes on the artifact : 53
    w:sdt controls on the artifact   : 53
    xml parts inflated and scanned   : 13
    declared expectation             : tagged >= 18

**The ruling's claim was right and the repository's derivation was an
undercount.** What was verifiable from the repository alone was 18 — the
controls `regenerate-consult-form.ts` adds — and the declaration recorded, in
advance, that *"53 makes TAG-ON-INGEST narrower, 18 makes it wider"*.

It is **53**. TAG-ON-INGEST is the narrower of the two designs. The premise was
load-bearing and unverified for weeks; it is now a fact with a number, taken by
an instrument that inflates the package first — a regex over the raw `.docx`
buffer would have answered ~0 and "settled" it with a fabrication.

⚠️ **AND THE NEAR-HOMOGRAPH IS WORTH KEEPING NAMED:** the provenance record's P3
proof says *"`w:sdt` tags balanced"*, which is XML NESTING, not `w:tag`
attributes. It reads like confirmation of this number and is not. That both
happen to be 53 here is a coincidence of this document, not a relationship.

## ⚠️ THE FINDING — A DIFFERENCE THE DECLARATION DOES NOT NAME

The declaration fixes the COUNT of re-proposed rows (10) and says nothing about
their CONTENT. The content is a change of kind, and it is the owner's to settle.

**All ten rows that were `manual` are now proposed as MODEL-FILLED.**

| | source `18a7ae19` | new `d2120cdd` |
|---|---|---|
| `extraction` | 43 CERTIFIED | 43 CERTIFIED + 7 RECOGNIZED + 1 NEEDS_CONFIRMATION |
| `manual` | **10 CERTIFIED** | **0** |
| `visit_metadata` | 0 | **2 RECOGNIZED** |

| field | was | now proposed as |
|---|---|---|
| Referring MD | `manual`, no concept | `extraction` → `visit_metadata.referring_physician` |
| Patient | `manual` | `visit_metadata` → `visit_metadata.patient_name` |
| Age | `manual` | `visit_metadata` → `visit_metadata.patient_age` |
| Past Surgical History ×3 | `manual` | `extraction` → `past_surgical_history` |
| Marital status | `manual` | `extraction` → `social_history.marital_status` |
| **Telehealth consent** | `manual` | `extraction` → **no concept**, NEEDS_CONFIRMATION |
| **Total minutes spent with patient** | `manual` | `extraction` → `total_time_minutes` |
| **Total time minutes** | `manual` | `extraction` → `total_time_minutes` |

`manual` means *"a per-visit human value; renders blank; attested"*. `extraction`
means *"the model fills it from a cited fact"*. **Confirming these as they stand
would convert ten fields the doctor fills by hand into fields the model fills** —
including a telehealth CONSENT line and two TOTAL-TIME fields, which are an
attestation and a billing quantity respectively.

**The act is correct.** The declaration says the transfer carries the 43 and
re-proposes the 10, and it did precisely that; re-proposal means the model
proposes afresh, and it proposed. Nothing is certified and nothing is active, so
nothing has reached a document. This is exactly the confirmation step the
declaration reserved for the owner.

⚠️ **AND A REMEMBERED CLAIM THAT WOULD HAVE MIS-READ THIS WAS CHECKED AND IS
NOW WRONG.** The record said four of these concepts were REFUSED by a closed
registry. Measured with `isRegisteredConcept` — the instrument, not a grep:

    true   visit_metadata.referring_physician      true   past_surgical_history
    true   visit_metadata.patient_name             true   social_history.marital_status
    true   visit_metadata.patient_age              true   total_time_minutes
    false  visit_metadata                          <- bare, correctly still refused

**The registry has been opened for all six since.** So these are registry-valid
proposals, not spurious ones — and the question in front of the owner is a
clinical one about `manual` vs `extraction`, not a technical one about the
registry.

⚠️ **ONE ROW IS UNMAPPABLE AND SAID SO ITSELF**, which is the proposer behaving
correctly: `[template-twin:mappings] 1/53 proposals were off-registry or
unconcepted and are left unconfirmed: ttf_86cf11d77e63d9e64a6b045b` — the
Telehealth consent line. It carries **no concept** and sits `NEEDS_CONFIRMATION`.
The standing rule is that an unmappable field is `manual`.

⚠️ **AND TWO ROWS PROPOSE A RESERVED SOURCE TYPE.** `schema.prisma` documents
`visit_metadata` as *"RESERVED, unimplemented until the flagged
review-before-sign lane exists"*. Patient and Age now propose it. Certifying
them would bind two controls to a lane that does not exist yet.

## WHAT HAPPENS NEXT — AND WHAT MUST NOT

The new template is a **DRAFT**. The owner confirms the rows; certification and
activation are separate ruled acts with their own declarations. The old template
stays **active** until then and is demoted, never deleted, because the five
frozen fill manifests point at what they were filled against.

**Recommendation, offered and not taken:** the eight rows that were `manual` and
carry a clinical or billing attestation — Telehealth consent, both Total-time
fields, and the three Past Surgical History controls — should stay `manual`
unless the owner says otherwise. Patient, Age and Referring MD are the arguable
ones, and they are the two proposing a RESERVED source type plus one that is
genuinely visit metadata.
