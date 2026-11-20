# The Gemini migration's records

The Gemini migration (and, from DECISIONS D275, its Claude Fable 5.2 interpreter) was the earlier pipeline's reading
layer. The owner replaced the whole deterministic layer with the Fable coding step (DECISIONS D351-D353), and lane E
removed its code, its tests and its design documents (FINAL.md, FINAL-V2.md, ADJUDICATION.md, the amendments, their
refutation records and the build lists). They remain in git history.

What stays here is the record of what happened:

- `DECISIONS.md` - the integration owner's decisions, cited as "DECISIONS D<n>": what each changed, why, what it cost and
  how it was measured. This copy ends at D344; D345 onward (D351-D354 among them: the owner's ruling and the Fable
  coding build) are in the build's working copy and land here when it is synced.
- `USAGE-LEDGER.md` - the provider spend ledger. Nothing in it is credited back or reset.
- `acceptance-a1/` - the frozen acceptance set's proof: the pass thresholds the owner fixed before any case existed, and
  the hashes of the sealed cases and of the development exclusions.

The current design is in `cpt-studio/ARCHITECTURE.md`.
