# V1 custom Word compatibility — predeclared target, corpus and scoring

Declared 2026-09-27, **before any change to the importer**. The commit that adds this file and
`word-corpus-manifest.json` is the predeclaration: its timestamp precedes every candidate result.
This is an engineering acceptance target, not a measured result and not a market-wide statistic.

## Baseline (dedac162, measured 2026-09-27 before any change)

The installed importer is a narrow deterministic adapter: two-column question|blank tables, strict
label|blank pair rows, `{{Question}}` placeholders and label + underlined-Tab paragraphs, plus AcroForm
PDF text fields. Any content control, legacy form field, text box, footer PAGE field or tracked
change refuses the whole form (except the one SHA-pinned WM IOV original); checkboxes cannot be
filled; mapping review is a text table with label renames only. Probe: 52 synthetic cases, 22
inspected, 30 refused. No real-form compatibility rate existed.

## Corpus (frozen; `word-corpus-manifest.json`)

- **Eligible:** blank clinical Word templates (`.docx`, legacy `.doc`) whose use is authorized by
  US federal authorship (17 U.S.C. §105), the UK Open Government Licence v3.0, or CC BY 4.0 /
  CC BY-SA 4.0 (each basis quoted in the sealed manifest), plus the owner's two forms (WM IOV and
  the colonoscopy operative template). Files with restricted (non-commercial), unclear or merely
  plausible authorization were excluded before selection. No patient record was collected.
- **Pool:** 321 candidates from two independent collectors; 277 eligible, 127 lineages, 38 source
  organizations. Structural tags come from the collectors' XML measurement, never from engine output.
- **Selection:** seeded (`20260937`, first seed from 20260927 satisfying every constraint) by
  `freeze_corpus.py` (kept with the sealed corpus): at most 2 files per lineage, a lineage never
  crosses sets; sets are **source-disjoint**; at most 8 files per source group and 24 NIH files in all;
  each family F1–F10 has ≥6 lineages in the 60, ≥3 in development, ≥2 in holdout, ≥2 in the
  qualification cohort; 2–6 legacy `.doc` files in the 60 (natural share 18/277) and ≥1 in the cohort.
- **Sets:** development 40 (19 source groups, including the owner's WM IOV and colonoscopy forms),
  holdout 20 (7 groups), **qualification cohort 20 (6 groups), predeclared now for the final candidate**.
  26 source groups across the 60.
- **Families:** F1 paragraph labels with blanks · F2 two-/multi-column · F3 merged/nested tables ·
  F4 mixed layouts · F5 multi-page sections · F6 repeated labels · F7 text boxes · F8 content
  controls and dropdowns · F9 checkboxes/checklists · F10 header/footer fields. Tags overlap. A
  family's "declared cases" are the files tagged with it here.
- **Sealing:** originals are read-only in `rebuild/.runtime/v1-word-corpus/{dev,holdout,qual}/`
  with `SHA256SUMS`. Holdout and cohort contents are not opened by development; their ground truth
  is established by separate annotators and stored sealed. The committed manifest lists them by
  hash, source group and declared families only; the full metadata is bound by the sealed manifest's
  sha256.

## Ground truth (before any candidate output is inspected)

For every template, independent annotators establish from the original alone (its XML and a render):
every intended answer area with its label/context, location (part, container, position), kind (text,
date, measurement, choice with its options, checkbox), and non-answer areas that must be preserved
(instructions, branding, signature and consent areas, existing check states). A signature area is an
expected **signature area**, never an auto-filled answer. The parser's field count never defines
completeness.

## Scoring (per document; every document stays in its denominator)

A document is an **automatic success** only if, with no template rewriting and no corrective manual
mapping:
1. every intended answer area is detected and mapped to the right destination, with its context and
   kind (no omission, no wrong destination, no silent drop, duplicate labels disambiguated or
   surfaced — never guessed);
2. empty, ordinary and long answers fill through the review/finalize path; and
3. the export is faithful: original wording, order, styles, table geometry/merges, content controls,
   check states and header/footer relationships preserved; reflow/pagination allowed; no clipping,
   overlap, lost question, overwritten neighbour or invented answer — checked by rendering and
   comparing every original/export pair and by structural diff.

Reported separately, never netted: field completeness (recall) and precision, wrong and omitted
mappings, explicit refusals, **assisted completions** (manual mapping — useful recovery, never
counted as automatic success), clinical answer quality on synthetic notes (explicit positives must
fill; missing, denied, corrected and ambiguous findings keep review/refusal; holding everything is a
failure), and latency.

**Release-blocking regardless of aggregates:** a silent omission, wrong destination, corrupted
control, changed clinical meaning or lost content.

## Targets

- ≥90% automatic document-level success on the frozen 60 (**≥54/60**) and on the holdout
  (**≥18/20**).
- Every family F1–F10 has passing independent examples and ≥75% success within its declared cases.
- Holdout evaluated once for the frozen candidate; first-pass results are retained. If a holdout
  failure informs a repair, the full 60-file manifest and every first-pass result stay; repaired
  outcomes are reported separately as known regression cases, never replacing failures, and the
  repaired final candidate must also meet ≥90% (≥18/20) on the predeclared qualification cohort,
  reported with every attempt and failure.
- Native Microsoft Word acceptance of the final holdout outputs and their actual controls needs the
  owner's authorized desktop session; LibreOffice renders are evidence, not native acceptance.

No claim of universal Word support follows from this sample. Encrypted/corrupt files, executable
macros, external relationships and image-only/scanned pages are handled as explicit, named refusals;
embedded code is never executed and external relationships never fetched.
