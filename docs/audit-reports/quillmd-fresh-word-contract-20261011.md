# Fresh Word answer-contract audit and repair — 2026-10-11

Status: implementation and qualification in progress. Installation and normal-HTTPS
acceptance are not yet established. The owner's signed-in browser remains unavailable;
no password reset, fabricated session or account-role change is authorized or used.

## Confirmed original failure, audited before patching

The retained encounter is `18b12def-0eba-4729-a732-18a1b498e988`, owned by
`kasra.rayat@gmail.com` in Synthetic North Clinic / X-ray. Its generation job is
`1f4dbc95-1ed8-4ada-98ee-5fddec1ccd97`; template
`73dabd43-3cd9-40ee-8338-fcb14c99f723`, immutable mapping
`0869c8ee-f527-49bd-beaf-974bcfac5c4d` (v1), physical preparation
`aa8fb259-c47a-4f73-88fd-4cbd3ee0340c`.

Preparation ran 19:06:31.925822–19:07:08.792791 UTC; the owner approved at
20:04:08.914453. The encounter was created 20:04:36.982288; the job queued
20:04:40.172737, ran 20:04:42.230013–20:04:45.371346, and the document finalized
20:06:04.389337 and downloaded 20:06:06.466622. Both queued and executing release
records identify `e62e73de7473b9f5afe7537d7b1f0e0fd983632e`.

The source SHA-256 is
`48f51d82ff02436f1770536cd015af39dbe7ebdd34239ee0831323b3ade3e01b`;
export SHA-256 is
`4c4ea3e450423d6deaaefe691539712cb8bfae7d68ba3a8a38a3239e93fd4c95`.
The original, both preparation responses, approval, job response, answers, final export,
audit rows and accounting were captured read-only and left unchanged. The protected
exact capture SHA-256 is
`a3ccf101b0d07e939584a504bf5a4987f4227a1d17ad6db693267057cf8ad704`.

Both actual physical-preparation roles completed using returned model
`claude-sonnet-5-5`; their raw responses reproduce the retained proposal/checker.
All 12 physical fields were generic text, with no units or choices. This was the
physical protocol's intended conservative metadata, rather than metadata lost on
approval. No reusable semantic-definition preparation or approval occurred.

The note ran `extractive-v7-custom-sentence-evidence`, a single sentence-selection
request (`req_011Cfw3qXafyoaoXssLSL2Vb`, response
`msg_011Cfw3qYQn9Ke9gxskiHhgu`). There were **zero** fact-extractor,
field-assigner or answer-checker stage receipts. The complete response selected
sentences, not concise values. Existing validation copied each unlabelled quotation
into `answer.text` (`generation.validate_tab_selections`), reproducing all 12
saved answers exactly. Review-only save preserved those values. The export reader
used those saved texts, and all actual Word answer cells equal them. Export preserved
the incorrect answers faithfully. A historical browser DOM/save POST body was not
retained; database/audit/export agreement does not invent that missing evidence.

Computed preparation provider costs were $0.032828 and $0.033762; note generation
$0.007320. Account charge was $0 under the existing standing synthetic authority.
Original costs and unresolved holds are preserved, with no invented credit or retry.

## Why the previous QA missed this

QA Harbor template `f31351c6-7670-4bc2-8bfe-4e003044f720` began with the same
12 generic physical field definitions. The prior browser harness then explicitly
started the extra reusable-definition workflow, entered reviewed definition
corrections through the supported UI, and approved semantic mapping v2 before testing
notes. The owner's ordinary fresh-upload path approved only physical v1, while its
Use Form link remained available. No SQL enrichment or secret generation route was
found; the extra preparation/review step was the meaningful difference. A numeric
mapping version was an inadequate capability test. Existing legacy narrative tests
also incorrectly treated whole source sentences in specific fields as success.

## Independent audit

Three reviewers independently checked mapping/routing, actual product stages, and
saved-answer/export handling before root began product edits. Protected proof digests:

- Mapping/routing: `69696de0b10fce9da7bacd8ede68e216e5bc99ee341cf5dcfb8f52ac473e6628`.
- Actual stages: `8abeffc80e2e4e692218a648b53ae8be9e5c08ade33d07a3d167680ab4335049`.
- Saved answers/export: `80aead85134fec91658e40e47a122c2557895d6eff10f3a3e6e994d819598045`.

