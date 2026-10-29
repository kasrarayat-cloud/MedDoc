# Negated status words (synthetic) — a constructed regression corpus, not an accuracy measure

**What it measures.** A negation written directly before a status word ("not aborted", "never cancelled", "wasn't
postponed", "without being aborted") denies that status, never the service. At 2b82889f routing read such a sentence
as the service's denial, cancellation or incompleteness ("Examination complete, not aborted." held a complete
colonoscopy for clarification: held-out document ho-02). `tests/test_repairs_gi2_negation.py` reads every case here
and requires the readings to stay as recorded, in both directions.

**Where it comes from.** `variants.json` is a sample of the 27,648-case constructed corpus of the gi2 negation
investigation (session 7c8d38da, 2026-10-28): a colonoscopy report frame, one of three descriptions (the cecum
reached, the scope only inserted, nothing about the scope), and an extent section that holds a negated status sentence
(lead + status word + trail + ".") followed by one extra sentence. Every text is fictional and opens with the synthetic
banner. The sample keeps every case that reads performed now but did not at 2b82889f (240) and up to 24 cases of every
other outcome cell (truth, reading at 2b82889f, reading now, service-name subject or not), so each kind of change and
each deliberate hold is present; every lead, status word, trail, extra sentence and description appears.

**Truth, fixed by construction, never by a reader.**
- A trail or extra sentence that genuinely denies, calls off, cuts short or doubts the procedure (`genuine: true`):
  never performed (held or denied).
- A clean case whose description documents the cecum: performed.
- A clean case with no documented extent, or with the planned-repeat trail: performed or held, never denied.

**Recorded differences** (`known_differences`, each with a reason in `reasons`): `leak` — newly performed beside a
doubt the guard's word list does not recognise (the ten `held_out` extra sentences were never used to write that list;
2b82889f held these cases only through the misreading, and reads each of them performed once the negated sentence is
removed); `pre-existing` — performed at 2b82889f as well (a denial routing does not read); `named-hold` and `more-hold`
— held, never released, in the safe direction. A recorded difference that disappears must be removed; a new one is a
regression.

**The counterfactual invariant** is checked on every case that reads performed: the same document without its negated
status sentence also reads performed. The negated sentence only ever withdraws a false denial; it never adds
performance.

It measures only the phrasings written into it.
