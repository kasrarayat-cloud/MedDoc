# Date/section binding (synthetic) — a source-reviewed regression corpus, not an accuracy measure

**What it measures.** Which section governs a date-of-service label (gi3 dates; interpretation 42). At 90377ec6f413 a
plan or history section dropped every date label it held, also past a heading the section reader cannot place, so
h2-08's charge block ("Charge information" / "Date of service: 2026-10-06") was dropped and the header's 2026-10-05
was sent. `tests/test_repairs_gi3_dates.py` reads every row here.

**Where it comes from.** `variants.json` holds:
- the 99 variants of the gi3 date investigation (session 7c8d38da, 2026-10-29): the neutral-heading family in plain,
  PDF, Word-table, OCR, numbered and markdown layouts, fields inside the plan, billing blocks after a procedure
  report, history sections, and the planned, historical, same-date and colon-heading controls. Four rows are known
  cases (h2-08 and h2-07, live text and author source), read from `tests/fixtures/gi3/`;
- two variants of the gi3 scope investigation (A08, A17: a "GI clinic follow-up" title over the header, RC5);
- the repair's own rows (`source`: "repair agent dates (gi3), provisional"): B4's plan items, the X3 broken label,
  RC5's title and its controls, RC6's setting and patient-status readers, and rule U beside a label the history no
  longer governs. These are author expectations, provisional until an adversarial review reads them.

Every text is fictional and opens with the synthetic banner. Each row carries its source-reviewed expectation and its
review; no row carries the output of a revision.

**Expectations.** `document` — that date is sent, and a member's date the document never states (2026-10-01) is held;
`conflict` — no date is sent, each listed date is a member's answer that is taken, and 2026-10-01 is held; `asked` —
no date is sent (`never` names the dates that must never be); `uncertain` — any of the `acceptable` outcomes
(`document:<date>` or `asked`); `facts` — the listed context facts as `origin:value` (`conflict`, `missing`).

**Known limits** (`known_limits.json`): the rows the repaired reading reads otherwise than their expectation, each
pinned by its exact output (the service-date fact, the date sent, every member probe, the setting and the patient
status) with its reason. A change that fixes one fails its pin and must update the file deliberately; a new
difference is a regression.

It measures only the phrasings written into it.
