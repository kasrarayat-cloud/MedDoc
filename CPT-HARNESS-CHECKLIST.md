# CPT Studio GI coding harness: acceptance checklist

The acceptance contract for the owner's directive of 2026-11-01 ("Implement and install the actual CPT Studio GI coding
harness on cpt.quillmd.com: Corti plus independent Astra and Fable document reviews, supported by authoritative
reference retrieval and evidence-based reconciliation"). The directive is recorded verbatim in
`docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`. Integration and deployment owner: session 1bf3b49c
(interpretation 64).

**Rules of this file.** Status is one of NOT RUN, IN PROGRESS, PASS, FAIL or BLOCKED. `[x]` marks only a PASS backed by
the evidence named in its row. Code written, a mocked test passing or an earlier report repeated is not a live PASS.
Earlier failures and measurements are kept in the log below, never rewritten.

**Starting point, as found on 2026-11-01 (before any harness change):**
- `cpt.quillmd.com` serves CPT Studio round 3, revision `80df1831d168` (image `sha256:88544c7cd33f…`, web and worker
  started 2026-10-31T12:55Z).
- Production participants: **Corti only** (`cpt-studio/studio/providers/corti.py`). The provider layer has an interface
  (`base.py`), credentials handling (`credentials.py`) and replay (`replay.py`). There is **no Astra or Fable adapter**,
  and the settings name only Corti's credentials file (`CPT_STUDIO_CORTI_CREDENTIALS_FILE`). The word "astra" appears
  once in the code, in a test that refuses it as an unknown provider.
- Reference layer: importers for CMS physician fee schedule and MUE tables, with release, source URL, sha256 and
  effective dates (`cpt-studio/studio/reference/`). CPT descriptors are not imported or displayed, because no AMA
  licence is held.
- Earlier in this session the review "lenses" were engineering subagents on the session's own model (Opus 5.5). They
  reviewed code and never reviewed an uploaded clinical document. They do not satisfy any item below.

## Stage 1: establish the actual starting point

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [ ] | 1.1 Installed revision, active work and existing provider integrations; fresh worktree; the shared checkout untouched | IN PROGRESS | live `80df1831d168` | this file's starting point | full inventory (Stage 1 map) |
| [ ] | 1.2 Map of the document-to-code workflow; production clinical reviewers distinguished from engineering agents | IN PROGRESS | — | — | write the map |
| [ ] | 1.3 Backend access to Corti, Astra and Fable: exact provider, API model or endpoint identifier, a minimal synthetic capability check | IN PROGRESS | — | — | Corti check; Astra and Fable access to be established (no adapter or credential found so far) |
| [ ] | 1.4 Authorized CPT and reference sources and retrieval tools, with releases, effective dates and permitted uses; unavailable dependencies recorded | IN PROGRESS | — | — | live `reference_sources` read; retrieval tools and egress |

## Stage 2: read the document correctly

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [ ] | 2.1 Original document, hash and revision preserved; Word, native PDF, scanned PDF and pasted text with traceable extraction and OCR | NOT RUN | — | — | re-verify on the harness release (earlier rounds are context, not a PASS) |
| [ ] | 2.2 PDF upload-security repairs and parser safeguards on the applicable paths; encoding, checkbox and extraction failures addressed; an unreadable symbol never becomes a negative clinical fact | IN PROGRESS | — | — | establish CPT Studio's own PDF paths (the rebuild's P1 is installed, but it is a different application); the pypdf 6.21.4 reader repair is deferred (interpretation 68) |
| [ ] | 2.3 Each service represented separately: date, status, anatomy, extent, technique, lesion identity, provider role, exact evidence | IN PROGRESS | — | — | round-4 Wave 1 repair cycle 2 in progress |
| [ ] | 2.4 Shared interpretation defects repaired without patient-specific exceptions; reviewers not fed one interpretation as unquestionable truth; source text and page evidence kept | IN PROGRESS | — | — | cycle 2 drops and narrow fixes; harness input contract |

