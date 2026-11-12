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

## v2: the labels re-derived blind (THRESHOLDS.md amendment 1)
**v2 is the set measured.**

### Blind re-derivation
Workflow wf_723a2741-bc3 ran 12 coders, two per family. Each saw only 18 reports and their proposals, under opaque ids. No
coder saw a label, rationale, note, source or kind.
- **Outcome agreement with v1:** 533 of 550 rows.
- **Disagreements:**
  - v1 HELD, blind EXCLUDED: 12;
  - v1 EXCLUDED, blind HELD: 3;
  - v1 READY, blind HELD: 2.
- **No blind coder gave READY** where v1 did not.
- **Also flagged:**
  - 5 rows where both said READY but quoted different acts;
  - all 214 rows where both said HELD, so their topics could be compared.

### Adjudication
Workflow wf_f2951183-c4f gave each adjudicator the two answers labelled A and B, in an order that does not say which is the
label.
- **Topics:** 208 of the 214 named the same fact; the other 6 went to adjudication.
- **28 rows decided:** 21 labels changed and 7 were kept. The changes:
  - HELD to EXCLUDED: 10;
  - EXCLUDED to HELD: 3;
  - READY to HELD: 4;
  - HELD with a corrected topic: 4.
- **Product policy given to the adjudicators.** They applied the outcome rule the way the product already does. The policy
  is stated from the code, not invented for the set:
  - An act the document places at another encounter is EXCLUDED. (assess.py: "not performed on the date of service".)
  - These are HELD for the reviewer (combination.py: "Held for the reviewer, not excluded"):
    - a base code beside its interventions;
    - a component that another proposed code includes;
    - competing codes;
    - a limited code where the full one applies;
    - control of bleeding the session itself caused.

### Consistency checks after the decisions were applied
- **Base codes.** A mechanical scan looked for a READY base code beside a counted intervention of its own family
  (combination._base, catalogue families). It found 4 rows in v1. All 4 were already among the adjudicated rows and went to
  HELD. None remain.
- **Paraphrases.** Every paraphrase still equals its regression case.
- **One dropped variant.** After its regression case was corrected, a1-colon-sig-var-05 no longer changed that case's
  outcome. A fresh pair adjudicator read all three documents and found both label sets right. The variant's edit changes no
  outcome, so it was dropped.

### The v2 set
- **215 cases, 546 code rows.**
- **Changes from v1, by kind:**
  - regression: 9 of 168 rows;
  - paraphrase: 10 of 168;
  - variant: 2 of 131, plus the dropped variant's 4;
  - independent: 0 of 83.
- **Expected outcomes, in code rows:**

  | Kind | READY | HELD | EXCLUDED |
  |---|---|---|---|
  | regression | 66 | 78 | 24 |
  | paraphrase | 66 | 78 | 24 |
  | variant | 62 | 46 | 19 |
  | independent | 59 | 20 | 4 |

- **The seal.** v2 was sealed 2026-11-12T04:39:52Z at
  `/home/claude/cpt-studio-completion-20261106/gemini-migration/acceptance-a1/sealed-a1-v2/`. Its 513 files hold:
  - the cases, and every record of v1 and v2;
  - the blind inputs, the re-derivations, the packets, the topic verdicts and the adjudications;
  - the opaque-id maps;
  - the tools and workflows that produced them.

  `SHA256SUMS-v2` in this directory is a byte copy of its `SHA256SUMS`, whose sha256 is
  `1eb4812c0880273d225f588443c2de842cff06998a00067e926515645160c9cb`.
- **The working copy is read-only.** A later label change follows amendment 1, part 2.

## Development exclusion list
`DEV-EXCLUSION.sha256` holds the sha256 of every a1 document text. Each text is hashed as written and with surrounding
whitespace stripped. That is 288 hashes for 216 documents, the dropped variant included, and nothing but hashes.
- No builder may use a document whose text hashes to a listed value as a development document or fixture.
- A guard test can check every fixture against the list.
- The sealed g1, c6 and c7 sets stay protected by the standing rule that nobody who builds reads them.

## Next
The design's step 0a verifies this commit before any instruction text is written and before any fresh call.
