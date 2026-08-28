# PIN PROPERTIES, NOT SPELLINGS

**Standing 2026-08-28. Three specimens in one week, all mine, and the third one
held a live tenant-scope defect in place while reporting green.**

> **A source-text gate that asserts an exact SPELLING can lock a defect in place.
> Assert that the count happens, that it filters correctly, and that it is
> practice-scoped — never its shape.**

## The three specimens

| # | the gate asserted | what it actually pinned |
|---|---|---|
| 1 | `expect(src).toContain('res.twinNotice')` | the local receiver NAME. The sibling call site reads `saved.twinNotice` and failed a correct implementation |
| 2 | `/transcribeVisit\.count\(\s*\{\s*where:\s*\{\s*noteTemplateId:\s*id\s*\}/` | the UNSCOPED `where` shape — **the defect itself** |
| 3 | `'practice-scope' in source` | a substring, which matched `practice-scoped` inside a comment |

**The second is the one that matters**, because the first and third produce false
REDS and this one produced a false **GREEN** over a real defect. The gate was
written to protect R1's delete fence. It required the visit count to be spelled

    prisma.transcribeVisit.count({ where: { noteTemplateId: id } })

which is the cross-tenant form. So the guard **demanded** the unscoped read, and
would have failed the correctly-scoped one. A second gate — `gate-practice-scope`'s
ratchet — caught it at 0 → 1, in CI, on the same commit.

## The severity, stated plainly

⚠️ **THE LEAKED NUMBER WAS SPOKEN TO THE DOCTOR.** `transcribeVisit` is a clinical
table, and this count was not merely computed and discarded — it is interpolated
into the refusal message the clinician reads:

    `That format is used by ${referencing} visits and cannot be deleted.`

**Cross-tenant data in a UI string is the finding's true weight**, not the query.
A count that crosses a tenant boundary and stays in memory is a bug; one that is
rendered to a human is a disclosure. Ownership of the *template* was checked
first — deliberately, so a foreign id cannot be probed — and that does not scope
a read of *visits*.

## Why the property form works

The rewritten arm asserts three claims, each of which survives any refactor that
keeps the behaviour:

    expect(body).toMatch(/transcribeVisit\.count\(/);      // it happens
    expect(body).toMatch(/noteTemplateId:\s*id\b/);        // it filters correctly
    expect(body).toMatch(/visitScope\(/);                  // it is practice-scoped

A spelling pin answers *"is the code written the way I wrote it?"* — a question
about the author's memory. A property pin answers *"does the code do the thing?"*
Only the second is a gate.

## ⚠️ AND CI'S RED IS STRONGER EVIDENCE THAN A MUTATION I WOULD HAVE STAGED

The unscoped version's failure was **involuntary**. A mutation proof is chosen by
the author, so it can only test failures the author already imagined — that is
its structural ceiling, and it is why a mutation that passes is weaker news than
it feels. This red was produced by a gate the author was not thinking about,
against code the author believed was finished.

**Keep the involuntary reds.** When CI refuses something you were about to merge,
that is the most valuable single data point in the change, and the temptation is
to fix it quietly and never mention it happened.

## ⚠️ THE ASYMMETRY — A LOOSE-SHAPE PIN IS THE DANGEROUS DIRECTION

**Added after a THIRD specimen, found by sweeping `toEqual({ where:` across every
test file rather than fixing only the one CI named.**

That sweep returned exactly one other site — `deleteMany` pinned at
`{ id, doctorId }` — and it **stays**, which is the point:

> **Pinning a shape that is already maximally tight is close to harmless, because
> the improvement it blocks does not exist. Pinning a LOOSE shape is the
> dangerous direction, because the thing it forbids is precisely the tightening
> somebody will later need to make.**

Doctor scope is NARROWER than practice scope and is what `gate-practice-scope`
explicitly sanctions, so that pin forbids nothing worth doing. Both of the
failures in this entry were the loose kind: each demanded the unscoped form and
would have refused the fix.

**So the sweep is not "unpin every shape."** It is: find the pins that sit on the
loose side of a boundary, because those are the ones holding a defect in place.

⚠️ **AND LET THE TYPE CHANGE DO THE SWEEPING.** Changing `genericHeaderKey` from
`string` to `string | null` made tsc enumerate all three call sites instead of
letting a falsy value slip silently through one of them. A signature change that
forces the compiler to re-check every caller is a better sweep than any grep —
grep finds what you thought to look for, the type checker finds what exists.

## The tell, so this is checkable rather than remembered

**When writing a source-text assertion, ask: "if somebody IMPROVED this code,
would my gate fail?"** If yes, the gate is pinning a spelling. The improvement
that would break it is the one you are forbidding — and in specimen 2 the
forbidden improvement was *scoping a cross-tenant read*.

**Sibling:** [the substring trap](50-the-substring-trap-fourth-sighting-same-family.md)
is the same family one layer down — there the spelling was matched too loosely,
here it was matched too exactly. Both replace a question about behaviour with a
question about text.
