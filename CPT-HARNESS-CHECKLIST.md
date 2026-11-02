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

**Three kinds of status, never merged (owner, 2026-11-01).** A row records whether its subject is DOCUMENTED (a fact
read from a source or written down), IMPLEMENTED (code built and tested offline) or VERIFIED LIVE (shown on the real
system with genuine responses). A PASS states which of the three it is. Documentation or a passing offline test is never
recorded as live verification.

## Stage 1: establish the actual starting point — PARTIAL (1.3 BLOCKED)

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [x] | 1.1 Installed revision, active work and existing provider integrations; fresh worktree; the shared checkout untouched | PASS | live `80df1831d168` (image `sha256:88544c7cd33f…`) | `docs/cpt-harness/stage1-starting-point.md` §1 (image labels, `docker inspect`, `.git/HEAD`, read 2026-11-01 21:30Z) | — |
| [x] | 1.2 Map of the document-to-code workflow; production clinical reviewers distinguished from engineering agents | PASS | `80df1831d168` | `docs/cpt-harness/stage1-starting-point.md` §2 (FILE:LINE map; Corti the only model reading documents; agent account scripted; engineering agents have no runtime role) | — |
| [ ] | 1.3 Backend access to Corti, Astra and Fable: exact provider, API model or endpoint identifier, a minimal synthetic capability check | IN PROGRESS (Astra and Fable PASS before install; the installed release's `app --access-check` decides) | live `80df1831d168` | per participant, below | D1 and D2 (below); then the access check for all three |

Item 1.3 per participant (documented / implemented / verified live):

| participant | documented | implemented | verified live |
|---|---|---|---|
| Corti | YES: `POST https://api.{us\|eu}.corti.app/v2/tools/coding/`, OAuth client credentials; its API takes and returns no model identifier (`docs/cpt-harness/stage1-starting-point.md` §3) | YES: installed adapter `corti-coding-v2@cptstudio-1` | PARTIAL: 45 live sent runs 2026-10-26 to 2026-10-31, each with `X-Request-Id`; no fresh access check under the harness yet; environment and tenant not recorded per run |
| Astra | YES: OpenAI, `gpt-6-astra`, `POST https://api.openai.com/v1/responses`, Bearer (owner-confirmed; `docs/cpt-harness/vendor-and-reference-facts-20261101.md` §1) | YES: adapter `openai-responses@cptstudio-harness-2` (tool loop), offline tests | ACCESS PASS 2026-11-02T06:01Z (pre-install check from the candidate image, not yet the installed release): HTTP 200, returned model `gpt-6-astra` (= requested), request `req_f5872cba22da497c87d11b2b6d12a20a`, response `resp_0545e923d6b404e4016ae82723477487d19787aa274210cad8`, 1,773 in / 515 out tokens, est. $0.0435; reading read (45385, nothing refused or unverified) |
| Fable | YES: Anthropic, `claude-fable-5-1`, `POST https://api.anthropic.com/v1/messages` (owner-confirmed; same file §2) | YES: adapter `anthropic-messages@cptstudio-harness-3` (no vendor output format; schema in the prompt; CPT Studio's strict parse), offline tests | ACCESS PASS 2026-11-02T07:52Z (pre-install check from the candidate image `fa457805c`): HTTP 200, returned model `claude-fable-5-1` (= requested), two exchanges with one `cms_code_facts` call (requests `req_011Cgdjn9XqR42Uc5t3eX9JE`, `req_011CgdjnX1eyPN4foZi8aYGp`; response `msg_011CgdjnXBqEtE9GD4Ph3sZF`), 7,254 in / 1,072 out tokens, est. $0.126; reading read (45385, nothing refused or unverified). Earlier: harness-2's request was refused ("compiled grammar is too large", `req_011CgdbDywZBDPP7SehwxfBs`; 12.8) |
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
| [ ] | 3.5 Initial assessments independent and FROZEN: Corti, then Astra, then Fable may run in sequence, but each first assessment is built from the same source revision alone, recorded immutably, and fixed before any participant is shown a peer's conclusion (owner, 2026-11-01) | NOT RUN | — | — | design in `cpt-studio/HARNESS.md` (harness@2); build |
| [ ] | 3.6 Peer review after the freeze: each model participant is then shown the frozen peer conclusions and CPT Studio's open questions, and answers with verbatim evidence; its peer-review output is recorded separately and never replaces its frozen first assessment; reconciliation follows | NOT RUN | — | — | design (harness@2); build |
| [ ] | 3.7 A documented service Corti omitted can be proposed by Astra or Fable, keeping its actual origin and evidence; never relabelled as Corti's output, never approved automatically | IN PROGRESS | — | engine merge being built (origin `participant`) | build; prove |

## Stage 4: retrieve, validate and reconcile

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [ ] | 4.1 Actual reference retrieval: source identity, retrieved passages, release and effective dates, tool traces | NOT RUN | — | — | two kinds kept apart (owner, 2026-11-01): (a) the references each PARTICIPANT actually retrieved through its tools and actually cited, with the tool trace; (b) the references the later RECONCILIATION retrieved. Each passage dated (source release and effective window) |
| [ ] | 4.2 Proposals checked against documented services, authorized CPT guidance and payer, bundling and modifier rules | NOT RUN | — | — | — |
| [ ] | 4.3 The complete service inventory reconciled against all three outputs, including services Corti omitted | NOT RUN | — | — | — |
| [ ] | 4.4 Disagreements resolved by source evidence and rules, not majority; contradictions kept; focused questions only where needed | NOT RUN | — | — | — |
| [ ] | 4.5 Proposed, reference-supported and reviewer-approved codes kept distinct; no automatic approval from agreement | NOT RUN | — | — | — |
| [ ] | 4.6 A documented path by which a source-supported finding corrects the shared date, status or extent interpretation, so that a false hold changes instead of gaining commentary; no promotion by agreement; clinical safeguards kept (owner, 2026-11-01) | NOT DONE in this release (D7, HARNESS.md 12.10) | — | built as harness@2's reviewer confirmation (11.3/12.5); three refutation rounds each found blocking defects in its "Verified" check, which cannot converge: the three retained false holds (h4-01 99204, h4-03 43244, h4-06 45385) are all "not documented" holds the readers read nothing for | OWNER QUESTION (class a): (i) a human-override confirmation that claims nothing CPT Studio cannot check, or (ii) no override, the false holds repaired at the readers (Wave 2; an I1-declared change) |

## Stage 5: verify generalization before deployment

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [ ] | 5.1 The retained date, status, extent, EUS, EGD/biopsy and ERCP discrepancies reproduced and classified | IN PROGRESS (documented: reproduced and classified before the harness) | `80df1831d168`, round-4 cycle 2 | `docs/cpt-harness/stage5-retained-discrepancies.md` (7 rows: 4 application, 3 provider, each with its harness@2 path) | measure each row again on the harness release, offline then live |
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

**What completes Stage 6 (owner, 2026-11-01).** The INSTALLED website, with the harness enabled, verified live. Corti-only
parity and replay are prerequisites, never completion. Completion requires all of:
- genuine Corti, Astra and Fable responses on fresh synthetic documents;
- reference-stage evidence: participant tool traces and the reconciliation retrieval;
- a persisted synthetic review;
- a reload that shows the review intact;
- an actual reviewed report downloaded and checked against the saved state.

## Final verdicts (three, reported separately)

| verdict | question | status |
|---|---|---|
| Functional completion | Does the installed harness run Corti, Astra and Fable live, retrieve references, reconcile, and carry a synthetic review through to a reviewed download? | NOT ESTABLISHED |
| Clinical validation | Is the coding accurate, as independently established (a qualified coder's adjudication of a predeclared set)? | NOT ESTABLISHED: no independent adjudication exists |
| Content-use permissions | May CPT content be used as the product uses it (D3, D4)? | NOT ESTABLISHED: owner decisions open |

The complete doctor-facing CPT demonstration is NOT READY while any required dependency (D1 to D4) is unresolved.

## External dependencies (one consolidated request)

Sent to the owner 2026-11-01 ~21:30Z. Each dependency blocks only its own live stage; engineering continues meanwhile.

| # | dependency | needed for | protected destination | status |
|---|---|---|---|---|
| D1 | An Anthropic API key with access to `claude-fable-5-1`. A dedicated key inside the existing authorized account QuillMD uses is preferred; QuillMD's key is acceptable if the owner prefers it. It cannot be copied out of `rebuild/.env` by this session | 1.3, 3.3, 3.4, 6.3 | `/etc/cpt-studio-provider-sources/anthropic.env`, root:root 0600 in a root 0700 directory, one line `ANTHROPIC_API_KEY=<key>`; the installer copies it unread to `/etc/cpt-studio/` (10150:10150 0400), mounted into the worker only | OPEN |
| D2 | An OpenAI project API key from an authorized OpenAI project with access to `gpt-6-astra` on the Responses API. No Codex or desktop session token | 1.3, 3.2, 3.4, 6.3 | `/etc/cpt-studio-provider-sources/openai.env`, same ownership and mode, one line `OPENAI_API_KEY=<key>` | OPEN |
| D3 | Licensed CPT content: either an AMA licence (descriptors, guidelines), or acceptance that validation uses CMS public sources only and says so | 4.2 | — | OPEN (owner, 2026-11-01: keep unresolved). Prepared: `docs/cpt-harness/licensing-requirements-20261101.md` D-4, D-5 |
| D4 | The AMA position (FAQ, updated 2026-07-14): developing and testing products that use CPT needs an AMA licence. CPT Studio holds none, and no source read supports its "internal synthetic evaluation" note. NCCI PTP edits are reachable only through an AMA point-and-click agreement limited to CMS programs | 4.2, and the product as a whole | — | OPEN (owner, 2026-11-01: keep unresolved). Prepared: `docs/cpt-harness/licensing-requirements-20261101.md` (review of 21 sources; **no document read grants CPT Studio any right to CPT content, code numbers included**; decisions D-1 to D-8, among them D-3: the harness sends synthetic documents, and in peer review CPT code numbers, to OpenAI and Anthropic) |
| D5 | Corti's public terms (§2.6.1.9) bar customers to "benchmark or test the Platform for competitive purposes without prior written approval". The harness runs Corti beside OpenAI and Anthropic, and its reports set their outputs side by side. Whether that is "for competitive purposes" is not stated; the owner's signed Corti agreement is not available to this review | the harness as a whole | — | OPEN, owner question (found 2026-11-01 by the licensing review) |

**The two credential destinations, exactly** (D1, D2). Each is a file the owner creates as root. No secret is ever
requested in chat.

| file | directory | owner and mode | content (one line) |
|---|---|---|---|
| `/etc/cpt-studio-provider-sources/anthropic.env` | `/etc/cpt-studio-provider-sources/`, root:root 0700 | root:root 0600 | `ANTHROPIC_API_KEY=<key>` (optionally a second line `ANTHROPIC_WORKSPACE_ID=<id>` if the key is not scoped to a workspace) |
| `/etc/cpt-studio-provider-sources/openai.env` | the same | root:root 0600 | `OPENAI_API_KEY=<key>` (optionally a second line `OPENAI_PROJECT=proj_<id>`) |

**What happens to them.**
- The installer copies each, unread, to `/etc/cpt-studio/anthropic-credentials.env` and
  `/etc/cpt-studio/openai-credentials.env` (10150:10150 0400).
- The copies are mounted read-only into the worker container only, at `/run/cpt-studio/`.
- QuillMD's own credentials are not touched.
- A spending limit on each key in its own console is advised.

**Rules for D3 and D4 (owner, 2026-11-01).**
- No agreement is accepted, no synthetic-testing exemption is inferred, and no download term is bypassed. In
  particular, the PTP quarterly change file, which is a direct link, is not downloaded.
- The existing provider agreements are being reviewed for any downstream CPT rights they document. Documented coverage
  is kept apart from assumption.
- The exact remaining licensing requirements are prepared for the owner's review in
  `docs/cpt-harness/licensing-requirements-20261101.md`.

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
- **2026-11-01T22:35Z The owner's corrections, applied to this file and to `cpt-studio/HARNESS.md` (section 11,
  harness@2):**
  - Stage 1 is PARTIAL while 1.3 is BLOCKED. Documented, implemented and verified live are kept apart (1.3 per
    participant).
  - First assessments are independent and frozen before any peer conclusion is shown. Peer review follows, then
    reconciliation (3.5, 3.6).
  - A reviewer-confirmed correction path lets a source-supported finding correct the shared date, status or extent
    reading (4.6). There is no promotion by agreement.
  - An omitted service keeps its origin (3.7).
  - Participant-retrieved and participant-used references are kept apart from the reconciliation's references, with
    tool traces (4.1).
  - D3 and D4 stay unresolved. No agreement is accepted, no exemption inferred and no download term bypassed. The
    licensing review is running.
  - Stage 6 completion means the installed site with the harness enabled and genuine responses. Three separate final
    verdicts.
  - The six harness@1 builders keep running; their work is the base that harness@2 builds on.
- **Correction to the entry above (appended, not rewritten):** it is stamped 22:35Z, but it was written at about 22:24Z. The clock read 22:25:46Z after that commit. The stamp was estimated rather than read; later entries use the clock.
- **2026-11-01T22:43Z Licensing review prepared for the owner:** `docs/cpt-harness/licensing-requirements-20261101.md`. It is a read-only review of Corti, OpenAI, Anthropic, AMA and CMS sources, with three key quotes spot-checked against the saved copies. It finds that no document grants CPT Studio any CPT right, code numbers included. It adds D5 (Corti's benchmarking clause). D3 and D4 stay open; nothing was accepted or downloaded.
- **2026-11-01T23:08Z Integration checkpoint (offline only):**
  - **Round 4 merged and pushed.** The integrated round-4 branch, `443e67032` (pushed), is merged into the harness.
    Its measured results: HARD 119/123; walk READY {43251, 43274}; H2 gate held; H3 no MUST regression; H6 195/195;
    Django 4,082 OK.
  - **Four builder packages merged:** adapters, passages, engine and installer.
  - **The reading-schema mismatch is fixed** (49 failures and 2 errors before, from my own contract change of the
    reading schema): merged-package suites 271 OK, ops 264 OK.
  - **I1 proven against the integrated round-4 baseline (`80f2f2dc8`)**, with Astra and Fable disabled:
    - engine parity: 11 cases byte-identical, in both call forms;
    - H1 replay base to head EQUAL (fixtures and retained inputs; controls behave: self EQUAL, three planted DIFFER);
    - H4 battery: 0 movements.
  - **Pending:** the website and pipeline packages are still being built. Nothing is verified live.

- **2026-11-02T01:30Z Integration owner changed; harness@1 and harness@2 part A integrated (offline only).**
  - **Takeover:** session 1bf3b49c ended at 00:39:35Z, with its two builder workflows in their final full suites; the
    owner chose that session cd048041 take over after it stopped. Every builder's work was committed; none had written
    its final report, so the integrated tree was verified afresh.
  - **Merged:** the engine's last commit, the website, the pipeline, and harness@2 part A (tool loop and peer review,
    the engine's confirmed findings and peer inputs, the installer's updates). One conflict, a union of appended tests.
  - **Integration fix (`ec00a5b87`):** the pipeline imports the CMS passages module directly, so a missing module fails
    instead of recording an empty retrieval; four tests updated to the installed module; the reports test's titles.
  - **Measured on `ec00a5b87`:** Django 4,593 tests OK (3 skipped); ops 289 OK; ops/verification 37 OK; node browser
    verifier 84/84; node app 71/71; check and makemigrations clean. I1 against the round-4 head `80f2f2dc8`: H1 replay
    EQUAL (HARD 119/123 both sides), H4 battery 0 movements, 0 new violations. Draft PR #1459 opened for CI.
  - **Next:** refutation round 1 on `ec00a5b87` (five lenses, running); harness@2 part B to the contract in
    `cpt-studio/HARNESS.md` section 12 (`99939d764`). Nothing is verified live; D1 to D5 stay open.

- **2026-11-02T06:10Z Participant credentials checked, wired, and access-checked (owner directive of 2026-11-02).**
  - **Files (05:52Z):** `/etc/cpt-studio-provider-sources/` root:root 0700 with exactly `anthropic.env` and `openai.env`,
    each a regular root:root 0600 file within 32,000 bytes that parses under CPT Studio's rules with its required key and
    no optional key. Checked in a no-network root container that prints booleans only (proved on fake files first).
  - **Wired (05:59Z):** the installer's own `secrets` phase alone, from the harness revision `e3c05bc0`, under the
    committed declaration `docs/foundation/mutations/20261102-cpt-studio-participant-credentials.md`: both copied to
    `/etc/cpt-studio/` as 10150:10150 0400 (states `created`, key names only); the three-file set `present`; the three
    CPT Studio containers unchanged (ids, images, start times); no value in any receipt or log (root-helper scan).
  - **Access (06:00-06:05Z), from a separately tagged candidate image in the installer's access-check layout** (copied
    file read-only at the worker's path, uid 10150, the installer's hardening, a throwaway network and database; output
    kept only after a root-helper scan found no credential value): **Astra PASS** (returned model `gpt-6-astra`, row
    1.3 above). **Fable: the key and the model work, the harness request does not**: Anthropic refuses the reading
    schema as structured output together with the reference tools ("compiled grammar is too large"; six probes pin it,
    request ids kept). Fable's adapter is being changed to send no vendor-constrained output; CPT Studio's own strict
    parse and validation are unchanged. Both checks run again, formally, in the install's `app --access-check`.
  - D3 and D4 stay open. Nothing here is a live verification of the harness (1.3 needs Fable's access too).

- **2026-11-02T07:55Z Fable's access passes with the harness-3 request shape.** Fable's requests now carry no vendor output
  format (the schema in the system prompt, the reference tools strict, CPT Studio's own strict parse and validation), merged
  as `225485e2d`. The pre-install access check from a candidate image of `fa457805c` (the installer's copied credentials,
  uid 10150, the installer's hardening, a throwaway database; output leak-scanned) answered HTTP 200 as `claude-fable-5-1`,
  ran the tool loop live (one `cms_code_facts` call, two exchanges) and its reading was read. Both participants' access
  is shown; 1.3 stays open until the installed release's own `app --access-check` repeats it for Corti, Astra and Fable.

- **2026-11-02T10:44Z Correction to the I1 records of 2026-11-01T23:08Z and 2026-11-02T01:30Z (appended, not
  rewritten; refutation round 2, parity-r2-1 and parity-r2-2, both reproduced).** Each record's figures are what its
  instruments printed, but each read them as I1 holding, and I1 covers more than they measure.
  - **What those instruments measure.** The engine parity test: the engine's result on 11 cases whose reference sources
    are built in memory (note `licence`). H1 replay: the engine on the retained regression fixtures, whose reference
    sources keep the round-4 note. H4 battery: the assess child with no reference rows. None of them loads a source
    through the importers, runs the pipeline's stages or re-assesses an encounter.
  - **2026-11-01T23:08Z ("I1 proven"):** the stages and keys and the reference-source entries of a source loaded through
    the importers were not measured. At that commit (`7c79270cd`) `studio/jobs.py`, `studio/review.py` and the
    importers were still the round-4 head's, so those parts had not moved (the note changed at 23:27Z, `ad025537c`),
    but nothing showed it.
  - **2026-11-02T01:30Z ("I1 against the round-4 head: H1 replay EQUAL, H4 battery 0 movements", on `ec00a5b87`):** I1
    did not hold as written. (a) `ad025537c` had changed the note the importers write on the CMS sources, so on an
    installed system every Corti-only assessment's two imported CMS entries and its sha256 differed from the round-4
    head's, and I1 did not say so (parity-r2-1; for the refutation lens's colonoscopy `07315c45fbda` on the round-4
    head and `c961e7e69c35` on the harness, the note the only difference). (b) The pipeline package (`367612adb`) had made the participants record and the
    retrieval traces decide whether a re-assessment is the recorded one, so a Corti-only re-assessment on identical
    inputs after the CMS passages were imported recorded a second assessment, carried the decision onto it and asked
    its question again (parity-r2-2). Neither instrument could see either.
  - **Now (R2-PARITY, branch `wip/harness-r2-parity-20261102`, offline; nothing verified live):** I1 states its one
    exception, the licence note, and the re-persist rule is the round-4 head's with no model participant configured
    (`05860513b`; HARNESS.md 9). `tests/test_harness2_r2_parity.py` loads the CMS tables through the importers and
    pins both digests, and pins the re-persist rule on the round-4 head's paths (14 tests). The I1 pins
    (`tests/test_harness_engine_parity.py`, `CortiOnlyParityTests`) pass unchanged. Against `80f2f2dc8` on
    `05860513b`: H1 replay base to head EQUAL; H4 battery 0 movements, 0 undeclared, 0 new violations.
- **2026-11-02 ~16:30Z (session cd048041): refutation rounds 2 and 3 repaired; checklist 4.6 not done in this release.**
  - Round 2 (32 findings, 31 reproduced, 1 blocking) was repaired by five agents and merged (HARNESS.md 12.9). Round 3
    attacked those repairs: 35 findings, all reproduced (3 blocking, 13 major), every blocking and eleven of the
    twelve majors in the reviewer-confirmation path's "Verified" check; the parity lens found nothing.
  - The session decided D7 (fail closed): this release offers no reviewer confirmation; the participants' located
    passages are still shown, with no verification claim (HARNESS.md 12.10). Item 4.6 is NOT DONE in this release; what
    it becomes is the owner's question, with options (i) and (ii) in its row.
  - Round 3's other repairs (peer shapes, wording, the exchange records) and the integration's trace and problem
    quoting are indexed in HARNESS.md 12.11. A focused fourth refutation of round 3's diff comes before the PR is made
    ready.
- **2026-11-02 ~19:40Z (session cd048041): refutation round 4 repaired.** 24 findings, all reproduced, none blocking;
  the parity lens found nothing again. D8 (no candidate served with confirmations off) and D9 (one strict-shape rule for
  every value a participant wrote that CPT Studio lists or shows) are recorded in HARNESS.md 12.12 with the round's other
  repairs. A focused fifth refutation of round 4's diff comes before the PR is made ready.
