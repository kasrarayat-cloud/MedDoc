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
| [x] | 1.1 Installed revision, active work and existing provider integrations; fresh worktree; the shared checkout untouched | PASS | live `80df1831d168` (image `sha256:88544c7cd33f…`) | `docs/cpt-harness/stage1-starting-point.md` §1 (image labels, `docker inspect`, `.git/HEAD`, read 2026-11-01 21:30Z) | — |
| [x] | 1.2 Map of the document-to-code workflow; production clinical reviewers distinguished from engineering agents | PASS | `80df1831d168` | `docs/cpt-harness/stage1-starting-point.md` §2 (FILE:LINE map; Corti the only model reading documents; agent account scripted; engineering agents have no runtime role) | — |
| [ ] | 1.3 Backend access to Corti, Astra and Fable: exact provider, API model or endpoint identifier, a minimal synthetic capability check | BLOCKED (Astra, Fable) | live `80df1831d168` | `docs/cpt-harness/stage1-starting-point.md` §3: Corti live (45 sent primary runs, all with `X-Request-Id`; no model identifier exists in its API); Astra and Fable identities owner-confirmed, no credential reachable | the owner's two credential files (below); then the harness's access check for all three, recording endpoint, requested and returned model, request id and usage |
| [x] | 1.4 Authorized CPT and reference sources and retrieval tools, with releases, effective dates and permitted uses; unavailable dependencies recorded | PASS | live `80df1831d168` | `docs/cpt-harness/stage1-starting-point.md` §4 (live read: RVU26D 19,453 rows, MUE 2026-Q4 15,212 rows, 2026-10-01 to 2026-12-31; no retrieval stage); `docs/cpt-harness/vendor-and-reference-facts-20261101.md` §3 (each source's release, URL and published terms) | — (usable: RVU26D and its documentation, MUE, NCCI Policy Manual Ch. VI, Claims Processing Manual Ch. 12; unavailable: PTP behind the AMA agreement, AMA content) |

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

Sent to the owner 2026-11-01 ~21:30Z. Each dependency blocks only its own live stage; engineering continues meanwhile.

| # | dependency | needed for | protected destination | status |
|---|---|---|---|---|
| D1 | An Anthropic API key with access to `claude-fable-5-1`. A dedicated key inside the existing authorized account QuillMD uses is preferred; QuillMD's key is acceptable if the owner prefers it. It cannot be copied out of `rebuild/.env` by this session | 1.3, 3.3, 3.4, 6.3 | `/etc/cpt-studio-provider-sources/anthropic.env`, root:root 0600 in a root 0700 directory, one line `ANTHROPIC_API_KEY=<key>`; the installer copies it unread to `/etc/cpt-studio/` (10150:10150 0400), mounted into the worker only | OPEN |
| D2 | An OpenAI project API key from an authorized OpenAI project with access to `gpt-6-astra` on the Responses API. No Codex or desktop session token | 1.3, 3.2, 3.4, 6.3 | `/etc/cpt-studio-provider-sources/openai.env`, same ownership and mode, one line `OPENAI_API_KEY=<key>` | OPEN |
| D3 | Licensed CPT content: either an AMA licence (descriptors, guidelines), or acceptance that validation uses CMS public sources only and says so | 4.2 | — | OPEN; the default is CMS public sources only, recorded as a limit |
| D4 | The AMA position (FAQ, updated 2026-07-14): developing and testing products that use CPT needs an AMA licence. CPT Studio holds none, and no source read supports its "internal synthetic evaluation" note. NCCI PTP edits are reachable only through an AMA point-and-click agreement limited to CMS programs | 4.2, and the product as a whole | — | OPEN, owner decision; predates the harness; nothing is accepted or imported meanwhile |

No secret is requested in chat. A spending limit on each key in its own console is advised.

## Progress log (append only)

- **2026-11-01T21:10Z** Checklist created before any harness change. Carried in from round 4, as context and not as
  passes:
  - the rebuild's P1 fix is installed (`c8b54991`, a different application);
  - CPT Studio's pypdf 6.21.4 move is deferred after a non-converging fourth round (13 findings, 6 major);
  - Wave 1 refutation cycle 2 filed 23 findings; the non-converged releasing rules are being dropped under the round's
    two-cycle rule;
  - the three retained Corti discrepancies (EUS, EGD with biopsy, ERCP stent exchange) trace to provider omissions;
  - the round-3 live walk (2026-10-31) read 1 of 6 dates, approved 1 code and reached no reviewed report.
- **2026-11-01T21:40Z Stage 1.**
  - **Done:** 1.1 and 1.2 PASS on live reads. Corti is the only production participant; Astra and Fable are absent.
  - **Identities and credentials:** the owner confirmed both identities (Astra = OpenAI `gpt-6-astra` via `/v1/responses`;
    Fable = Anthropic `claude-fable-5-1` via `/v1/messages`). No credential for either is reachable without reading
    QuillMD's `rebuild/.env`, so 1.3 is BLOCKED on D1 and D2.
  - **References:** the live store holds only CMS PFS RVU26D and MUE 2026-Q4; their use terms are being checked before
    any import (1.4).
  - **Round-4 work in flight:** the Wave 1 repair cycle 2 finished. The non-converged releasing rules (PV1 C1/C2, PI E1
    and A1, the PD strong-head hold) were dropped, with narrow fixes kept (PD DT-5, PO-1). Projected HARD 119/123
    (installed 98) and walk READY {43251, 43274}, the same as installed. The integration is running.
  - **Next:** the harness design (`cpt-studio/HARNESS.md`), then its build, independent of D1 to D3.
