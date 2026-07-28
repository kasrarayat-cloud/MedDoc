# Prod imaging E/M override — purge record (the sixth artifact)

**When:** 2026-07-28T17:20Z · **Database:** prod `meddoc`
**Scope:** the `em` key of `cptCodes` on ONE unsigned imaging visit. Nothing else.
**Order:** the export-layer guard shipped FIRST, so the value was already
suppressed in every artifact before this cleanup ran.

## Why this one was separate

The five rows purged earlier held `emScoredCode` — a computed baseline. This row
held `cptCodes.em.override.code = 99212`: a **doctor-set** code, recorded through
a surface the specialty-label bug wrongly exposed on imaging visits. Clearing a
recorded clinical judgement is a different decision from clearing machine residue,
which is why the standing check classifies the two rather than sweeping both.

Ruling: unsigned, on the operator's own synthetic account, and the append-only
audit trail preserves the historical record of the original override.

## Guard

```
NOTICE:  guard passed: exactly 1 unsigned imaging row carrying an em key
```

Predicate: `id = 'cms3k19d2001801mkyarrlq57' AND "signedAt" IS NULL AND
specialty = 'ultrasound' AND "cptCodes" ? 'em'`. Abort on any count but 1.

## Before → after

| | value |
|---|---|
| before | `{"em": {"override": {"code": "99212", "overriddenAt": "2026-07-27T20:48:15.183Z"}}}` |
| after | `{}` |

`UPDATE 1`, `INSERT 0 1` (audit). The `em` KEY was stripped, not the column —
`cptCodes` carries procedures and modifiers on other visits, and that must hold by
construction rather than by luck.

### Blast radius

`status=READY`, `soapVersion=1`, `emStale=false`, `emScoredCode=null`,
`icdCodes=present`, `soapFinal` length 3499 — all unchanged. Still unsigned.

## Audit trail

```
cms3k19d2001801mkyarrlq57  EM_LEVEL_CHANGED  from=99212  field=cptCodes.em
removed={"override": {"code": "99212", "overriddenAt": "2026-07-27T20:48:15.183Z"}}
```

`cause: 'operator_remediation'`, `userId` NULL (not the doctor's action), the full
provenance in `metadata.reason`, and `metadata.removedBlob` preserving exactly
what was taken out — so the row can be reconstructed from the audit log alone.

## Acceptance

```
$ bash scripts/check-imaging-em-artifacts.sh
🟢 imaging E/M invariant holds on prod — 0 of 13 imaging visits carry office E/M state
exit=0
```

The invariant now holds at all three layers — compute, store, export — and on the
production data.
