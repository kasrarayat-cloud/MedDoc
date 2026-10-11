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
