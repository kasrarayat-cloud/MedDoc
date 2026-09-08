# §2.5 DECLARATION — the composed deploy of `8cd1705f`

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
HEAD = 8cd1705f2bb57426c324119cb3c0bac179971749   (52 commits)
```

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
| `.claude/settings.json` | grants for `prove-mutation.sh` | not runtime; recorded for completeness |

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

## POST-DEPLOY COMPARISON

Judged against this file and nothing else. **A difference that is not declared
here is THE FINDING**, whatever its explanation sounds like afterwards.
