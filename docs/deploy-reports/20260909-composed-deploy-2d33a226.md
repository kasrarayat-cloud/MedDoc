# §2.5 DECLARATION — the composed deploy of `2d33a226`

**Written and committed BEFORE the deploy. Owner-ruled STRICT**, above what the
script's own logic would require: it is code-only (repo migrations 115 = applied
115), so `declaration_strictness_for_migrations` would keep `present`. The
ruling raises it, so this file is committed first and its timestamp provably
precedes the act.

## THE RANGE — DERIVED, NEVER TYPED

```
PRODUCTION = 123da094003afae9ff481c4f0eb52c33ecff9866
```

Read from the running container's own
`org.opencontainers.image.revision` label — **not** from `origin/main`, not from
a rollback tag's name, and not typed. `git merge-base --is-ancestor` confirms it
is an ancestor of the head, so the range is a well-formed fast-forward.

```
HEAD = 2d33a2261122...   (the merge of #1076)
```

⚠️ **AMENDED BEFORE THE DEPLOY, NOT AFTER — THREE TIMES NOW, AND THE THIRD IS
THE ONE THAT CHANGED THE PAYLOAD.** A peer landed **#1076** while this was
staged: *"the audit gate went red repo-wide — two CRITICAL Next RCEs, eight HIGH
in the docx path."*

**THE CARRY-FORWARD DOES NOT APPLY TO IT.** The ruling permits carrying a
declaration forward from its declared ancestor *if what follows is docs-only*.
`package-lock.json` is not docs — it decides what is inside the image. So the
head moves and the passenger list grows rather than the declaration being waved
through on a technicality.

⚠️ **AND THIS IS THE "OVERTAKEN, NOT OVERRIDDEN" SHAPE, CAUGHT EARLY.** Nobody
bypassed anything: the peer fixed a real vulnerability correctly, this lane
declared a deploy correctly, and the two met in one tree. The only reason it was
noticed is that the range is RE-DERIVED before each attempt instead of being
carried in the head of whoever wrote it down first.

**AMENDED BEFORE THE DEPLOY, NOT AFTER — TWICE PREVIOUSLY.** The first version named
`8cd1705f`. That commit's `CI` came back RED (`gate-265-shellout-budgets`, two
violations only visible once the merges put the files in one tree), the batch
failed as a unit exactly as its own declaration required, and the fix plus the
act's entry point moved the head twice more.

**A declaration naming the wrong commit is worse than no declaration, because it
looks like evidence.** Both amendments are corrections to a PREDICTION made
before the act, which is legitimate; a number adjusted once the outcome is known
is not, and none of the rows below has moved.

