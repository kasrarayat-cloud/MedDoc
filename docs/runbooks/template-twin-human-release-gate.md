# Template Twin human release-gate package

## Status and purpose

This package coordinates the remaining human checks for Template Twin without
putting a real physician document, real practice image, patient information,
or production credentials into GitHub Actions. It is tied to one exact Git
commit and is valid only for that commit.

The package has four independent purposes:

1. let a non-technical reviewer run synthetic desktop Microsoft Word QA;
2. give a licensed physician an offline worksheet for the seven unresolved
   WM IOV ordinary-placeholder intentions;
3. give an authorized practice administrator a worksheet for recording the
   result of the authenticated static-media review; and
4. return strict, hash-bound JSON evidence that a local validator can check.

The package has **no clinical or production authority**. It cannot certify or
activate a template, approve an image, authorize signing, import an
Office-saved document, deploy code, or change application data. Even a local
validator result of `PASS` proves only that the returned evidence is complete,
well-formed, unaltered, and tied to the expected commit.

## Package identity and download

The PR-only GitHub Actions workflow, `.github/workflows/template-twin-human-release-gate.yml`
(`Template Twin human release gate`), publishes an artifact named:

```text
template-twin-human-gate-<first-12-characters-of-PR-head-SHA>
```

The workflow summary records the full generating commit, artifact name,
byte size, and SHA-256. The artifact is retained for seven days.

The founder coordinates the gate as follows:

1. Open draft PR #363 and select the successful human-release-gate workflow
   run for the exact PR head under review.
2. Confirm that the full commit in the workflow summary is the intended PR
   head. Do not use a package from another commit.
3. Download the artifact with the matching short SHA and compare its SHA-256
   with the workflow summary before extracting it.
4. Extract it to a new local folder. Do not add files to the package or reuse
   evidence from an older package.
5. Give the Word instructions to the desktop Word reviewer, the physician
   worksheet to a licensed physician, and the media worksheet to an
   authorized administrator for the owning practice.
6. Collect the machine-readable outputs without editing them, and return them
   for repository-local validation.

If the artifact expires, rerun the PR-only workflow for the same commit. If the
PR head changes, generate a new package and repeat every human check; evidence
for the old SHA is intentionally stale.

The founder coordinates this process but does not substitute for the licensed
physician, the practice administrator, Privacy/Legal, Clinical Safety, or the
desktop Word observer.

## Desktop Microsoft Word gate

The Word corpus contains synthetic documents and synthetic clinical values
only. It includes the supported controls and boundary cases, together with
expected values, page expectations, hashes, Open XML evidence, and
LibreOffice evidence. LibreOffice results do not count as Microsoft Word
approval.

The reviewer needs no coding knowledge and no administrator privileges:

1. Extract the package on a Windows computer with installed desktop Microsoft
   Word.
2. Double-click `RUN-WORD-QA.cmd`.
3. Watch Word while each disposable copy opens. Record every repair,
   protected-view, conversion, or other dialog exactly as observed.
4. Follow the plain-language visual checklist for values, controls, tables,
   headers, footers, fonts, margins, page breaks, page count, and pagination.
5. Mark each question `PASS`, `FAIL`, or `BLOCKED`; do not infer a pass for an
   unobserved item.
6. Return the generated `template-twin-word-evidence-<short-sha>.zip` and its
   adjacent `.sha256` file.

The script verifies Microsoft Word availability, records Windows and Word
versions, checks originals before and after the run, opens only working copies,
saves separately reopened DOCX copies, exports PDFs, records hashes and
automation errors, and creates one timestamped evidence ZIP. It makes no
network request and does not upload any evidence. Repair dialogs and visual
layout remain human observations; automation cannot truthfully decide them.

Word status remains **PENDING** until the returned ZIP passes local evidence
validation and the human observations pass review. A Word pass is still QA
evidence only and does not relax strict pre-delivery verification contract v2.

## Licensed-physician intent worksheet

The physician worksheet contains exactly seven safe references, `P-01`
through `P-07`. It includes stable field and binding hashes, document section,
structural coordinates, token syntax, permitted decisions, and signing
consequences. It contains no document bytes and withholds source-adjacent text
from the downloadable packet.

A licensed physician must complete these steps personally:

1. Open `review-packets/physician-intent-worksheet.html` locally. The page has
   no server dependency and its content security policy disables network
   connections.
