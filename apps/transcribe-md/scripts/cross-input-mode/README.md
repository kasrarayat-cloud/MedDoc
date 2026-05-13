# Cross-Input-Mode Audit Harness

Reusable QA harness that runs **the same clinical scenario through all three input modes** (`text_notes`, `voice_dictation`, `audio_upload`) and verifies the L7 (ICDs / CPTs / Rx) outputs are clinically equivalent across modes.

The original motivation: the L7 layers read the SOAP, not the audio. Mode parity at L7 reduces to **SOAP quality across the L1→L4 pipelines** for each mode. This harness empirically validates that reduction across the full specialty surface.

## What it covers

24 demo-critical scenarios across all 12 clinical specialties (2 per specialty), each run through 3 input modes = **72 visits per audit cycle**.

Load-bearing safety scenarios with explicit `required: true` safety rules:
- **BS1** Bariatric — calcium carbonate post-RYGB → must trigger carbonate-vs-citrate warning
- **VS2** Vascular — iohexol 110 mL + eGFR 58 → must trigger contrast-AKI / lisinopril-hold warning

## Run path

```bash
cd /opt/meddoc-pro

# 1. Build the manifest the TTS synthesizer reads (idempotent, fast).
node_modules/.bin/tsx apps/transcribe-md/scripts/cross-input-mode/runner.ts --emit-manifest

# 2. Synthesize audio (skips files that already exist on disk).
python3 apps/transcribe-md/scripts/cross-input-mode/synthesize.py \
  --manifest /tmp/cross-input-mode-manifest.json

# 3. Emit the safety-rule labels manifest. The analyzer reads this back
#    and round-trips against its regex parser of scenarios.ts — drift
#    here fails the audit loudly rather than silently mis-counting.
node_modules/.bin/tsx apps/transcribe-md/scripts/cross-input-mode/runner.ts --emit-rule-labels

# 4. Run the full cycle — creates + uploads + enqueues + polls 72 visits.
#    First-run experience: <1 h wall-clock on tight TTS audio at the
#    default concurrency=2, ~$22 total Anthropic + Deepgram. Real-world
#    dictation audio with hesitations will cost more (~$30-35). Confirm
#    credits before invoking.
node_modules/.bin/tsx apps/transcribe-md/scripts/cross-input-mode/runner.ts --run

# 5. Analyze.
python3 apps/transcribe-md/scripts/cross-input-mode/analyze.py
```

Output: `/tmp/cross-input-mode-results.json` (raw per-visit dump) + `/tmp/cross-input-mode-parity.json` (structured parity matrix) + stdout summary.

## Pass criteria

For each scenario:
- All 3 modes terminate in `status=READY` (no FAILED).
- **ICD-10 Jaccard overlap ≥ 80%** on every pairwise comparison (text↔dict, text↔upld, dict↔upld).
- **`required: true` safety rules fire identically across all 3 modes** (binary all-or-none — these are demo-load-bearing).
- Cost per visit within the $0.30–$0.80 envelope established by prior audits.

Optional / advisory (not pass-blocking):
- CPT E&M tier agreement across modes
- CPT procedure-code Jaccard
- Rx drug-name Jaccard
- `required: false` safety-rule fires (advisory — model may legitimately phrase the same safety thought without matching a strict regex)

## Adding scenarios

Edit `scenarios.ts`. Each entry needs:
- `tag` — unique short code, e.g. `BS3`, `C3`. Pattern: `<SpecialtyAbbrev><number>`.
- `script` — doctor-dictation-style English text (~150–300 words). Used verbatim for `text_notes`; TTS-synthesized for the audio modes.
- `expect.icdAnyOf` — per-condition any-of arrays (give the model laterality + specificity flexibility).
- `expect.rxSafetyRules[].required` — set `true` only for demo-load-bearing rules; the harness fails the pass criteria if a required rule misses on any mode.

After editing, re-run from Step 1 — `synthesize.py` is idempotent and only regenerates audio for new / changed `tag`s if you also delete the matching `.mp3` from `.local/cross-input-mode-audio/`.

## Cost + duration

| Item | Cost | Duration |
|---|---|---|
| TTS synthesis (24 scripts × ~1500 chars × $15/1M) | ~$0.55 | ~3 min |
| Pipeline run (72 visits, observed mean $0.31/visit on TTS audio) | ~$22 observed; up to ~$30–35 with real dictation audio | <1 h observed at concurrency=2 (TTS clean audio); plan 2–3 h with real recordings |
| Analysis + reporting | ~$0 | ~2 min |
| **Total per audit cycle** | **~$22–35** | **~1–3 h** |

## Idempotency notes

- TTS fixtures live in `/opt/meddoc-pro/.local/cross-input-mode-audio/` (gitignored — too large for repo). `synthesize.py --force` regenerates everything; otherwise skips existing files.
- The runner ALWAYS creates fresh visit rows per invocation — there's no resume from partial run. If the run dies mid-way, run again from scratch (and accept the duplicated cost). Acceptable trade-off vs the complexity of a per-visit idempotency key.
- All visits are soft-deleted at the end of each cycle so re-runs don't pollute the test-patient's visit list.

## Owner / when to run

Run before a major demo or after any change that touches L1 / L1b / L2 / L4 prompts or the Deepgram model selection. Spotting an L1-vs-L1b SOAP-quality divergence early is the load-bearing value; the L7-layer SOAPs are downstream of those.
