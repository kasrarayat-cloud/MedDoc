# A SPEC CAN BE FALSIFIED BY THE VERY RULING THAT WROTE IT

**Ratified 2026-08-27.**

> **When an order names a QUANTITY and also requires WORK, the work can move the
> quantity. The order is then wrong about itself — and it was right when
> written.**

⚠️ **REFERENCE CASE.** Ruling #153 discharged F8's park and scoped its deploy in
one instruction. Clause (g) said, in as many words:

> *"migration **107 → 108** with the **three** permanent enum labels NAMED as the
> irreversible clause"*

Measured against the deploy target, it was **107 → 109** with **four** permanent
labels.

**The ruling did not err. Its own requirement produced the difference.** #153
carried #148(e)'s re-arming condition — *the refusal audit is owed IN THE SAME
CHANGE* — and the slice honoured it by shipping a second migration,
`20260827120000_f8s2_icd_refusal_audit`, adding `ICD_CODE_DECISION_REFUSED`. The
order was written before that slice landed. **It was accurate at the moment of
writing and false by the time it was executed, because of what it asked for.**

## WHY THIS NEEDS ITS OWN ENTRY

It is not staleness in the ordinary sense. A stale figure is one nobody
refreshed. **This figure was invalidated by the correct execution of the
instruction that contained it** — so the more faithfully the order is carried
out, the more wrong its own numbers become.

⚠️ **AND THE FAILURE MODE IS OBEDIENCE.** The tempting move is to make the
measurement match the order — to write `107 → 108` because that is what the
authorising ruling says, and to treat the third label as a rounding error. That
produces a **false declaration**, which is the one artifact §2.5 exists to
prevent, arrived at by deference.

> **AN ORDER'S QUANTITIES ARE A SNAPSHOT. ITS INSTRUCTIONS ARE THE AUTHORITY.**
> Execute the instructions; **re-measure the quantities**; report the difference
> and why it moved. *"A difference that is not in the declaration is THE
> FINDING"* applies to differences the declaration's own author introduced.

## THE PRACTICE

- Before acting on an order that names numbers, ask: **does this order also
  require work that could change them?** If yes, they are inputs to re-measure,
  not facts to copy.
- Re-measure against the artifact the act will touch, and **name the delta in
  the same breath as the act** — not as a correction afterwards.
- **Say plainly that the order was right when written.** A correction that reads
  as "the authority was wrong" invites re-litigation of a decision that was
  sound; a correction that reads as "the authority's own requirement moved this"
  invites nothing, because it is simply what happened.
