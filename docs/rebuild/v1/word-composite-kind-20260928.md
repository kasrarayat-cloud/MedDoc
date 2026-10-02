# Composite date/description answer areas — bounded repair

D30 A10's printed question requests both the order date and restrictions/safeguards. Its complete label and destination were already preserved, but `kind_for` returned `date` because the date check preceded the existing narrative-description check. This was incorrect metadata; **no date-only truncation was demonstrated**. The same family includes time plus descriptive details.

## Change and scope

Use the existing narrative pattern before date/time classification for ordinary free-text fields. No new clinical keyword list, prompt, field omission, destination change or population writer. Explicit native date controls remain dates; manual signature/initial handling remains first. Stored mappings/finalized exports remain unchanged.

- Three synthetic composite labels change to `long_text`; plain dates/times, signature/initial and unrelated text retain their types. Native date with a descriptive alias remains native date.
- Twenty-three focused controls initially pass, including22 existing question-box controls; the test-only readability refactor subsequently passes its two cases.
- Independent finished-diff refutation:12 controls, no demonstrated counterexample; all other metadata and applicable export bytes unchanged. Reviewer source SHA256 `21399290ec826f9c0c2b9e419b725a93008f39da565558ded076372990af0bc6`. Report in the Word worktree's `composite-kind-independent-refutation-20260928.md` at frozen docs head4bd24a30.

## Actual authenticated D30 route

One isolated PostgreSQL test traverses authorized original upload, mapping confirmation, encounter, mocked-provider worker generation, review/save, finalization and authenticated downloaded DOCX for missing, ordinary and long answers. The ordinary supported note is: “The patient is subject to an order dated January 1, 2026, with supervised community leave.” Its answer needs no clinician edit. Missing remains missing; the long case explicitly exercises clinician correction and is assisted.

All other XML slots and all non-body package parts are unchanged; missing output retains every package member's bytes. Source/output hashes, first generated answer, reviewed answer and authenticated route outcomes are retained. Zero provider calls or charges. This is product-route evidence with a mocked provider, not Sonnet5 clinical qualification.

The original and ordinary export are12 pages. The90-sentence long answer reflows to15 pages. The first raw PDF-text check reports non-contiguous answer/87prefixes because running headers/footers interrupt three continuations; that first outcome is retained. A separate body-bounded comparison confirms the complete answer and90/90sentences. Affected original/ordinary page2 and long pages2–5 were visually inspected; no observed clipping, overlap or overwritten neighbours. No native Word result is claimed.

## Remaining document gate

D30 remains a whole-document failure: accommodation/list ownership, referenced context, role/authorship and compound-answer completeness are still unresolved. This repair earns no automatic-document success or compatibility percentage. Original corpus denominators, first passes and rights restrictions remain unchanged.

Durable text evidence: `docs/rebuild/v1/evidence/composite-kind-20260928/`. Original/actual downloads, PDFs, images and exact scripts remain under the private runtime named in its SHA256 manifest.
