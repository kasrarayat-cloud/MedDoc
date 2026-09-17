# Document SDK evaluation — fresh QuillMD foundation

Evaluated official documentation on 2026-09-17. No subscription was purchased,
no new cloud was provisioned, and no clinical content was sent to a provider.

| Option | Relevant capability | Constraints and decision |
|---|---|---|
| python-docx | Structured Word paragraphs, runs, tables and existing document editing | Use now for an explicitly bounded DOCX subset. Run-level edits preserve other run formatting. It is not a page layout renderer. [Official text/run documentation](https://python-docx.readthedocs.io/en/latest/user/text.html). |
| pypdf | Read AcroForm fields, fill values and generate appearances; copies the form structure when appending a document | Use now for visible text fields, with ReportLab font metrics and explicit overflow rejection. Flat PDFs and arbitrary printed forms require another adapter. [Official form documentation](https://pypdf.readthedocs.io/en/stable/user/forms.html). |
| Aspose.Words | Headless Word manipulation, rendering, export and mail merge | Strong candidate for advanced Word content controls/layout and DOCX-to-PDF qualification. Commercial licensing must be selected. Evaluation mode adds a watermark and has document-size limits, so it cannot be silently substituted into clinical exports. [Features](https://docs.aspose.com/words/net/features/), [licensing](https://docs.aspose.com/words/net/licensing/). |
| Apryse SDK | PDF field reading/filling, widget appearance editing, form creation and interactive review | Strong candidate for PDF field mapping and a document review surface. Need an appropriate SDK license/trial key, deployment terms, and processing-control review before integration. [Forms documentation](https://docs.apryse.com/web/guides/forms/), [license setup](https://docs.apryse.com/web/faq/add-license). |
| Adobe Document Services | Word template generation and PDF conversion through service APIs | Candidate if a cloud processing agreement and data-flow approval are obtained. Requires service credentials and commercial terms. API conversion capability alone does not prove exact customer-template fidelity; qualify against synthetic complex forms. [Document Generation API](https://developer.adobe.com/document-services/docs/overview/document-generation-api/), [Create PDF](https://developer.adobe.com/document-services/docs/overview/pdf-services-api/howtos/create-pdf/). |

The current implementation adapts established libraries; it does not implement
a Word/PDF rendering engine. Every new original is retained, each mapping is a
snapshot tied to its original hash, and export writes a separate file. Unsupported
controls, unknown layouts and overflowing PDF answers fail explicitly. The
application must show supported-format limits before upload and retain clinical
review before finalization.

Next external decision: select and license an advanced document SDK after
qualifying actual required form types against synthetic samples. Aspose.Words
for advanced DOCX plus Apryse for PDF mapping is a candidate pairing, not an
approved purchase or completed integration. A cloud option additionally requires
the required patient-data agreements and retention/region controls. OCR and
scanned-form mapping remain unavailable until an adapter is actually integrated
and verified.

## Implementation verification and refutation

`documents.tests` passes 14 synthetic tests. Coverage includes preserving original
bytes, Word question/run formatting and headers, long untruncated DOCX answers,
PDF values and regenerated appearances, overflow/Unicode refusal, stale mappings,
immutable output paths, ZIP traversal/duplicates/expansion/macros, XML entities,
PDF JavaScript/external actions/encryption, flat-PDF rejection, and actual kernel
denial of network sockets, secret-file reads and process creation.

A finished-adapter refutation found and reproduced two counterexamples, then
repaired them and reran the full document suite:

* `engine.py` Word inspection/`replace_span`: a `{{Symptoms}}` run with
  `font.hidden=True` accepted `Severe pain`, and the resulting answer remained
  hidden. Hidden/compressed/non-wrapping Word content now fails with
  `overflow_risk`; regression test `test_hidden_run_and_partially_invalid_placeholders_blocked`.
* `engine.py` placeholder validation: `{{Symptoms}} Also {{malformed%}}`
  produced one mapped field while silently leaving the malformed second marker.
  Validation now checks unmatched marker text after removing every recognized
  placeholder and rejects the template with `invalid_placeholder`.

These tests establish the documented subset, not universal Word/PDF visual
fidelity. Complex source formatting still needs the advanced SDK qualification
and clinician review described above.