⚠️ **THE PAYLOAD IS STRICTLY LARGER THAN THE ITEM THAT PROMPTED THE DEPLOY.**
`main` carries the earlier batch (#1055–#1058) as well as #1066/#1067/#1064. A
declaration naming only #274 would be R5's exact failure — *"I deployed `main`"
is not the same claim as "I judged what I deployed"*, where sixteen true rows
covered a payload none of them could have detected a regression in. So there is
a row per runtime passenger below.

## RUNTIME PASSENGERS — every file that moved, and what it does

| file | passenger | what could go wrong |
|---|---|---|
| `template-twin/visit-metadata.ts` | **#1057** AGE NEVER GUESSES + the newborn-floor fix | an age printed where it should be blank, or blank where it should print |
| `template-twin/resolver/index.ts` | **#272** record-derived refusal never withholds; `fieldDemandsInput` | a required control blocking the whole document again |
| `template-twin/validation/index.ts` | **#272** the second blocking route; shared predicate | a blank that should warn now blocks, or vice versa |
| `template-twin/ir.ts` | typed refusal vocabulary; `fieldDemandsInput` | a refusal token unrecognised at the validator |
| `template-twin/transfer-args.ts` | **#1055** parameterised transfer arg parsing | a guard that should refuse accepting |
| `scripts/transfer-certification-to-active.ts` | **#1055** the transfer tool | a dropped mapping column |
| `template-twin/ingest-plan.ts` | **#274** identity + bijection | a certified disposition on the wrong control |
| `template-twin/ingest.ts` | **#274** the four steps | a partial apply, or an activation nobody asked for |
| `template-twin/create-draft.ts` | `fieldCreateInput` exported | the shared column writer changing behaviour |
| `template-twin/fill-engine.ts` | typed refusal collector | a refusal not reaching the resolver |
| `scripts/regenerate-consult-form.ts` | constants exported; `main()` guarded | the script running on import |
| `scripts/re-issue-form.ts` | **the ruled act's entry point** — #274 shipped the seam without the door | it performs the act; a defect here is the act misfiring |
| **`package-lock.json`** | **#1076 — two CRITICAL Next RCEs and eight HIGH in the docx path** | ⚠️ a dependency bump is a different risk class from the rest of this payload: it changes code nobody here wrote. 178 insertions / 167 deletions. **This is also the strongest reason to ship promptly** — production is currently running the vulnerable tree |

⚠️ **TEST FILES SHIP BUT ARE INERT — MEASURED.** `find /app/apps/transcribe-md/src
-name '*.test.ts'` returns **340** inside the running image, so the fifteen gate
files in this range are technically in the payload. Nothing executes them at
runtime; they are recorded here so the diff and the passenger list reconcile,
and so nobody later reads their absence as an omission.

⚠️ **AND ROOT `scripts/` IS NOT A PASSENGER — MEASURED, NOT ASSUMED.** The range
also moves `scripts/prove-mutation.sh`, `scripts/make-lens-sandbox.sh`,
`scripts/run-ruled-mutation.sh`, `scripts/lib/*` and `.claude/settings.json`.
`docker exec … ls /app` shows the image contains `apps`, `packages`,
`node_modules` and the two manifests — **there is no `/app/scripts`**. Those are
host-side tooling and reach production in no form. Listing them as passengers
would pad the declaration with rows no post-deploy check could ever move, which
is how a declaration stops being read.

⚠️ **NONE OF THESE HAS A LIVE CALLER FOR #274.** `ingestTemplateTwin` is not
invoked anywhere in the tree yet — it is reached only by the ruled act, through
the in-container door. That bounds the blast radius of the newest passenger and
is stated so nobody reads its presence as activation.

## THE DECLARED DELTA

**MUST change: NOTHING BUT THE IMAGE IDS.** This is a code-only deploy.

**MUST NOT change — captured from production BEFORE the act:**

| row | baseline |
|---|---|
| visits | **58** |
| patients | **46** |
| signed visits | **40** |
| note templates | **16** |
| compiled versions | **5** |
| certified versions | **4** |
| field definitions | **238** |
| mappings certified | **238** |
| fill manifests | **5** |

⚠️ **THE CLINICAL ROWS ARE NEVER OMITTED.** A deploy that moves a visit, patient
or signature count has done something nobody asked for, and the only way to know
is to have written the numbers down while they were still true.

**Also MUST NOT change:** applied migrations stays **115**; co-tenant HTTP status
unchanged; no template activated, demoted, certified or de-certified by the
deploy itself.

## HELD DECLARATIONS CROSS-REFERENCED

The re-issue declaration (`docs/foundation/mutations/20260908-re-issue-53-control-form.md`,
committed `2026-09-08T18:28:05Z`) names runtime files that appear in this range —
`ingest.ts`, `ingest-plan.ts`, `create-draft.ts`.

**It is NOT overtaken.** It declares a MUTATION that has not run, and this deploy
is what makes its code reachable. It is judged separately, after this deploy, on
its own act — deferred here **by name**, which is what the rule requires rather
than silence.

## ⚠️ THE ADVISORY ROW — its own judgement, owner-ruled

A dependency bump is code nobody here wrote, so it gets a row of its own rather
than riding in the passenger table.

**BEFORE — read from the RUNNING image, not from a lockfile:**

| package | running (vulnerable) | declared |
|---|---|---|
| `next` | **16.2.11** | **16.3.4** |
| `sharp` | **0.35.3** | **0.35.4** |
| `@xmldom/xmldom` | **0.8.13** | **0.8.15** |

⚠️ **`docker exec … cat node_modules/<pkg>/package.json` IS THE AUTHORITY HERE,
NOT `package-lock.json`.** The lockfile says what a build SHOULD resolve; the
image says what is actually executing. Those have diverged in this repository
before — the `sharp` optional-dependency splice is on record — and the whole
point of an advisory judgement is what is running, not what was intended.

**AFTER — the same three read the same way.** All three must move to the
declared versions. A package that does not move is THE FINDING, whatever the
build log said.

**AND THE MAMMOTH WITNESS:** a `.docx` round-trip fill on the deployed image.

⚠️ **WHY A WITNESS AT ALL:** eight of the HIGH advisories are in the **docx
path**, which is the path this deploy's other twelve passengers all serve. A
version number moving proves the package changed; it does not prove the document
pipeline still works. The witness is the cheap thing that does.

⚠️ **AND IT USES THE BLANK TRACKED FIXTURE, NEVER A PATIENT'S DOCUMENT.** A real
doctor's visit is never a smoke target — not to confirm a deploy, not once. The
fixture is `WM IOV Template.docx`, a customer's BLANK form with no clinical
content, and the round-trip is compile-and-render only: nothing is signed,
adopted or exported, and no visit is touched.

## POST-DEPLOY COMPARISON

Judged against this file and nothing else. **A difference that is not declared
here is THE FINDING**, whatever its explanation sounds like afterwards.
