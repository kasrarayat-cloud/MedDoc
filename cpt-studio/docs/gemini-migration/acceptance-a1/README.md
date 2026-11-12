# Acceptance set a1

This is the frozen measuring set for the Gemini-owned interpretation (owner directive 2026-11-12, HARNESS.md "Owner directive,
2026-11-12").
- The cases live outside the repository, sealed read-only.
- This directory holds the proof that they existed, unchanged, before any prompt change: the pass thresholds and the set's
  hashes.

## What it is
- **216 synthetic GI reports with 550 code rows.** There are six families (colon-sig, egd, eus, ercp, enteroscopy, currency-em),
  each with four kinds:

  | Kind | Cases per family | What it is |
  |---|---|---|
  | regression | 10 | A previous failure, rebuilt as a complete report |
  | paraphrase | 10 | The same facts and the same outcomes, in other words |
  | variant | 8 | A minimal edit that changes the outcome |
  | independent | 8 | An ordinary report written from scratch, mostly READY |

  The regression cases come from:
  - refutation rounds 5-6;
  - the repair rounds' reviews;
  - the U32 registry;
  - FRESH's recorded failures.
- **Expected outcomes, in code rows:**

  | Kind | READY | HELD | EXCLUDED |
  |---|---|---|---|
  | regression | 68 | 80 | 20 |
  | paraphrase | 68 | 80 | 20 |
  | variant | 63 | 46 | 22 |
  | independent | 59 | 20 | 4 |

- **Built by workflow wf_f0c940ab-f9e (2026-11-12).** Each family had:
  - an author;
  - an independent checker (209 of 216 cases agreed);
  - an adjudicator for the 7 disputes (7 changed, 0 dropped).
- **Mechanical structural checks** (counts only): 0 violations. They checked that:
  - every proposal cite, READY act and listed act is an exact quote of its document;
  - every expected list matches its proposals one to one;
  - every HELD names a topic;
  - every paraphrase's outcomes equal its regression case's;
  - every variant changes at least one outcome.

## Where it is, and how to check it
- **v1** (as authored, checked and adjudicated), sealed 2026-11-12T03:42:10Z, 233 files: the 216 cases plus the check and
  adjudication records. Files are 0400 and directories 0500.

  `/home/claude/cpt-studio-completion-20261106/gemini-migration/acceptance-a1/sealed-a1-v1/`
- `SHA256SUMS-v1` in this directory is a byte copy of the seal's `SHA256SUMS`, whose sha256 is
  `1886c335c6867a5fb64068d086fc73eb7630b6f024392c6d8b63c05158d42dd1`.
- To check, run `sha256sum -c SHA256SUMS` inside the sealed directory, then `cmp` its `SHA256SUMS` against this copy.

## Blindness
- The integration owner, who builds the new path, has read no case: only counts and hashes.
- The design agents never see the set.
- THRESHOLDS.md amendment 1 says what happens when a case is read, and how a disputed label is decided without the builder.

## Next
- Per THRESHOLDS.md amendment 1, every label is re-derived blind and every disagreement adjudicated.
- v2 is then sealed, and its hashes are committed here before any prompt change.
- v2 is the set measured.
