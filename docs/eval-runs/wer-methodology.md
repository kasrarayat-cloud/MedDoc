# WER methodology — PriMock57 eval

**Status:** `chore/wer-methodology-audit` (2026-05-10).
**Source:** `apps/transcribe-md/scripts/eval/primock57-run.ts`.

## Why two WER columns

The `primock57-run.ts` eval emits **two** WER numbers per case, computed
from the same Deepgram transcript + the same TextGrid reference, with
different normalizations applied to both sides:

| Column | Normalization | Use case |
|---|---|---|
| **WER (internal)** | lowercase → strip ASCII punctuation → collapse whitespace. Keeps numbers, hyphens, apostrophes. | Watch internal trend across releases. Stricter; reflects ALL ASR drift including digits/hyphenated tokens. |
| **WER (PriMock57-aligned)** | lowercase → hyphen→space → strip non-`[a-z \']+` → collapse whitespace. Mirrors `preprocess_text()` in the dataset's `scripts/utils.py`. | Compare against the published paper's baselines (Moramarco et al., ACL 2022). Less strict; ignores numeric mismatches. |

Both apply to BOTH the reference text and the hypothesis, so each
metric is internally consistent.

## What the divergence looks like

PriMock57's preprocessing (in their own `utils.py`):

```python
def preprocess_text(text):
    text = strip_transcript_tags(text)   # <UNSURE>, <UNIN/>, etc.
    text = text.lower()
    text = text.replace('-', ' ')         # follow-up → follow up
    text = re.sub(r'[^a-z \']+', '', text) # numbers + most punct gone
    text = re.sub(r'\s+', ' ', text)
    return text.lstrip().rstrip()
```

Concrete divergences observed on the PriMock57 corpus:

| Pattern | Internal | PriMock57-aligned |
|---|---|---|
| `"3 days"` vs `"three days"` | counts as 1 sub error | both normalize to "days" (digit dropped) — no error |
| `"follow-up"` vs `"follow up"` | counts as 1 sub error (single token vs two) | both normalize to "follow up" — no error |
| `"50mg"` vs `"50 mg"` | counts as 1 sub error | both normalize to "mg" — no error |
| `"7.5"` vs `"seven point five"` | counts as 3 sub errors | both normalize to "" vs "seven point five" — 3 insertions (PriMock57-aligned still penalizes for the spelled-out form because digits get dropped entirely) |

The internal metric will be slightly higher on average. Both move
together (a real ASR regression shows in both).

## How to read the published paper's numbers

Moramarco et al. (ACL 2022) report WERs around 23-30% for various ASR
systems on PriMock57. Those numbers were computed with the
`preprocess_text` shown above against an `sclite`-driven scorer (NIST
SCTK). Our `werFromTokens` implements the same word-level Levenshtein
that `sclite` produces; differences between our two columns and the
paper's WERs trace to:

1. Different ASR system (paper used wav2vec / Google / older
   Whisper; we use Deepgram nova-3-medical).
2. Different audio mixing (paper used Sox `-m`; we use ffmpeg
   `amix`). Approximately equivalent but not byte-identical.
3. Different normalization than `preprocess_text` only if you cite
   the **internal** WER column — the **paper-aligned** column is
   byte-for-byte the same `preprocess_text` they use.

## What's NOT addressed

The following confounds are documented but not yet handled:

- **Word-to-digit normalization** — neither metric maps "three" ↔
  "3". Both apply the same rule to ref + hyp so the impact is
  symmetric per case, but cross-case comparisons might shift if
  the corpus mix changes.
- **British vs American spellings** — PriMock57 is British
  (`colour`, `haemoptysis`). Deepgram nova-3-medical training is
  predominantly American. Tokens like `colour` vs `color` count
  as 1 substitution in both metrics. No spelling-map applied.
- **Filler tokens** — TextGrid markers (`<UNSURE>`, `<UNIN/>`,
  `<INAUDIBLE_SPEECH/>`) are stripped by our `stripTextGridTags`
  before WER. Deepgram doesn't emit anything analogous, so no
  asymmetry.

## Recommendation

Cite the **PriMock57-aligned** column when comparing against the
paper or other published baselines. Use the **internal** column for
release-to-release regression tracking, where the slightly stricter
metric makes cosmetic ASR drift more visible.
