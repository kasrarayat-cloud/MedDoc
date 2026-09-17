# Required WM IOV Word qualification — 2026-09-17

The owner has confirmed Word and WM IOV for the first release; scanned forms
are deferred. No SDK purchase is needed for the demonstrated DOCX editing:
**Aspose.Words.FOSS26.3.0** is MIT licensed, accepts the complete blank form,
and preserves the required structures in the checks below. The later v2 section
records completed adapter variants; application release evidence is tracked
separately in the checkpoint. Public routes remain maintenance and patient data disabled.

## Provenance and scope

Only the accepted blank `WM IOV Template.docx` was read. Original SHA256:
`c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b`.
No filled old document, patient data, application history or provider call was
used. Synthetic result files stay in a0700 runtime directory with0600 files.

Official [FOSS licensing](https://docs.aspose.org/words/net/getting-started/license/)
and [installation](https://docs.aspose.org/words/net/getting-started/installation/)
identify the MIT DOCX engine and lack of page rendering. The downloaded
[NuGet metadata](https://api.nuget.org/v3-flatcontainer/aspose.words.foss/26.3.0/aspose.words.foss.nuspec)
names Aspose, MIT, and the linked official repository. Its license is retained
with the qualifier. Package versions/content hashes are locked; no license key,
subscription, new cloud or purchase was needed. .NET8.0.425 was installed only
under the private worktree; its archive SHA512 matched Microsoft's release metadata.

## Actual form inventory

The main part has133 paragraphs, one28-row/84-cell measurement table,28 dropdown
SDTs, and two separate header parts. There are no nested SDTs. The Address SDT
is a block under the document body; the other27 are inline. Only Address has
a semantic alias/tag. Remaining controls must be identified by original hash,
part, stable SDT ID and reviewed surrounding text, never ordinal alone.

| Controls (zero-based) | Content |
| --- | --- |
|0 | Address |
|1–5 | Exam side, referring physician, technologist, machine, location |
|6–11 | Six separate clinical-indication choices |
|12–13 | Diagnosis; technique's venous-system selection |
|14–17 | Right-leg treated vein, start, end, treatment outcome |
|18–21 | Corresponding left-leg treatment fields |
|22–24 | Right impression vein, reflux choice, deep-system choice |
|25–27 | Corresponding left impression choices |

Additional answer locations are **four demographic blanks**, **52 measurement
cells** (26 rows with diameter in mm and reflux time in ms), **six tributary
location markers**, and the signature-time marker. Fifteen other empty body
paragraphs are spacing/narrative candidates, not automatically answer fields.
The private inventory contains every ID, question context, option and default.

## Demonstrated SDK behavior

Reproducible sources: `rebuild/documents/wm_qualification.py` and
`rebuild/documents/sdk_word/`. The final run passed **37 structural checks**:

- All28 longest non-placeholder choices selected through the SDK and reopened
  intact; every original SDT ID and option list preserved; no FOSS watermark.
- Original non-control text,133 body paragraphs, both headers, paragraph style
  IDs, section geometry and all embedded-media hashes preserved in the control
  scenario. The original file hash did not change.
- All4 demographic values,52 measurements and6 location markers survived the
  filled-form round trip. A synthetic signature timestamp was inserted.
- A **19,931-character** synthetic narrative round-tripped completely. The
  expanded document retained all answers and table data.

Two implementation problems were found and repaired during qualification:
new bare runs inherited the SDK's default font; new answers now clone the
existing run formatting through the SDK. Longer table content could separate
the signature label from its signer; the existing label now uses SDK
`ParagraphFormat.KeepWithNext`. This is a declared pagination change in the
complete scenario; the control-only scenario preserves original geometry.

## Completed visual qualification and its limits

Aspose.Words Python.NET26.9.0 rendered the accepted blank and complete synthetic
outputs privately. Evaluation mode has watermarks and general size restrictions,
as documented in [commercial licensing](https://docs.aspose.com/words/python-net/licensing/).
**Its PDFs/images are evidence only and must not become application exports.**

- Blank and dropdown-completed documents render3 pages. Original measurement
  and trailing-section pages2–3 are pixel-identical in this controlled renderer.
- The fully filled measurement/location/demographic document renders4 pages;
  the long narrative case renders7. All28 choices, all52 measurement values,
  all6 locations and all4 demographics are visible in the relevant cases.
- The long-answer PDF contains its ending marker and all280 repeated sentence
  endings. No evaluation truncation warning was observed for these cases.
- Visual inspection covered the completed question/answer page, all measurement
  rows, the narrative continuation/end, and the signature's pagination. The
  source already contains a trailing section/header page; it was preserved.

The VPS substitutes Liberation Serif for Times New Roman and DejaVu Sans for
Aptos/Aptos Display. This is **not** an exact Microsoft Word/native-font fidelity
certification. Review the final unwatermarked DOCX in the owner's actual Word
environment before launch acceptance. No proprietary font was installed.

Authoritative final evidence directory:
`/opt/meddoc-pro/.worktrees/private-os-isolation/rebuild/.runtime/wm-release-qualification/`.
It contains `qualification.json`, `render-evidence.json`, `inventory.json`,
`clinical-mapping-manifest.json`, SDK evidence, synthetic DOCX files and clearly
named evaluation PDFs/page images. Earlier failing/partial attempts remain
separately named for diagnosis; they are not the final citation.

## Clinical release gates: filling controls is insufficient

The original form contains prewritten findings and identities. In particular,
the longest-choice scenario yields reflux-positive selections alongside fixed
"No saphenous reflux" statements. It deliberately demonstrates why successful
format filling cannot certify clinical correctness.

The generated manifest records14 paragraph anchors containing fixed/default
clinical assertions or identities: body paragraphs9,11,19,23,27,30,31,32,34,35,
36,39,45,46. These include Full Study, technique/reflux assertions, prior
treatment language, right/left impression fragments, fixed negative findings,
clinical correlation and preprinted interpreting/signing identity.

Required behavior before this template can finalize:

1. Every selected dropdown must be an allowed original value with evidence.
   Missing choices stay missing; symptom/asymptomatic and positive/negative
   contradictions block finalization until explicitly resolved and reviewed.
2. Every prewritten clinical assertion needs documented support plus clinician
   review. The first bounded adapter refuses export when a fixed claim is
   missing or conflicting; it does not silently alter the preprinted text.
   A checked review box alone does not invent evidence. Any future reviewed
   replacement behavior needs its own explicit mapping, audit and qualification.
3. Measurements retain side, anatomical row and unit. Missing values never
   become0, normal or a copied contralateral measurement. Each unnamed
   tributary requires its own documented location.
4. Names/signature timestamps come from authorized user/finalization metadata,
   not AI inference or the preprinted clinician. A provider option in the blank
   form is not evidence that the named person performed or signed this exam.
5. Any source edit or voice correction invalidates dependent answer/assertion
   reviews. Finalization rechecks the same mapping version, source revision,
   original hash, permissions and all required decisions.

## Chosen bounded integration sequence

This is the implementation sequence, not an owner architecture decision.

1. Keep `documents/service.py` as the trusted parent: opaque immutable source,
   bounded private workspace, clean environment, timeout, exclusive export and
   hashes. Add an advanced Word backend; do not run the SDK in Django or the
   provider worker process.
2. Separate common package safety checks in `engine.validate_docx` from current
   capability refusals. Run the existing Python sandbox's ZIP/XML checks first;
   continue to refuse macros, embeds, external relationships, entities and
   malformed/oversized packages. Enable only the pinned WM structure initially.
3. Launch the FOSS helper under a dedicated native sandbox launcher. Landlock
   must be applied **before** exec/runtime thread creation, with read-only
   access to the exact runtime/assembly dependencies and job input, and writes
   only to the job directory. Upload/job files have no execute right. Deny
   networking, ptrace, process inspection, mount, namespace and subprocess
   creation. .NET needs runtime threads: permit only thread-form clone, deny
   clone3/process clone, and install a synchronized second exec-denial filter
   before opening the document. Disable .NET diagnostics and inherit no secrets.
   Prove resource limits with measured .NET startup; do not silently disable
   the existing512MiB Python limit or claim .NET passes it without evidence.
4. Expose a bounded JSON protocol for inspect/fill. All edits use SDK SDT, Run,
   Paragraph and Cell APIs. Require exact immutable locators/expected source
   text, option membership, unique IDs, complete outputs and exclusive paths.
   A missing/unsupported SDK or failed isolation must refuse the advanced form.
5. Version the90 answer fields with backend/schema/source hashes in
   `TemplateVersion.fields`. Store prewritten assertion requirements separately
   so they are not lost or squeezed into the current100-answer-field limit.
   Add explicit source/revision-bound clinical assertion decisions and actual
   signer metadata; preserve existing documents' mappings and original files.
6. Extend generation validation, review and `finalize` with the clinical gates
   above. The current finalized call passes only answer strings and current
   canonical fields: it must carry and validate reviewed assertion decisions
   and the encounter's fixed mapping version for this backend. Never silently
   trust defaults or append evidence-free clinician names.
7. Refute the completed clinical diff before merge. Required proofs include
   all28 controls,90 answer fields, unsupported defaults, contradictory reflux,
   missing measurements, invalid options, ambiguous tributaries, changed voice
   evidence, real signer binding, long answers, original/option preservation,
   stale mappings, department isolation, malicious ZIP/XML, process/network/
   secret-file denial, .NET resource exhaustion and completed Word export.

## Adapter and kernel boundary follow-up

The separate self-contained `WordHost` and mandatory managed security gate have
now been implemented. The native boundary is applied before CLR startup;
thread-synchronized exec denial is installed before any document/request read.
The independent boundary probe passed nine actual controls, including file and
exec denial on existing and new threads, network/process denial and a 28-control
SDK round trip. That probe measured about 2.23 seconds, 87,888 KiB peak RSS,
3,860,912 KiB reserved address space and six threads. It does not justify changing
the existing Python parser sandbox. .NET has its own limits and qualification.

The final bounded adapter run passed **39/39** positive/negative checks through
that same kernel boundary. Evidence is
`rebuild/.runtime/wm-adapter-verification-v5/verification.json`, with canonical
mapping in `inspect.json`. The pinned v5 runtime manifest is
`rebuild/.runtime/wm-word-manifest-v5.json`, SHA256
`2587d4dbf5853ab7f7b5c18d38c7e32029161386c3f8bb66adb4afb4ee2c0886`.
These checks include complete supported fill, Unicode evidence, long answers,
explicit missing blanks/placeholder retention, allowed options/units, stale
reviews/mappings, missing assertion evidence, negation stripping, cross-row
borrowing, fixed negative conflicts, wrong signer, and exclusive output.

The actual JSON protocol is documented in
`rebuild/documents/sdk_word/PROTOCOL.md`. It carries 90 versioned answers plus
14 source/revision-bound assertion/identity decisions, supports explicit reviewed
missing values, preserves measurements as blank when missing, requires explicit
units, and handles Unicode code-point source offsets. Finalization trusts the
authenticated parent's reviewer/signer/timestamp context and independently checks
review evidence and allowed values. Source control/page delimiters are excluded
from metadata text, not deleted from Word output.

The first adapter run found two metadata/verification issues and was repaired:
SDK `GetText()` included a trailing page-break character in the signer string,
and a requirement label collided with a dropdown label. All requirement labels
now have an explicit `Prewritten statement: ` prefix. A strict XML-byte test
also demonstrated that the SDK normalizes revision/drawing edit IDs, compatibility
declarations and an empty crop element. Media bytes, header text/styles/image
geometry and the remaining header structure are checked separately; ZIP/XML byte
identity is not claimed.

Application integration, end-to-end browser evidence, the finished clinical
refutation pass and the clinical limitations below remain separate release gates.
Do not read structural or boundary qualification as complete WM product support.

## Required reviewed literal replacement cases

The exact original literal/control sequence and SHA256 of each literal segment
are recorded privately in `literal-segment-inventory.json` beside the other
qualification evidence. No such replacements are enabled in the current adapter.
Future replacement mappings must bind to the original version and literal hash,
change only SDK text runs, retain every SDT/question and show the resolved full
statement for clinical review before export.

| Original anchor | Exact default segment / required case |
| --- | --- |
| Body paragraph 9 | `Full Study` after `TYPE OF EXAM: `; exam-type assertions need actual documented support. |
| Body paragraph 11 | `Maged S. Mikhail, MD, RPVI, RVT` after the interpreting-physician label; any replacement must come from authenticated authorized clinician metadata. |
| Body paragraph 19 | The fixed technique before and after its venous-system SDT asserts that the listed techniques were performed and reflux lasted over 500 ms; this cannot be presumed for an undocumented or negative study. |
| Body paragraphs 23/27 | Literal ` was found to have had previous treatment ` between the third and fourth SDTs; a no-prior-treatment case cannot be exported as this assertion. Prefix/intermediate connectors are inventoried so replacements never delete dropdowns. |
| Body paragraphs 30/34 | Literal ` is ` between the vein and reflux SDTs; original `is absent.` option produces `is is absent.`. An explicit versioned connector replacement is needed to repair this grammar without changing either option/control. |
| Body paragraphs 32/36 | Entire fixed literal `No saphenous reflux in right lower extremity.` / `No saphenous reflux in left lower extremity.`; positive cases require a documented reviewed replacement, never removal of the adjacent question/control. |
| Body paragraph 39 | `Clinical correlation with the above findings is required.` is a prewritten recommendation requiring review and support. |
| Body paragraph 45 | Only `<<insert date and time>>` is currently replaced, from trusted finalization time. The signature label stays. |
| Body paragraph 46 | Fixed signer identity; a different actual authorized signer currently blocks. A qualified trusted identity replacement is required for general clinician use. |

Paragraphs 31/35 consist of a laterality/deep-system phrase and one SDT; the
entire resolved statement is reviewed with source evidence. Unanswered controls
inside any prewritten assertion continue to block that assertion. Fifteen blank
paragraphs remain unclassified and cannot be silently repurposed for notes.


## v2 reviewed variants and completed-case evidence

The original v1 clinical refusal restrictions above are historical findings,
not the current v2 behavior. The owner authorized implementing the required
cases. `wm-iov-foss-v2` now preserves all 90 answer locations and 14 review
requirements while supporting allowlisted, source-supported statement variants:
positive reflux, absent veins with corrected connectors, no prior treatment,
explicitly missing/not-assessed information, and actual authenticated clinician
identity. Missing SDT display text is cleared without deleting the control or
changing its original options. Empty clinical-indication separators are adjusted
so a documented no-symptom case reads `CLINICAL INDICATIONS: Asymptomatic`.

All statement changes have immutable original text/hash, an allowlisted selected
variant, actual resolved text/hash and a visible changed flag. Replacements use
SDK literal-run editing; unchanged styled labels/indents, SDTs, options, question
headings, paragraphs and page breaks remain. Source evidence is mandatory for
all clinical assertions under their own complete labels, including side. The
actual interpreting/signing clinician comes exclusively from authenticated
metadata; changing that signer invalidates the prior review hash.

Independent refutation found a v1 defect despite its earlier passing checks:
identical right/left treatment sentences accepted the same bare right-sided
source sentence even when an explicit left-labelled source denied treatment.
The repaired SDK and review helper require exact own-label evidence and
consistency with every nonempty explicit value for that label. The original
counterexample is retained; it now refuses without an export. A second verified
compatibility defect rejected the helper's case/whitespace-normalized full label;
that supported case now passes both boundaries. Independent v2 evidence is in
`rebuild/.runtime/wm-v2-independent-refutation/` (12 checks).

The actual kernel-boundary v2 suite passed **90 checks** across five completed
scenarios and targeted refusal/no-export controls. Five completed exports are
positive, absent, no-prior-treatment, asymptomatic and a 19,826-character long
answer. Original hash, all 28 control IDs/options, 133 paragraphs, headers/media,
complete answers, reviewed statement changes and actual signer are verified.
Other controls cover side borrowing, contradictory source labels, hidden
measurements, unknown variants, conflicting template findings, stale source/
signer/mapping review, oversized answers and duplicate JSON.
Evidence: `rebuild/.runtime/wm-v2-verification-5/`; the exact final-build recheck
also passed 90/90 under `wm-v2-verification-6/`. Every unpacked DOCX package part
from each final export is byte-identical to the corresponding rendered build5
export; only ZIP container bytes differ. This comparison is recorded in
`wm-v2-verification-6/layout-equivalence-to-rendered-5.json`.

### Completed private layout evaluation

`rebuild/.runtime/wm-v2-layout-5-final/` contains the clearly named evaluation
PDFs/page PNGs and `render-evidence.json`. Positive, absent, no-prior and
asymptomatic exports each render three pages; the long case renders eight.
All selected text, all 52 measurements and every resolved clinical statement
are visible. Signature label and actual signer remain on the same page. No text
span was outside the page bounds and no evaluation truncation warning appeared.
Visual inspection included complete findings/impressions, no-prior and
asymptomatic branches, measurement rows and signature, and long continuation.

The first long-text extraction check failed because repeated evaluation footer
text appeared between pages of an otherwise complete answer. Diagnosis found
all 19,800 payload `x` characters and the ending marker; the corrected comparison
explicitly excludes only the known trial warning/footer lines. The complete
long answer then matches across pages. The original failing probe remains.
No DOCX answer was truncated. These watermarked PDFs/images remain evaluation
artifacts, not exports; native Word/font fidelity acceptance is still required.

### Exact build and reproducibility

`build_word.py` pins SDK **8.0.425**, self-contained runtime **8.0.31**, Linux x64,
MIT FOSS **26.3.0**, and transitive lock/content hashes. It emits a separate
manifest and a proof containing SHA256 of all build input source/project/lock/
global.json/build-script bytes. The installer compares those to the exact
reviewed commit. No shared SDK installation or purchase was made.

The first repeat-build probe found differing DLL/PDB bytes caused by generated
source paths. The build now maps repository and generated artifact paths
separately. Two clean builds then produced identical source proofs and all
**192 runtime files**, manifest SHA256
`ce182e17d73b476f016696d4cb53e33ba319eaafe8ab33f0563f23e5abab3382`.
Final candidate/proof: `rebuild/.runtime/wm-v2-build6/`; independent repeat:
`wm-v2-repeat6/`; comparison evidence: `wm-v2-build6/reproducibility.json`.
This is demonstrated reproducibility, separate from clinical/formatting proof.

### Final build8 and advisory evidence

The user-visible warning text was updated after build6 to describe the actual
review/export behavior without stale implementation claims. This changed only
one source file's comment/warning strings. A further provenance check found
that the SDK's default assembly informational version and SourceLink used the
ambient Git HEAD, despite the new source files being uncommitted. The build now
uses the SDK's supported MSBuild controls to disable ambient source-control
queries, SourceLink and informational-version revision injection, with
`SourceRevisionId` and `RepositoryCommit` explicitly empty. The generated
assembly metadata is asserted to be `1.0.0`, with no SourceLink output; source
input hashes and installer comparison to the reviewed commit are authoritative.

**Final frozen artifact:** `rebuild/.runtime/wm-v2-build8/`, manifest SHA256
`2a2ab5e1ba63e041dfd087e7f2c205999ccf8ff6bc41f9409cfd1d99e4537680`.
The final build8 inspector and five completed cases passed **47 targeted checks**;
its mapping digest is unchanged from the full90-check clinical build. Every
unpacked Word package part in all five final exports is byte-identical to the
corresponding full-regression/rendered outputs. Evidence:
`wm-v2-verification-8/final-build-equivalence.json`.

Reproducibility was then tested against **two separate private synthetic Git
repositories with different actual HEADs and identical build-input bytes**.
Both and the main worktree produced identical 192-file runtime manifests and
source proofs. Actual DLL bytes contained none of the ambient revision strings.
Evidence: `wm-v2-build8/cross-head-reproducibility.json`. These source-only test
repositories were private local fixtures; no remote, public repository, old
application data or patient data was involved.

A current read-only NuGet advisory query used SDK8's supported
`dotnet list ... package --vulnerable --include-transitive --format json` against
`https://api.nuget.org/v3/index.json` on 2026-09-17. A separate package inventory
was positively checked against the exact lock before accepting zero findings.
All five locked packages matched: Aspose.Words.FOSS26.3.0,
BitMiracle.LibTiff.NET2.4.649, SkiaSharp3.119.0, and its macOS/Win32 native packages
3.119.0. **Zero published vulnerable-package entries** were reported. Evidence:
`rebuild/.runtime/wm-nuget-audit/{result,inventory,summary}.json`. This is advisory
coverage for those NuGet packages, not proof about unpublished defects, host
libraries or the .NET runtime's separate security status.
