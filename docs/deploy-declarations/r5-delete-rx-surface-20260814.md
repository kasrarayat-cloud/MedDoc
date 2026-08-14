# §2.5 DEPLOY DECLARATION — R5, delete the Prescription Safety surface

**Owner ruling #109.** Written and committed BEFORE the deploy, so the
post-deploy comparison has one correct answer fixed before the evidence exists.

Branch `feat/r5-delete-rx-surface`. Code-only: **no migration**, no schema
change, no data backfill.

---

## THE HEADLINE, STATED PLAINLY

This deploy **REMOVES A SERVER-SIDE SIGN REFUSAL.** `POST /api/visits/[id]/sign`
no longer returns `422 OVERRIDE_REQUIRED` when a visit carries a critical Rx
warning with no matching override row. That is a real reduction in what the
server refuses. It is a product decision, not a cleanup, and it is written here
in those words so that nobody has to reconstruct it later from a diff.

**Why both halves go together:** the only surface from which a doctor could
clear that refusal was deleted by the same ruling. A refusal with no remedy is
not a safety net — it is an unclearable block, and every affected doctor would
sit at 422 with nothing to click.

## AND IT HAS NEVER FIRED — MEASURED, NOT ASSUMED

Two independent measurements on production, both positive-controlled:

| measurement | value |
|---|---|
| `RX_SIGN_BLOCKED_NO_OVERRIDE` audit rows, all time | **0** |
| production Rx warnings by severity | **65, every one `minor`** |
| visits carrying any Rx warning | 27 |
| visits carrying a `critical` warning | **0** |
| `rx_warning_overrides` rows | **0** |

- **Control for the audit query:** 50 other `RX_*` audit rows exist, so the
  action-name filter is live and the zero is not a broken matcher.
- **Control for the severity query:** the `@>` containment matcher returns `t`
  against a synthetic critical warning, so the zero is not a broken predicate.

**The gate's precondition has never been true on any production visit.** This
deploy therefore changes the sign outcome of **exactly zero** visits, past or
present. That is the argument for shipping it now rather than the argument for
it being harmless in principle — if a critical warning ever appears, the
behaviour change becomes real, and the ruling accepted that.

## AMENDED FOR THE RESTORE — owner ruling on #109, after the adversarial pass

⚠️ **THE NEVER-FIRED MEASUREMENT ABOVE IS STILL THE CENTRE OF THIS DECLARATION.**
The gate removal changes zero visits. What follows is a SECOND change, added
after the refutation pass found that the deletion had over-reached.

**A DELETION IS SCOPED BY WHAT THE COMPONENT DOES, NOT BY WHAT THE RULING CALLS
IT.** The deleted component had two jobs — prescription SAFETY, which #109
names, and the drafted MEDICATION LIST, which it does not. Deleting the whole
thing took the second with it, while the export went on printing a MEDICATIONS
block into the signed PDF, DOCX and EHR clipboard. For one commit a doctor
could have signed a record carrying drug, dose, quantity and refills that
appeared on no screen.

Measured on production, and unlike the gate this population is NOT empty:

| measurement | value |
|---|---|
| visits carrying drafted prescriptions | **17 of 40** |
| …already signed | **13** |
| prescription rows | 53 |
| control — same extractor on warnings | 27, matching the independent count above |

**RESTORED:** a read-only prescriptions display — drug / strength / form, sig,
quantity, refills. No warnings, no severity, no override, no gate, no add /
edit / remove. The safety surface and both gate halves stay deleted.

### ADDITIONAL MUST CHANGE
- `/visits/[id]` pre-sign: a quiet **Prescriptions** card on visits that carry
  drafted medications — and on those only

### ADDITIONAL MUST NOT CHANGE
- **the export is untouched.** `rxSection()`, the PDF and the DOCX emit exactly
  what they emitted before, byte for byte
- no alarm, no amber and no glyph on the restored card — a routine refill must
  not read like an interaction

### TWO OPEN ITEMS, RECORDED HERE RATHER THAN REDISCOVERED
1. **Drafted prescriptions have no edit or remove surface anywhere post-R5.**
   Deliberate; re-opens on first doctor contact. A doctor who edits the note
   text will not see this card follow them — it reads `rxDrafts`, the note is
   `soapFinal`.
2. **Whether the exported MEDICATIONS block should print at all is an OWNER
   QUESTION.** Open, and explicitly not answered tonight.

## MUST CHANGE

- image ids for `transcribe-md` and `transcribe-md-worker`
- `/visits/[id]`: no prescription-safety card, no critical band, no Rx tab
- `/board`: no red lane border, no row tint, no critical tally, no
  `?filter=critical` arm, ordering is newest-first with no critical band
- gate flow: two steps (E/M, attestation) where there were three

## MUST NOT CHANGE

- **every clinical count**: visits 40, signed 25, patients 29, templates 9,
  audit_logs 11360 (monotonic — may only grow), `rx_warning_overrides` **0**
- the E/M confirm gate and the attestation gate — both still refuse
  server-side (`400 ATTESTATION_REQUIRED` unchanged)
- extraction: L7c still drafts prescriptions and warnings; `rxDrafts` still
  populated on new visits
- the EXPORTED note still prints the medication list
- no migration applied; `_prisma_migrations` count unchanged

## MOVING BY DESIGN

- `RX_SIGN_BLOCKED_NO_OVERRIDE` and `RX_OVERRIDE_RECORDED` stop being written.
  Both stay in the Postgres `AuditAction` enum — historical rows reference them,
  and an enum value is not removable by the edit that stops writing it.
- `lib/rx-warning-audit.ts` loses its only caller and is retained deliberately,
  labelled in place. It is tree-shaken out of the shipped bundle; that is
  expected, and the module is retained in SOURCE because the ruling left the
  data's disposition open.

## ROLLBACK

Image tag `:pre-r5-20260814`, tagged from the running digests before promotion.
Flag rollback is NOT available — this is a deletion, not a flag.

## THE FINDING RULE

Any difference not named above is THE FINDING, whatever its explanation sounds
like afterwards.
