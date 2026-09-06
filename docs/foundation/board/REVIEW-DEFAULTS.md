# BOARD FILING — REVIEW-DEFAULTS (Design/Admin)

**Filed 2026-09-05 by the custom-file session, per owner rulings #194 (item 4)
and its round-four rider.** Sequenced **after** the custom-file batch's 🟢.

## WHY IT EXISTS

Ruling #194 deleted the `keep` half: **the machine never prints an undictated
default.** The doctor's own defaults do not disappear — they become a **human
act at review**, where the click is the assertion.

## ITEM 1 — INSERT MY DEFAULT

On the pre-sign review, every **blank scaffolded control** shows its compiled
`scaffoldText` with an **"Insert my default"** control, plus **"Insert all my
defaults"** with the list shown.

- the click is the **doctor's assertion**, audited as
  `DEFAULT_INSERTED_BY_DOCTOR`;
- it fills through the **normal human-typed path** — not a new writer;
- speed is preserved; the claim is the doctor's.

**The resolver side is already built and shipped in PR #999:** `scaffolded` and
`scaffoldText` are carried in the compiled IR, **outside `structureSha256` and
outside `assertSourceMatchesIr`'s comparison** — a moved structure hash orphans
every certified twin, measured once at 10 of 10.

⚠️ **THE HUMAN-FILL PROOF KIND IS NOT PRE-BUILT, DELIBERATELY.** A proof kind
with no emitter is #170's defect, and it is the exact shape this whole arc was
about: `default_kept` shipped that way and cost three adversarial rounds. It
lands **with this feature's emitter, in the same commit**, or not at all.

## ITEM 2 — `omit` NEEDS A PRODUCT SURFACE

**Measured after #194:** `grep -c unmentionedPolicy` over every `.tsx` is
**zero**. The model schema omits the field; the proposer no longer sets it; both
writers persist `mapping.unmentionedPolicy ?? null` from payloads that cannot
carry it.

> **So `'omit'` — the only surviving policy — can be written by a ruled mutation
> and by nothing a doctor can reach.**

The custom-file transfer sets it directly for the owner's telehealth line, so
his form is served. **A second doctor cannot choose it at all.**

The confirm-list / settings row gains **"omit this line when not dictated"**
beside "insert my default", so a doctor can choose what the transfer writes
today.

⚠️ **AND `omit` IS THE HALF THAT SURVIVED THREE ADVERSARIAL ROUNDS**: it clears
through the proven bounded clear, carries its own reason token, earns a
byte-verified `emptied` proof, and is counted in its own `omitted` bucket so it
is neither reported as undictated nor silently lost. The mechanism is sound; it
has no door.

## WHAT NOT TO REBUILD

The `keep` half. Six formulations of its mechanism were falsified and then its
premise was: it fired when **no fact carried the field's concept**, and concept
equality is the only test this pipeline performs, so *"nothing dictated
contradicted this"* was always a claim about the empty set. Full account in
`docs/foundation/rulings/2026-09-05-194.md`.
