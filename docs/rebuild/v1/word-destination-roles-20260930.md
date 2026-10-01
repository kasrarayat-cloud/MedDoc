# Word destination authority by roles — what was built, refuted and integrated (2026-09-30)

Private and synthetic throughout. No provider request was made for this work; model-assisted mapping stays OFF by
default in every profile; the installed release (`dedac162`) was not touched.

## Design (the recorded narrower design, applied)

Whether a place may receive a model answer is decided by the ORIGINAL document's structure and approved mapping
roles, never by the model and never by the stored mapping:

- **Roles** (`documents/word_v3.py` `_role_reading`, read from a fresh inspection of the original): signing and
  initials areas keyed by span and line segment (so `Name: ____  Signature: ____` keeps Name answerable), protected
  areas and regions, form-field protection, locked content controls, source-policy patient sections and attestation
  cells, and a question box whose question reads as signing/consent (evaluated before the empty-cell check).
- **Gates**: fill and locate refuse a non-signature field on a role place; v3 confirm refuses such a mapping;
  generation never asks such a field; save and finalize refuse generated text there; mapping resolve applies removals
  first and re-validates the whole mapping; a batch plan whose original has a held field is refused before any hold
  or send.
- **Model path**: an envelope/integrity failure refuses the response; each invalid change is held with its reason
  and does not sink valid independent ones; a model ADDITION is never adopted (it becomes a review item a clinician
  adds or dismisses); a replacement only relabels an automatic ordinary field with no role and keeps its place;
  dependent changes (D1–D6) are held together; the result is order-independent; the stored field-dict keys are
  unchanged; the provider request for retained campaign attempt 2 is byte-identical (10,023 bytes, sha256
  `2c7d0e10…`), so no campaign declaration amendment is needed.
- **Legacy default path**: a row whose printed label reads as signature, initials or clinician identity is never
  generated; generated or accepted text there is refused at save and finalize; a clinician's own typed value exports.
  Identity is the mapped label's OR the printed label's (never weaker than 43fcf214).

## History (every round kept; branches pushed)

| branch / commit | result |
|---|---|
| `fix/v1-destination-roles` e555540d (implementation) | round 1: 19 confirmed (8 regressions vs 43fcf214) |
| a32243eb (repair 1: one fail-closed signing reader, structural extents) | round 2: 2 MEDIUM regressions + pre-existing leaks |
| 4e6b6e8a (repair 2: widened wording readers) | round 3: 7 regressions (HIGH/MEDIUM) — **not integrated**; the wording-reader assumption was dropped |
| `fix/v1-roles-salvage` 258650f2 (from a32243eb; the two regressions fixed, no new reader) | refutation: 7 regressions |
| 8951fdec (repair: each cause dropped or narrowed) | final verification: 4 partial/new MEDIUM regressions (below) |
| 6cd7c1ee (FV-01: identity never weaker than the mapped label) | red-first test + L05 test; **integrated** in `c1847625` |

## Results on the integrated code (synthetic batteries)

- **Leaks closed on the default legacy path** (43fcf214 generated all of them from `Label: value` notes): the 17
  must-hold labels — 'Patient signature', 'Initials', 'Witness signature', 'Consultant signature', 'Signature of
  examining clinician', "Participant's signature", 'Nurse initials', 'Initial here', 'Initial each page', 'Signature
  and date', 'Signature (patient)', 'Signed by (witness)', 'Nurse (initial)', 'Initial:', 'Staff initial', 'Nurse
  initial', 'Initials — Nurse' — and L01 (the Playwright reproduction: signing cells now byte-identical to the
  original). Model additions into signing boxes, Signature-column cells, signature lines and initials boxes; manual
  text fields on signing places; remove-then-re-add; stored forged mappings: refused or held (RF01–RF19).
- **Declared usefulness cost on the legacy default path (accepted-capability loss, owner decision)**: these clinical
  or checklist labels are no longer generated (the clinician types them; the typed value exports): 'Initial and
  ongoing management', 'Visit type (initial/follow-up)', 'Troponin initial', 'Troponin (initial)', 'Troponin —
  Initial (ng/L)', 'Lactate (initial)', 'Dose (initial)', 'Initial (baseline) weight', 'Initial / repeat', 'Gene
  expression signature', 'Signed on admission', 'Signed off by consultant', 'Consent form signed by patient', 'Drug
  chart signed by prescriber', 'Patient signature obtained', 'Witness signature obtained', 'Initial', 'Patient
  initials'. A draft generated before the upgrade that holds generated text in one of these rows is refused at save
  until cleared (B2-N7). On v3 (off by default) two of them refuse a clinician's add (B2-N6). Restoring them needs a
  release arm in the signing reader, which is the wording trap four rounds refuted; left for the owner to accept or
  to fund a different approach.
- **Unchanged vs 43fcf214**: every PC18/PC09 label, 'Troponin — Initial', 'Initial assessment', 'Consent form
  signed', 'Time signed', all 83 round-3 labels; legacy fill refusals in PC18: 0.
- **Relations interaction**: the ordinary-relations contract refuses a whole form when a field is role-held (the
  keyed record binds the whole catalogue); measured on 33 dev forms + 8 synthetic twins: 0 forms affected, because
  `v3_confirm` already refuses held fields.
- **Workflows**: 9 app walks (f1, f5, legacy rows, legacy tab lines, L01 shape, salvage legacy/v3) finalize and
  download with login (302 without); every export passes the DOCX skill validator and was rendered with LibreOffice.

## Residuals (recorded in `destination-roles-20260930/residuals.json`)

- **28 pre-existing leaks/limits (present on 43fcf214 too, not regressions)**, e.g.: comma/dash-joined 'Signature,
  date' read as a date; bare 'Sign', 'Please sign', 'Countersignature', 'Initialled by'; label cells wrapped over two
  paragraphs ('Consultant' + 'signature'); ordinary engine areas inside a signing box; captions printed beside or
  under a line with guidance between; content controls whose alias names something else; 'countersignature' /
  plural 'signatures' in a question box; signing wording in a log-table header. Each is the engine's own mislabel of
  a signing place as an ordinary answer; the clinician still reviews every generated answer before finalizing.
- **Declared regressions vs 43fcf214**: B2-N5/N6/N7 above; B2-N9 is superseded by 6cd7c1ee.
- **LOW test gaps**: two model-path arms not pinned by a test (mutants MG, MF survive the focused suites).

Evidence: `rebuild/.runtime/v1-product-20260930/b2/mapping/` (impl, refute, verify, repair, final-verify),
`legacy-battery-compare.json` here.