Root owns implementation, live provider use and deployment. Reviewers perform
read-only refutation. Interim counterexamples cover tenant scoping, semantic error
classification, identifier spelling/boundaries, whole-clause values, Unicode names,
calendar dates, degree-unit spelling, and version-preserving definition review.
Finished-diff refutation, qualification and installed acceptance will be appended
only after their actual results exist.

## Qualification and refutation before installation

The first full PostgreSQL fixture run retained 1,545 tests with 137 failures,
44 errors and nine skips. Independent classification found nine supported
manual tab-form admission regressions, one incomplete fixture packet, and
171 historical untyped Word admission mismatches/downstream effects. Manual
creation is now separate from AI admission: it validates any present semantic
contract without requiring one for manual entry. AI quote/enqueue still refuse
missing definitions before provider reservation. No generation fallback was reopened.

Generic opaque-byte authorization/accounting fixtures now use the unchanged PDF
protocol; explicit real Word fixture consumers retain DOCX. Older single-call
Word compatibility suites have a narrowly scoped, documented test-only historical
admission mock. Their results are not fresh semantic acceptance. The unmocked
ordinary-clinician fresh-upload suite remains separate. The CI seed now uses
supported simulated preparation/explicit approval; simulated note agents leave
facts missing, and the browser's separate manual-entry coverage is labelled as
such. It cannot be cited as automatic semantic extraction success.

Independent finished-candidate passes on `2b6272c0ac62c665005727b1398fc834c4c28c38`
retained 55 mapping controls, 38 value/evidence controls and 12 version controls.
The earlier counterexamples (clipped repeated-punctuation identifiers, whole
all-caps name clauses and separate-v2 downgrades) are now refused or held for
review. A further product-stage finding demonstrated local SDK configuration
failure creating an uncertain hold with zero HTTP sends. Client construction is
now completed before reservation/send admission; this prospective fix does not
reclassify historical unknown usage. Revised finished-diff checks are pending.

The document-engine suite passed all 147 tests without provider calls. Full-core
v2, complete browser qualification, merged-revision installation and public HTTPS
fresh-upload acceptance remain pending at this report revision.

The second full isolated PostgreSQL run retained 1,548 tests, four failures, five
errors and nine skips. Its remaining failures were nine old financial/SDK-fixture
assumptions. Financial-only empty mappings are now PDF protocol fixtures. Actual
SDK offline deadline tests supply a synthetic local key, assert locally prepared
client construction separately from actual transport timeout, and still require
zero sends, unchanged reservations and no retry on deadline refusal. These are
qualification updates, not an exception to Word AI admission.

Further finished-diff counterexamples were fixed before installation: actual SDK
credential validation was lazy, so an explicit provider/key guard now precedes
reservation; missing own approved sources become actionable shared validation
errors; fixture seeding targets only its own preparation rather than a queued live
request; physical-only manual Word drafts expose their existing answer controls.
Historical unknown holds are not retrospectively reclassified.

All three independent finished-product-diff passes found no further demonstrated
defect on `d5fac5dc26ee3e511ddacbbfb46fbab57620af1b`: mapping/routing 72 controls,
product stages 15 focused tests plus actual SDK offline transport controls, and
saved/export handling 38 value/evidence, five rendering and 12 definition controls.
Proof digests: `a92c96407742468efb6e9343524815d3bb198aa25bacdff3f8f6403cf2ef0a82`,
`92846452e616ea62ad19e38ebc3d6e9747cbb1a67c898d3d8ef331c886e7e091`,
`1c31979eba186aef549963c9a7346ee71f4659334c339d993671fa3e24f168a8`.

All 1,344 operations tests passed (two environmental skips). The isolated fixture
browser's first actual flow passed all 15 checks, including three simulated roles,
manual review, finalization, original-format export and administrator MFA isolation.
Its next advanced-WM stage refused the local operator ownership boundary; no
production setting was changed. Complete CI uses its immutable separately installed
Word helper. Fixture browser/manual values and hand-authored validator definitions
are not automatic fresh-upload extraction proof. Installation/public HTTPS fresh
acceptance and the owner's browser confirmation remain pending.

Branch CI on `3e19a8e0558bcc0dc7269cd638b7a117e15aa192` passed the actual
private browser/accessibility and marketing jobs. The full application run retained
1,552 tests with four failures and one error, all five in old offline preparation
transport fixtures that omitted the now-explicit local synthetic SDK key. Those
fixtures now supply a local dummy key within their mock transport scope; the
provider guard remains intact. No product runtime file changed. The failed run
`38176363166` remains retained; the next descendant must earn a full citation.
