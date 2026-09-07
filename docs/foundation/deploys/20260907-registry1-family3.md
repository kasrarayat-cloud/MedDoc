# §2.5 DECLARATION — the COMPOSED, CODE-ONLY deploy of REGISTRY-1 + family 3

**Written and committed BEFORE the act.** The deploy path's strictness is
`present` rather than `strict` (ruling #96(b)'s logic — strictness is
proportional to reversibility, and a deploy is answerable by a rollback), so a
commit is not demanded here. It is made anyway: this deploy changes what reaches
a clinical document, and a declaration whose answer could have been tuned to the
outcome is worth less than one that could not.

| | |
|---|---|
| range | `2e2d331e` → the merge commit of PR #1050 *(recorded at the act)* |
| what it carries | ruling **#246** (REGISTRY-1, families 1/2/4) **and** ruling **#247** (family 3, both stages), in one act |
| runtime files | **21** |
| **migrations** | **ZERO** |
| schema.prisma | **unchanged** — `git diff --stat origin/main...HEAD` on it is empty |
| passengers | none — every commit in the range belongs to this lane |

⚠️ **THE RANGE IS ONE PR AND THAT IS DELIBERATE.** `feat/registry-1-family3`
contains `feat/registry-1`'s head `bcbb198d` as an ancestor, so merging #1050
lands #1046 too. One merge instead of two: *a merge is a push*, and the second
of two merges four seconds apart is the shape that has cancelled a 33-minute
`e2e` in this repository before. It also means the citation covers exactly the
tree that ships, rather than covering its parent.

⚠️ **NO PASSENGER, MEASURED NOT ASSUMED.** `git log --oneline origin/main..HEAD`
is twelve commits, all from this lane. There is no other author's migration
riding along and no held declaration whose runtime files appear in this range —
so the *overtaken, not overridden* hazard has nothing to overtake here.

---

## WHAT MUST CHANGE

| # | row | expected | what makes it a FINDING |
|---|---|---|---|
| C-1 | `transcribe-md` + `transcribe-md-worker` image ids | **both move** | either unchanged — the deploy did not ship |
| C-2 | `bulkConfirmable` present in the shipped client chunk | **absent → present** | absent after. ⚠️ **canon 131** — this names an EXPORTED symbol, because a local one is renamed by the minifier and the row then measures the minifier. `confirmClassOf` is the pre-existing exported sibling and is the positive control: it must be present BEFORE and after |

## WHAT MUST NOT CHANGE — and the clinical row is never omitted

| # | row | expected | what makes it a FINDING |
|---|---|---|---|
| N-1 | `_prisma_migrations` applied count | **unchanged** | any movement. This deploy carries no migration; a change means something else ran |
| N-2 | `transcribe_visits` count | **unchanged** | any change. A deploy that moves a visit count has done something nobody asked for |
| N-3 | `transcribe_md_patients` count | **unchanged** | any change |
| N-4 | visits with `status = 'SIGNED'` | **unchanged** | any change — a deploy must not sign anything |
| N-5 | `template_twin_semantic_mappings` count, and the count with `mappingStatus='CERTIFIED'` | **unchanged** | any change. Certified mappings are IMMUTABLE and nothing in this range rewrites them; the classifier changes affect only a FRESH proposal |
| N-6 | `template_twin_fill_manifests` count | **unchanged** | any change. A deploy fills nothing |
| N-7 | the ACTIVE note template id and its compiled version id | **unchanged** | any change — activation is a separate ruled act, and it comes AFTER this |
| N-8 | co-tenant HTTP status (`quillmd.com`, `pro.`, `admin.`) | unchanged | a 5xx that was not there before |

## ⚠️ THE JUDGEMENT ROW RULING #225 ADDED, AND IT IS MEASURED AFTER ACTIVATION

| # | row | expected |
|---|---|---|
| J-1 | **the active GI template fills end-to-end** | it does, on the owner's own fresh visit — which is the acceptance this whole arc exists for, and which happens after the re-upload/transfer/re-propose/confirm/certify/activate sequence, not at deploy time |

**J-1 IS NOT DISCHARGED BY THIS DEPLOY AND MUST NOT BE READ AS IF IT WERE.**
See the blast radius below: on the live certified template this code is a NO-OP
until that template is re-certified.

---

## BLAST RADIUS

**Owner's own visits only. Zero patient records written. Ultrasound
byte-identical.**

⚠️ **AND THE HONEST HEADLINE IS THAT NOTHING VISIBLE CHANGES YET.** The three
controls this arc is about — `Referring MD`, `Patient`, `Age` — carry
`sourceType: 'manual'`, `clinicalConcept: NULL` on the ACTIVE certified compiled
version, recorded in
`docs/foundation/mutations/20260903-transfer-certification-to-active.md`.
Certified mappings are immutable on all three write paths, so this deploy
changes what a FRESH classification produces and changes nothing about the twin
in production. The fill path is reached, the new L3 field is extracted, the fact
is minted and travels into the manifest — and all three controls still render
blank until the ruled re-certification sequence runs.

Found by the adversarial pass's stored-artifact lens, and recorded here rather
than left to be discovered when the acceptance rows do not flip.

### THE ONE BEHAVIOUR THAT DOES MOVE FOR AN EXISTING VISIT

`freezeNativeManifestForSigning` now compares the PATIENT ROW's `updatedAt`
against the manifest's. A visit whose patient row was written after its manifest
was produced will **re-fill at signing** where it previously returned
`already_fresh`. That is the intended fix (the document reviewed must be the
document signed), and its cost is one re-fill on the rare path. It cannot cause
a wrong fill: the re-fill is the same code the original fill ran.

| # | row | expected |
|---|---|---|
| B-1 | signed visits whose native manifest is present and verified | **unchanged in count** — re-filling replaces a manifest, it does not create or destroy one |

---

## ROLLBACK

`pre-<sha>-<date>` tags for both images, cut by `deploy-prod.sh` as always.

⚠️ **AND THE CHANGE IS FORWARD-ONLY IN ONE RESPECT, STATED SO A ROLLBACK IS NOT
PLANNED IN IGNORANCE.** A fill manifest written after this deploy can carry
`status: 'record_derived'` and `counts.recordDerived`, and neither parses under
the previous schema (`invalid_value` on the status enum; `unrecognized_keys` on
the `.strict()` counts object). Nothing re-parses a real visit's stored manifest
today — the `manifest` JSON column has zero non-test readers — so a rollback is
survivable, but a manifest produced in the window would be unreadable by the
code it rolled back to.