## Stage 3: three genuine participants

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [ ] | 3.1 Corti receives the supported source and returns proposals; selected codes, alternatives, evidence, raw response and metering preserved unrewritten | IN PROGRESS | live `80df1831d168` | — | verify against this contract |
| [ ] | 3.2 Astra independently examines the source: service facts, proposed codes, missing services, clarification needs | NOT RUN | — | — | depends on 1.3 |
| [ ] | 3.3 Fable independently examines the source before seeing Astra's or Corti's conclusions | NOT RUN | — | — | depends on 1.3 |
| [ ] | 3.4 Each participant's model or endpoint, input revision, request identity, output and usage recorded | NOT RUN | — | — | — |

## Stage 4: retrieve, validate and reconcile

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [ ] | 4.1 Actual reference retrieval: source identity, retrieved passages, release and effective dates, tool traces | NOT RUN | — | — | depends on 1.4 |
| [ ] | 4.2 Proposals checked against documented services, authorized CPT guidance and payer, bundling and modifier rules | NOT RUN | — | — | — |
| [ ] | 4.3 The complete service inventory reconciled against all three outputs, including services Corti omitted | NOT RUN | — | — | — |
| [ ] | 4.4 Disagreements resolved by source evidence and rules, not majority; contradictions kept; focused questions only where needed | NOT RUN | — | — | — |
| [ ] | 4.5 Proposed, reference-supported and reviewer-approved codes kept distinct; no automatic approval from agreement | NOT RUN | — | — | — |

## Stage 5: verify generalization before deployment

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [ ] | 5.1 The retained date, status, extent, EUS, EGD/biopsy and ERCP discrepancies reproduced and classified | IN PROGRESS | — | round-4 Corti traces (session record) | consolidate into the harness evidence |
| [ ] | 5.2 A small independently authored unseen synthetic set predeclared before execution, with expectations sourced independently | IN PROGRESS | — | sealed set u4-01 to u4-10 (manifest sha256 `c5e59d548b4087a0…`) | check its coverage against this item; declare its use |
| [ ] | 5.3 The declared set run and every result reported | NOT RUN | — | — | — |
| [ ] | 5.4 Tenant isolation, duplicate prevention, unknown-outcome recovery, evidence preservation, unchanged historical approvals and exports | NOT RUN | — | — | — |

## Stage 6: install and verify the website

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [ ] | 6.1 The verified release installed on cpt.quillmd.com with rollback evidence and preservation checks; served revision verified | NOT RUN | — | — | — |
| [ ] | 6.2 Understandable per-document progress (Corti, Astra, Fable, reference validation, clarification, final status); detailed traces in the administrative view | NOT RUN | — | — | — |
| [ ] | 6.3 Fresh synthetic documents uploaded through an ordinary authorized account; all three participants and reference retrieval proven to execute live | NOT RUN | — | — | — |
| [ ] | 6.4 Clarification, review and synthetic decisions completed; persistence after reload; actual reviewed reports downloaded and checked against saved state | NOT RUN | — | — | — |
| [ ] | 6.5 Automated synthetic decisions labelled accurately | NOT RUN | — | — | ordinary-reviewer acceptance mode built (`1e23e80b6`, unmerged) |
| [ ] | 6.6 Desktop and mobile verified, including genuine failure and unavailable-provider states | NOT RUN | — | — | — |

## External dependencies (one consolidated request)

To be written at the end of Stage 1, once each dependency is verified rather than assumed.

## Progress log (append only)

- **2026-11-01T21:10Z** Checklist created before any harness change. Carried in from round 4, as context and not as
  passes:
  - the rebuild's P1 fix is installed (`c8b54991`, a different application);
  - CPT Studio's pypdf 6.21.4 move is deferred after a non-converging fourth round (13 findings, 6 major);
  - Wave 1 refutation cycle 2 filed 23 findings; the non-converged releasing rules are being dropped under the round's
    two-cycle rule;
  - the three retained Corti discrepancies (EUS, EGD with biopsy, ERCP stent exchange) trace to provider omissions;
  - the round-3 live walk (2026-10-31) read 1 of 6 dates, approved 1 code and reached no reviewed report.
