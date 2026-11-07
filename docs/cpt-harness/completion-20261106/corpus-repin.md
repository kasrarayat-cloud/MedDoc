# Completion repair: the completion corpus re-pinned once, on the integrated tree

`tests/fixtures/gi4/completion/corpus.json`, re-pinned 2026-11-06 by `python -m ops.gi4.completion --repin` after
`--report` measured every movement from the stage-1 pins (fd8040d71e44's readings). The machine-readable declaration
is `cpt-studio/tests/fixtures/gi4/declarations/completion-integration-corpus.json` (every moved entry, its verdict
before and after, its requirement).

**Invariant:** no entry is FALSE READY where the installed baseline had none: **0**. The 39 FALSE READY entries left
are all FALSE READY at the installed baseline too (group B, the installed release's own false READYs; 57 before).

## After the re-pin (627 entries)

| verdict | entries |
|---|---:|
| matches | 275 |
| safe side (held where listed is required) | 248 |
| FALSE HOLD | 51 |
| FALSE READY (each also at the baseline) | 39 |
| held pending an owner ruling | 11 |
| needs ruling (installed READY) | 3 |

## Movements from the stage-1 pins (481 entries)

| before -> after | entries |
|---|---:|
| FALSE HOLD -> matches | 43 |
| safe side -> matches | 15 |
| FALSE READY -> matches | 14 |
| FALSE READY -> safe side | 6 |
| WRONG FLAG -> matches | 6 |
| listed where a hold is required -> matches | 3 |
| matches -> safe side | 7 |
| matches -> FALSE HOLD | 7 |
| the reading moved, the verdict did not | 380 |

### The fourteen that moved toward holding

- **Seven, matches to safe side** (H2|PKG-PURPO-05, -11, -12 and their +45378 rows; R1|L1-4d): a marking for a
  later localization done at another facility or by another source. The base matched them only by excluding the
  marking as planned; the purpose reading (builder A, U5) now dates the marking today, and the other-provider or
  other-source cue holds it. Required: excluded as another provider's or source's. Held, never READY.
- **Seven, matches to FALSE HOLD** (ADM|C3-2-1:N2 attempted; ADM|C3-2-2's four consents; ADM|C3-2-3's two
  questions): a participant's code for an act a consent names, a question asks about, or an attempt says "could not
  be removed". Builder Q1's equal eligibility reads the participant's code exactly as Corti's selection of the same
  passage, which is held - and the base code with it (base_included) - where the corpus requires the participant's
  code excluded and the base READY. For a consent and a question the hold is the truthful reading (neither states the
  act not done, and "not performed" needs documentation: directive item 5), so the requirements and the readers
  disagree; for "could not be removed" the reader's stated-not-done rule does not read the failure. **Recorded as
  false holds and left to the owner's review** - not re-required to match the output.

## New: group E, the integration's minimal pairs (16 entries)

Each required outcome was written from the clinical facts before its reading was taken; each baseline was read on
the installed tree. All 16 match on the integrated tree.

| entries | rule | installed baseline |
|---|---|---|
| 8 | the dilation technique (Savary, through-the-scope, Maloney, unnamed, an Impression's restatement, two single-code cases) | 3 FALSE HOLD, 2 FALSE READY, 3 matches |
| 2 | a participant's passage about another, failed act of the code's kind | matches |
| 6 | a dated history in the indication beside a labelled paragraph (3 released, 3 held) | 3 FALSE HOLD, 3 matches |

## One requirement revised

C4M|C4-2:C4-2-4a ("The Schatzki ring in the distal esophagus was dilated with a through-the-scope balloon to 18 mm.
The dilation was performed without complication.", Corti 43249, Astra 43248): required both held as competing,
because the engine could not read a technique and a reviewer was to reject the unsupported code. The text states the
technique, so 43249 is the documented dilation's code and 43248 accounts for no documented act: now required 43249
READY, 43248 held. Never two READY either way. The entry keeps `required_before` and `required_revised`.
