# A COUNT IS A DERIVATION, NOT A CLAIM TWO SIDES CAN BOTH BE RIGHT ABOUT

**Standing 2026-09-08, from a merge conflict that had exactly one correct answer
and two plausible-looking wrong ones.**

This house resolves ledger and schema conflicts as **UNIONS**: when both sides
describe things that ACTUALLY HAPPENED — a migration that ran, a row that
landed — the answer is always both, and "take theirs" silently deletes work.
That rule is right and it has a boundary nobody had written down.

> **A COUNT IS NOT A UNION AND IT IS NOT A CHOICE. It is a function of the thing
> it counts, and after a union it is USUALLY NEITHER SIDE'S NUMBER.**

---

## THE REFERENCE CASE

`docs/canon/INDEX.md` carries a header: *"N entries live in full at
`docs/canon/`."* A merge produced:

```
<<<<<<< HEAD
**171 entries live in full at `docs/canon/`.**
=======
**181 entries live in full at `docs/canon/`.**
>>>>>>> origin/main
```

Both numbers were true of their own side. The row hunk below it was a genuine
union — 1 entry from one branch, 11 from the other — so the merged file had
**182**.

⚠️ **TAKING EITHER SIDE WOULD HAVE BEEN RED, AND NOT OBVIOUSLY.**
`gate-agents-md-size` recomputes the count from the rows themselves
(`expect(Number(claim[1])).toBe(rows.length)`), so a picked number fails; a
derived one is the only green. **Nothing about the conflict marker suggests
that** — it looks exactly like every other two-sided disagreement, and the
union habit is strong enough to carry a reader straight past it.

The same shape recurred one file over the same day: `RULINGS.md`'s *"N
rulings"* line, and its archive census *"4 archives · 369,216 chars · largest
106,835"* — three numbers, none of which either branch held after the union.

---

## THE RULE

> **When a conflict hunk contains a NUMBER, do not resolve it. RE-DERIVE it from
> the merged content, using the same expression the gate uses.**

And the corollary that makes it operational:

> **If nothing re-derives it, that is the finding.** A count nobody computes is
> a claim wearing a measurement's clothes, and it will be wrong the first time
> anything is added on two branches at once.

---

## HOW TO TELL A COUNT FROM A FACT

The union rule and this one do not conflict; they apply to different cells.

| the cell | resolution |
|---|---|
| *"#246 — REGISTRY-1 ratified"* | **UNION.** It happened. Both sides' rows are facts |
| *"a migration added 2 audit actions"* | **UNION.** It ran |
| *"130 rulings"* · *"4 archives"* · *"182 entries"* | **DERIVE.** It is a function of the rows, and the rows just changed |

⚠️ **THE TELL IS WHETHER THE VALUE HAS AN INDEPENDENT EXISTENCE.** A ruling
happened whether or not anyone wrote it down. A count exists only as a statement
about a set — change the set and the old number is not a competing opinion, it
is stale.

---

## WHY IT IS FILED WITH THE UNION RULE AND NOT INSIDE IT

Because the union rule's own justification — *both sides describe things that
actually happened* — is TRUE of both numbers and still yields the wrong answer.
The reasoning that makes unions correct is exactly the reasoning that makes this
mistake, which is why it needs its own name rather than a footnote.

---

## RELATED

- **LEDGER AND SCHEMA CONFLICTS RESOLVE AS UNIONS** — the rule this bounds.
- **A CONTROL CAN PASS VACUOUSLY** — the same family: a number that is never
  recomputed cannot disagree with anything.
- **#278** — the ledger's shape; the conversion that surfaced all three counts.
