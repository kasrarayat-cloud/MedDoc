# Shared extent and table interpretation (synthetic) - source-reviewed expected facts

**What it measures.** Whether routing reads, by the SOURCE, the extent a GI report states and the services it reports,
across the layouts the live service sees: Word tables (rows extracted as cells joined with " | "), plain text, PDF line
wraps and OCR. It holds the second round's acceptance failures as the live service read them (h2-01: a "Procedure
summary" table that no section reader understood; h2-02: "Deepest point reached:" and "could not be advanced past the
hepatic flexure"; h2-04: "Procedure and findings" and "Furthest extent: pyloric channel."), their paraphrases and
layout variants, and the controls a repair must keep (a prior-procedures table, an office note's outside table, planned
dates, a cancelling comment, "past" as a time, aims, denials, "Insertion time"). `tests/test_repairs_gi3_extent.py` reads
every case here.

**Where it comes from.** `variants.json` is the gi3 extent investigation's set (session 7c8d38da, 2026-10-29): 89
synthetic texts in families F1 (procedure-summary tables and their controls), F2 (extent labels and "past"), F3 (the
pyloric outlet and composite headings), F4 (two services), F5 (depth in centimetres), F6 (failed or denied landmarks),
F7 (the known cases ho-01..ho-04, h2-03, h2-05, h2-09, h2-10 as the live service read them) and F9 (adversarial probes
and gate texts the repair changes). Every text opens with the synthetic banner.

**Truth, fixed by a reading of the source, never by a reader.** Each case carries `expected`, the facts a careful coder
takes from its text (per family: `status_in`, `extent`, `interventions_excludes`; `not_today`: families that must not
read performed or incomplete), and `review`, the one-line reading that justifies it. `hint: "uncertain"` marks a case
whose source leaves the reading open. No reader output is stored here: the test module pins every case read right, and
pins every residual by its exact output with a reason, so a change that fixes one fails loudly and is updated
deliberately.

It measures only the phrasings written into it.
