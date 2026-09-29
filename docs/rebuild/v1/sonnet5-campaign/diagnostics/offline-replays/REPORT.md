# D30 / D31 whole-app replays on the candidate, offline — 2026-09-29

**Mocked evidence only.** `anthropic.Anthropic` was patched and `socket.connect` denied; no rendering, no native Word,
no corpus scoring. Candidate `8e3dcfd0` (HEAD and 618 tracked files hashed before and after every run: unchanged).
Settings as the prior harness (v3 engine, claude-sonnet-5 profile, thinking disabled, batches on, history context
off), run once with `QUILLMD_V3_FIELD_RELATIONS` on and once off. Test databases `quillmd_qa_replay_*` on the QA
PostgreSQL were created and dropped by Django. Machine output: `results.json`. Written by the lead from the replay
agent's returned findings (the agent could not write report files). No replay after the latest integrations had been
recorded before this.

| case | relations ON | relations OFF | prior |
|---|---|---|---|
| D30 missing | success, export = original | success | same (0313bd94) |
| D30 ordinary (12 facts) | success, export `c6f55499` = prior | **held**: A22 (v3_21), A54 (v3_53) "possibly incomplete"; 10/12 | success |
| D30 long (5,105 chars) | **REGRESSION: held**, A35 (v3_34) | success, export `388d42cb` = prior | success |
| D30 accommodation | success `fa4771f3` = prior | success | success |
| D30 combined accommodation | success `90a7940d` = prior | success | success |
| D31 missing | success, export = original | success | same (fba37e2f) |
| D31 ordinary | success `a67c6c10` = prior | success | success |
| D31 long (5,556 chars) | **REGRESSION: held**, A48 (v3_58) | success, export `0093933d` = prior | success |
| D31 MAPPA sentence (A39, v3_48) | **FIXED**: success `7dc38c12` | **FIXED**: success, same export | conflict (held) |
| A15 two options, component | `multi_choice`; boxes 1–2 of 9 ticked; A1 "tick one" still refuses two | same | refused ("Only one option can be chosen") |
| A15 one sentence naming both (declared 23:38:32Z) | success `b24936e8`, exactly boxes 1–2 ticked | held (fails closed) | — |
| A15 two labelled lines, one option each (declared) | held | held | — |

## Findings

1. **Long answers regress with field relations on.** `v3_literal_facts.opposed_ids` (integrated in `e3ee2410`)
   withholds any selected unit longer than `v3_syntax.MAX_CHARACTERS` (1,000); `complete_ids` then raises
   `OpposedClaim` and the relation is refused. A spy counted 3 withholds and 3 raises on D31 long; a harness-only
   counterfactual that holds nothing completes both long cases with exports byte-identical to the prior ones. It fails
   closed (a usefulness loss, not a wrong answer). The relations path is off by default and paused.
2. **The MAPPA sentence now passes both ways.** With the flag off the repaired reader is never reached (0 calls); a
   flag-off result at `fba37e2f` was never recorded, so "it would also have passed then" is inferred, not measured.
3. **Community-leave A15 is repaired at component level** and through the whole workflow on the relations path; the
   default path holds a sentence naming two options, and both paths hold two labelled lines naming one option each
   ("more than one answer, or an answer that differs from its own labelled line") — a remaining usefulness gap.
4. **D30 ordinary needs the relations path** for all 12 facts; the default path holds two as possibly incomplete.

Every failure is at answer validation/review: the job succeeded, the reservation settled, the destination was held
with its source kept. D30 maps 61/61 corrected areas (mapping byte-identical to the prior one); D31 maps 51/51 plus
the same 10 write-protected controls, differing from the prior mapping in exactly `v3_17` (choice → multi_choice)
and `v3_3` (A1's context now carries its instruction). Every successful walk changed only `word/document.xml` (or
nothing), kept the ZIP member list and the stored original, and a foreign export returned 404. Test exit codes are 0
even on a semantic failure; `results.json` is the authority.
