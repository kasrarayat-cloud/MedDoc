# QuillMD invited pilot — doctor guide (synthetic data only)

For invited doctors testing with **fictional cases only**. Real patient information must not be
entered: patient-data processing is not approved for this environment, and the product enforces
synthetic-only operation.

## Where to click

1. Open **https://app.quillmd.com:9443/**, enter the preview access details you were given, then
   sign in with your own account.
2. **Workspace → Form library.** Open a form to see where each answer goes ("Review mapping"), or
   choose **Use form →**. The new document opens with that form's current version already chosen.
3. Choose the fictional patient, type your notes, tick "These are synthetic clinical notes", and
   **Create document**. (You can also create the document first and then record or upload voice;
   the transcript must be reviewed and saved into the notes before generating.)
4. **Generate supported answers.** For every question, read the answer and its source evidence,
   then make one decision:
   - keep or correct the generated answer, **or**
   - tick **Accept this suggestion** where one is offered, **or**
   - tick **Leave blank — reviewed** when no answer belongs there (leave the answer box empty).
   Then tick "I reviewed this answer…" and **Save answers and review decisions**.
5. **Finalize document**, then **Export original format**. If finalizing is refused, the message
   names each question that still needs your decision.
6. **Billing & usage** shows every charge; "Explain this charge" gives its full derivation.

## How to write notes

Write each fact under the form's own question wording, one per line: `QUESTION LABEL: value`
(for example `Symptoms: no chest pain`). This is **required** for the qualified Word form below,
and gives the most reliable result on every form. On ordinary forms, unlabelled sentences may be
used, but an answer the system cannot tie unambiguously to one question comes back as a
**conflict** — shown with the whole note as evidence and, where clear, a suggested value — for
your decision. Unrestricted free dictation is not a supported way to fill a form.

## Supported forms

| kind | what works | notes |
|---|---|---|
| **Ordinary Word (.docx) forms** | question/answer tables, labelled underlined blanks, multi-column question rows, mixed table + underline layouts | answers expand in place; check every exported page |
| **Fillable PDF** | visible text fields | printable ASCII only; Helvetica field fonts |
| **Qualified Word form** | exactly **one**: the WM IOV template, identified by its file fingerprint, with its dropdowns and prewritten statements | requires `LABEL: value` notes; its own "No answer documented" choice replaces "Leave blank — reviewed" |

**Not supported, refused at upload:** any other Word file using content controls (dropdowns,
date pickers), text boxes, tracked changes, fields, macros or positioned answer areas; scanned or
flat PDFs; encrypted PDFs. A form with content controls is **not** qualified merely because it
resembles the WM IOV template. CPT coding is disabled.

## What "Leave blank — reviewed" means

It records that **you** decided no answer belongs to that question: your name, the document
revision and the time are kept, together with the original conflict, any suggestion and the
evidence. It is different from an untouched empty answer (which still shows as `missing`) and
from accepting a suggestion. The export keeps the answer area empty — no suggestion or other text
is inserted. It is not offered on signature questions (they keep their own identity rules) or on
the qualified Word form. Untick it, type an answer, or accept the suggestion to withdraw it.

## Known limitations

- Suggestions help with wording; they do not resolve every interpretation problem. A suggestion
  is never offered under a denial, a hypothetical or a quoted source.
- Exported pages can shift because answers expand; preprinted page labels may not match.
- Answers are generated from your notes only; nothing is inferred from outside them.
