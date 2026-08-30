# JUDGEMENT — THE ANNOTATION ACT

**Judged 2026-08-30T04:23:44Z.** Declaration
`docs/foundation/mutations/20260830-annotation-act.md`, committed
`2026-08-30T04:21:15Z`; the act began `04:21:28Z` — **13 seconds later, and
provably after**, which is the whole product of the ruled-mutation gate.

**11 declared rows. 11 matched.**

## MUST CHANGE — 4 of 4

| quantity | declared | measured | |
|---|---|---|---|
| `audit_logs` | 11,962 → **12,001** | **12,001** (+39) | ✅ |
| `EM_OMITTED_IN_SIGNED_ARTIFACT` rows | 0 → **10** | **10** | ✅ |
| `TEMPLATE_PROVENANCE_LOST` rows | 0 → **29** | **29** | ✅ |
| distinct visits touched | **38** | **38** | ✅ |

`INSERT 0 10` and `INSERT 0 29` in one transaction. **39 rows, 38 visits** — the
overlapping visit received two rows because it carries two distinct facts.

## MUST NOT CHANGE — 7 of 7, and this is #155(a) made checkable

| quantity | measured | |
|---|---|---|
| visits | **51** | ✅ |
| signed visits | **34** | ✅ |
| patients | **40** | ✅ |
| note_templates | **11** | ✅ |
| CERTIFIED twins | **1** | ✅ |
| `em=null` + scored + SIGNED | **10** | ✅ |
| NULL `noteTemplateId`, servable | **29** | ✅ |

⚠️ **THE TEN SIGNED RECORDS ARE UNTOUCHED, AND THAT WAS THE POINT.** #155(a) ruled
they stay as signed; this act made the gap visible **without moving a byte**.
`em=null` is still 10 — the same ten — and not one signed artifact changed.

## THE PAIRED SEAL IS CLOSED

| act | claim about `audit_logs` | judged |
|---|---|---|
| migration deploy `36ad23ce` | writes **ZERO** rows bearing the five new labels | **0** ✅ |
| this act | writes exactly **+39**, all label-bearing | **+39** ✅ |

*A quantity shared across consecutive acts, declared in both directions.* Neither
act could have written out of band without the other's row contradicting it.

## WHAT THE ROWS REFUSE TO SAY

    "originalTemplate": "not identifiable — no deletion audit row was ever written"
    "destructionWindow": "2026-07-07..2026-08-27"
    "retrospective": true

**No inferred id.** Measured before writing: 9 template-targeted audit rows exist
and every one is `TEMPLATE_TWIN_*`; none is a deletion. The id is genuinely
unrecoverable, so the row says that instead of a plausible guess.

## IDEMPOTENCY — PROVED ON THE LIVE TABLE, NOT ARGUED

A second `--apply` wrote `INSERT 0 0` twice; `audit_logs` stayed at **12,001**.
An append-only table has no undo, so this is proved rather than asserted.

⚠️ **AND THAT PROOF FOUND A DEFECT IN THE VERIFIER ITSELF.** The success check
required a delta of exactly 39 — correct on the first run, **wrong on every
idempotent re-run**, where the correct delta is 0. It printed 🔴 for correct
behaviour. **A false red teaches people to ignore reds**, which is the same damage
as a false green, arriving from the other side. Rewritten to assert the END STATE
(10 + 29 rows, 38 visits) — the invariant that holds on both runs — and re-run
green.
