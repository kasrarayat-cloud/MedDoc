# A NEW KEY IN A RECOMPUTED SUMMARY INVALIDATES EVERY ARTIFACT ALREADY STORED

**Ratified 2026-09-07, from ruling #247 Stage B.**

`templateTwinCounts` produces the fill manifest's `counts` block. Adding a bucket
to it looks like the most additive change available — a new number, nothing
removed, every existing key untouched.

**It is not additive, because that block is RE-COMPUTED and COMPARED.**
`certification-lifecycle.ts` re-verifies a **stored** manifest by recomputing the
counts from the manifest's own stored field resolutions and comparing canonical
shas:

```ts
canonicalSha256(manifest.counts) !== canonicalSha256(templateTwinCounts(manifest.fields, ir.fields))
```

A manifest written last month has no `recordDerived` key. Recomputing it today
produces one. The shas differ, the re-verification returns `false`, and a
document nobody touched fails its gate — **for a change that added nothing to
it.**

> **A summary that is recomputed and compared is not a place where a new key is
> free. Every artifact holding the old shape is now wrong, and none of them
> changed.**

⚠️ **AND THE PRECEDENT WAS ALREADY IN THE FILE, UNNOTICED.** `omitted` was added
by ruling #194 as `.optional()` in the schema and **unconditionally returned** by
the function. Optional in the schema only means old manifests still PARSE; it
does nothing about the recompute, so every manifest stored before #194 has failed
this comparison ever since. Nobody saw it because the population is tiny (2 rows
in production) and because a `false` here presents as *"this manifest does not
match its certification"*, which reads like the check working.

**THE SHAPE THAT AVOIDS IT — emit the key only when it is non-zero:**

```ts
const recordDerived = fields.filter((f) => f.status === 'record_derived').length;
return {
  ...base,
  ...(recordDerived > 0 ? { recordDerived } : {}),
};
```

Now a manifest with none recomputes byte-identically to before the key existed,
and one with some carries the number. ⚠️ **`canonicalSha256` refuses
`undefined`**, so the spread form is required — `recordDerived: undefined` is not
the same as an absent key and will throw rather than hash.

**THE GENERAL SHAPE, and it is wider than counts:** whenever a value is
**persisted once and derived again later for comparison** — a counts block, a
canonical hash input, a normalised document, a settings snapshot — the derivation
is part of the artifact's contract. Changing it is a MIGRATION of everything
already stored, whether or not a database column moves. The two honest routes are
(a) make the addition invisible for the old population, as above, or (b) version
the derivation and keep the old one reachable. **Neither of those is "it's just
one more field."**

⚠️ **THE TELL:** if you can find code that calls the producer on data it did not
produce — `f(stored.fields)` compared against `stored.summary` — then the
producer is pinned, and its output shape is an interface with existing callers
you cannot see.
