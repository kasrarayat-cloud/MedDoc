# A DOUBLE WITH FEWER METHODS THAN THE CLIENT MAKES THE WRONG CHOICE THE ONLY CHOICE

**Standing 2026-09-08, from a 500 on every admin suspend that a full unit suite
could not see.**

A test double is usually judged on what it RETURNS. This entry is about what it
OFFERS: the set of methods it exposes, and what that set forbids the code under
test from doing.

> **When a double implements fewer methods than the real client, the code cannot
> choose the method the double lacks. Every arm then passes — not because the
> choice was right, but because no other choice was reachable.**

The double stops being a stand-in and becomes a CONSTRAINT, and the constraint is
invisible: nothing in the arm mentions the missing method, so nothing in the
failure — when it finally arrives somewhere else — points back here.

---

## THE REFERENCE CASE

`withPracticeLock` took a Postgres advisory lock with `tx.$queryRaw`.
`pg_advisory_xact_lock` returns **`void`** (asserted from
`pg_get_function_result`, not assumed), and `$queryRaw` must DESERIALIZE the row
it gets back. It cannot deserialize a void column, so the call threw and the
route answered **500** on the ordinary suspension of a solo owner.

**Every unit arm was green.** The double was:

```ts
const txAt = (level: string) => ({
  $queryRaw: vi.fn(async () => [{ level }]),
});
```

One method. The helper *could not* have called `$executeRaw` under test —
TypeScript would have refused, and the arm asserting "the lock was taken" was
satisfied by the only call available. `e2e` caught it against a real database.

⚠️ **AND THE REPOSITORY ALREADY HELD THE ANSWER**: `billing-charge.ts:453` takes
its advisory lock with `$executeRaw*`, for exactly this reason, one package over.

---

## THE RULE

> **A double carries EVERY method of the real client that the code under test
> could plausibly reach — especially the ones you expect it NOT to use.**

Then add the arm that only becomes possible once it does:

> **Assert WHICH method was called, not merely that something was.**

```ts
expect(probes.length, 'the isolation probe was not a query').toBe(1);
expect(locks.length,  'the lock was never issued, or was issued as a QUERY').toBe(1);
```

⚠️ **THE TYPE SYSTEM IS THE CHEAPEST HALF OF THIS.** Widening the helper's
parameter to require `$executeRaw` made `tsc` name both doubles that lacked it,
before any test ran. A structural type on a collaborator is not ceremony; it is
the list of choices the code is allowed to make, and a double that satisfies a
narrower one is not exercising the same code.

---

## THE GENERAL SHAPE

**Ask of every double: what can the subject NOT do while talking to this?**

- fewer METHODS → the wrong method is unreachable, and every arm agrees
- fewer FIELDS → a read of the missing one is `undefined`, and `undefined ===
  null` is false, so a predicate silently changes answer
- fewer VALUES → the fixture that gives two distinct things one value cannot
  witness them being confused

All three are the same defect: **the double is narrower than reality, and the
narrowing is exactly where the bug lives.**

---

## WHAT IT IS NOT

It is not an argument for integration tests over unit tests. The unit arms here
were correct about what they asserted and are worth keeping; they were asked a
question the double had already answered. ⚠️ **Nor is it an argument for
faithful mocks of everything** — the fix was four lines, adding the ONE method
the subject might reasonably have chosen.

---

## RELATED

- **A CONTROL CAN PASS VACUOUSLY** — the family. This is its shape at the seam.
- **#277** — ratifies the `$executeRaw` fix **and its double**, deliberately:
  ratifying the fix alone would ratify the state that hid it.
- **A FIXTURE THAT GIVES TWO DISTINCT THINGS THE SAME VALUE CANNOT WITNESS THEM
  BEING CONFUSED** — the values-shaped member of the same idea.