2. Use each P-reference and structural location to compare the placeholder
   with the approved local or authenticated QuillMD preview. Do not copy the
   source document or its content into email, GitHub, CI, or the returned
   evidence.
3. For each of the seven placeholders, choose exactly one outcome:
   - map it to one exact supported clinical concept;
   - define one template-scoped scalar custom concept;
   - mark it intentionally static, with a reason; or
   - leave it unresolved, with a reason, which keeps certification blocked.
4. For every clinical mapping, define requiredness, data type, exact units or
   allowed values where applicable, polarity and denial behavior,
   temporality, laterality, blank/unknown behavior, and maximum length or
   range.
5. Provide positive, negative, and ambiguous **synthetic** examples. Never
   enter a patient name, encounter detail, identifier, or other PHI.
6. Enter the physician name, professional role, jurisdiction,
   license/registration reference, review time, and every required
   attestation.
7. Save progress locally if needed. Select “Validate and export JSON” only
   when the worksheet reports no contradictory or missing decisions. The
   worksheet calculates the canonical payload SHA-256. Use the print action
   for an optional human-readable PDF copy.
8. Return the exported
   `template-twin-physician-intent-<short-sha>.json` without editing it.

No clinical answer is preselected. An unresolved answer is valid evidence of
a blocker, not a pass. The worksheet cannot self-certify a model proposal or
activate a template. Every accepted decision must later be repeated, reviewed,
synthetically exercised, and certified inside QuillMD under authenticated
physician identity; changing intent creates a new uncertified version.

## Practice-administrator media worksheet

The package contains no actual WM IOV JPEG and no image upload control. The
worksheet records metadata and a recommendation from QuillMD's authenticated,
practice-scoped static-asset workflow; it does not scan or approve an image.
The current safe-alpha workflow accepts only a byte-verified PNG. The existing
WM IOV JPEG is therefore unsupported and remains blocked; this worksheet must
not be used to imply that it can be approved in place. Advancing that document
requires either a new physician-supplied version containing an approved PNG (or
no media) or a later, separately reviewed JPEG-support implementation.

An authorized administrator for the owning practice must:

1. Review the real asset only through the approved local or authenticated
   QuillMD workflow. Never send the image to GitHub Actions, the downloadable
   packet, email, an external provider, or the returned evidence.
2. Confirm whether the candidate PNG is a reusable blank practice logo/static asset, whether
   it contains patient information, person names or identifiers, photographs,
   barcodes, hidden metadata, or an authorized organization/practice name, and
   whether the organization owns or may use it.
3. Copy the exact practice-scoped SHA-256, true MIME type, dimensions, byte
   count, scanner and local OCR versions, OCR/metadata/privacy evidence hashes,
   and privacy-scan result from the authenticated workflow.
4. Record current authenticated state, decision version, retention-policy
   status, and a policy reference when one is confirmed.
5. Choose recommendation, rejection, or referral to Privacy/Legal, explain the
   reason, and complete every administrator attestation.
6. Export `template-twin-media-review-<short-sha>.json` and return it without
   adding the image or editing the JSON.

Founder approval alone is not clinical or privacy approval. A recommendation
from this worksheet has no approval effect. Actual approval must be completed
inside authenticated QuillMD, is scoped to one practice and exact SHA-256, and
must be repeated after any byte change. Revocation blocks new certification
without altering historical signed documents. The real WM IOV image remains
blocked until this authenticated decision and the applicable Privacy/Legal
policy are complete.

## Returned-evidence validation

Codex or an engineer runs the repository-local, non-production validator from
the repository root on these evidence inputs:

- the returned desktop Word evidence ZIP and its mandatory adjacent
  `<zip-filename>.sha256` sidecar;
- the unchanged physician-intent manifest from the exact downloaded package;
- the physician decision JSON; and
- the media-review evidence JSON.

```bash
npx tsx apps/transcribe-md/scripts/template-twin-human-gate/validate-returned-evidence.ts \
  --word-evidence-zip /approved/local/path/template-twin-word-evidence-<short-sha>.zip \
  --physician-manifest /approved/local/path/physician-intent-manifest.json \
  --physician-decision /approved/local/path/template-twin-physician-intent-<short-sha>.json \
  --media-review /approved/local/path/template-twin-media-review-<short-sha>.json \
  --expected-source-commit <full-40-character-commit-sha> \
  --output /tmp/template-twin-human-gate-validation.json
```

The validator verifies the package and file hashes, strict JSON schemas,
source commit, source-document/manifest bindings, reviewer roles, all seven
physician decisions, required observations, attestations, and evidence
completeness. It rejects altered files, stale or mismatched SHAs, incomplete
answers, founder-only clinical approval, and evidence for another document or
Template Twin commit.

The Word ZIP sidecar must be in the same directory under the exact name
`<zip-filename>.sha256`. A missing sidecar is a `FAIL`; the validator never
replaces independent returned hash evidence with a digest it calculated only
after receiving the ZIP. A malformed, unsafe, unreadable, or mismatched
sidecar also produces a machine-readable `FAIL` report. The report path is
deliberately restricted to `/tmp` so this inspection command cannot write
into the repository or a production evidence store.

Its concise result is one of:

- `PASS` — the supplied evidence passed integrity and completeness checks;
- `FAIL` — evidence is invalid, altered, contradictory, or reports a failed
  gate; or
- `BLOCKED` — a required observation, authorized human decision, or tool is
  unavailable or explicitly unresolved.

The validator is local-only: it does not upload evidence, activate a template,
write production data, certify a mapping, approve media, authorize signing, or
change any QuillMD state. Preserve the original returned files alongside the
validation report for independent review.

## Artifact and CI content policy

The GitHub artifact may contain only source-controlled worksheets/scripts,
strict schemas, manifests, classified QA evidence, and generated synthetic
DOCX/PDF test cases. It must never contain:

- the real WM IOV DOCX, its bytes under another name, its extracted text, or a
  physician identity;
- the real WM IOV JPEG or any other real practice asset;
- patient data, encounter evidence, production logs, credentials, secrets, or
  production endpoints; or
- unexpected binaries, macros, embedded objects, custom XML, active fields,
  external relationships, or unapproved media.

Generation is pinned to the pull request's head SHA. The hygiene gate checks
allowlisted file types, ZIP/OPC contents, forbidden names, PHI/secret patterns,
and the real source document's SHA-256 without printing source content. A
forbidden filename, matching real-document digest, unexpected binary, or
unsafe package part fails artifact publication.

## Secret-scanner result classification

The current synthetic PostgreSQL fixture values were rewritten as unmistakably
non-secret test values. The current fixture files produce zero detections, and
the official verified-only scan reports zero verified secrets.

The immutable stacked commit range still contains three historical,
**unverified** PostgreSQL detector matches in a preserved commit. The offline
all-detections scan therefore exits 183 on that historical range. This is not
reported as “zero detections,” and it is not reported as a verified secret.
Rewriting those preserved commits is forbidden; no broad path, regular
expression, or repository-wide exclusion was added. Verified-secret scanning
remains fail-closed.

## Evidence custody and cleanup

- Treat returned human evidence as private review material even though all
  Office documents and clinical examples are synthetic.
- Keep it in the dedicated local evidence directory used for the audit; do not
  commit it, attach it to a public issue, or upload it to CI.
- Do not rename, edit, recompress, or merge returned files before validation.
- Keep the SHA-256 sidecars with their files.
- After validation and required review, delete extracted working copies and
  temporary Word/LibreOffice profiles using the included cleanup instructions.
- Let the GitHub artifact expire after seven days; do not extend retention by
  copying it to an unapproved service.
- Preserve only the authorized evidence record required by the approved
  retention policy. This runbook does not create or decide that policy.

## Remaining blockers

The human package does not remove any existing Template Twin gate. At minimum,
all of the following remain required before the relevant template can advance:

- returned desktop Microsoft Word evidence with no repair, clinical-value,
  control, occurrence, or unacceptable layout failure;
- licensed-physician decisions for all seven placeholders, followed by formal
  authenticated QuillMD review, field-level synthetic testing, certification,
  and version binding;
- authenticated, practice-scoped media approval for exact safe bytes, or a new
  physician-supplied source version without the blocked media;
- successful evidence-ingestion validation for the exact final commit;
- all clinical safety, privacy/legal, security, operations, storage,
  backup/restore, rollout, audit, and production-readiness approvals; and
- both stacked draft PRs reviewed and intentionally advanced through the
  normal release process.

Until those gates pass, Template Twin and the unchanged WM IOV document must
not be described as certifiable, clinically approved, Word-approved,
production-ready, or ready for real PHI.
