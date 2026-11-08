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

## Stage 1: establish the actual starting point — PASS (1.3 verified live 2026-11-03)

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [x] | 1.1 Installed revision, active work and existing provider integrations; fresh worktree; the shared checkout untouched | PASS | live `80df1831d168` (image `sha256:88544c7cd33f…`) | `docs/cpt-harness/stage1-starting-point.md` §1 (image labels, `docker inspect`, `.git/HEAD`, read 2026-11-01 21:30Z) | — |
| [x] | 1.2 Map of the document-to-code workflow; production clinical reviewers distinguished from engineering agents | PASS | `80df1831d168` | `docs/cpt-harness/stage1-starting-point.md` §2 (FILE:LINE map; Corti the only model reading documents; agent account scripted; engineering agents have no runtime role) | — |
| [x] | 1.3 Backend access to Corti, Astra and Fable: exact provider, API model or endpoint identifier, a minimal synthetic capability check | PASS (verified live 2026-11-03T20:16Z: the installed release's `app --access-check`) | live `41e03656df61` | `app-20261103T201636446797Z.json`: Corti HTTP 200 on `https://api.us.corti.app/v2/tools/coding/` (no model id); Astra `gpt-6-astra` requested and returned; Fable `claude-fable-5-1` requested and returned; each output scanned credential-free before it was recorded; `docs/foundation/reports/2026-11-03-cpt-studio-harness-install.md` | — |

Item 1.3 per participant (documented / implemented / verified live):

| participant | documented | implemented | verified live |
|---|---|---|---|
| Corti | YES: `POST https://api.{us\|eu}.corti.app/v2/tools/coding/`, OAuth client credentials; its API takes and returns no model identifier (`docs/cpt-harness/stage1-starting-point.md` §3) | YES: installed adapter `corti-coding-v2@cptstudio-1` | PASS 2026-11-03 on the installed release: the access check (HTTP 200, 5,024 ms, 0.013192 credits) and the walk's 3 runs (HTTP 200 each). Earlier: 45 live sent runs 2026-10-26 to 2026-10-31, each with `X-Request-Id`. Environment and tenant are still not recorded per run |
| Astra | YES: OpenAI, `gpt-6-astra`, `POST https://api.openai.com/v1/responses`, Bearer (owner-confirmed; `docs/cpt-harness/vendor-and-reference-facts-20261101.md` §1) | YES: adapter `openai-responses@cptstudio-harness-2` (tool loop), offline tests | PASS 2026-11-03 on the installed release: the access check (HTTP 200, `gpt-6-astra` returned exactly, 1,773 in / 503 out, est. $0.0429) and the walk's 6 Astra runs (HTTP 200, each `gpt-6-astra`, each reading read). Earlier: ACCESS PASS 2026-11-02T06:01Z (pre-install check from the candidate image, not yet the installed release): HTTP 200, returned model `gpt-6-astra` (= requested), request `req_f5872cba22da497c87d11b2b6d12a20a`, response `resp_0545e923d6b404e4016ae82723477487d19787aa274210cad8`, 1,773 in / 515 out tokens, est. $0.0435; reading read (45385, nothing refused or unverified) |
| Fable | YES: Anthropic, `claude-fable-5-1`, `POST https://api.anthropic.com/v1/messages` (owner-confirmed; same file §2) | YES: adapter `anthropic-messages@cptstudio-harness-3` (no vendor output format; schema in the prompt; CPT Studio's strict parse), offline tests | PASS 2026-11-03 on the installed release: the access check (HTTP 200, `claude-fable-5-1` returned exactly, two exchanges with one `cms_code_facts` call, 7,273 in / 919 out, est. $0.1187) and the walk's 5 Fable runs (HTTP 200, each `claude-fable-5-1`; hw-03's first reading not used: an extra `reason_detail` field breaks the reading schema). Earlier: ACCESS PASS 2026-11-02T07:52Z (pre-install check from the candidate image `fa457805c`): HTTP 200, returned model `claude-fable-5-1` (= requested), two exchanges with one `cms_code_facts` call (requests `req_011Cgdjn9XqR42Uc5t3eX9JE`, `req_011CgdjnX1eyPN4foZi8aYGp`; response `msg_011CgdjnXBqEtE9GD4Ph3sZF`), 7,254 in / 1,072 out tokens, est. $0.126; reading read (45385, nothing refused or unverified). Earlier: harness-2's request was refused ("compiled grammar is too large", `req_011CgdbDywZBDPP7SehwxfBs`; 12.8) |
| [x] | 1.4 Authorized CPT and reference sources and retrieval tools, with releases, effective dates and permitted uses; unavailable dependencies recorded | PASS | live `80df1831d168` | `docs/cpt-harness/stage1-starting-point.md` §4 (live read: RVU26D 19,453 rows, MUE 2026-Q4 15,212 rows, 2026-10-01 to 2026-12-31; no retrieval stage); `docs/cpt-harness/vendor-and-reference-facts-20261101.md` §3 (each source's release, URL and published terms) | — (usable: RVU26D and its documentation, MUE, NCCI Policy Manual Ch. VI, Claims Processing Manual Ch. 12; unavailable: PTP behind the AMA agreement, AMA content) |

## Stage 2: read the document correctly

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [ ] | 2.1 Original document, hash and revision preserved; Word, native PDF, scanned PDF and pasted text with traceable extraction and OCR | IN PROGRESS (verified live 2026-11-03 for a text-layer PDF, Word and pasted text) | live `41e03656df61` | walk hw-01 (PDF), hw-02 (DOCX), hw-03 (paste): stored original byte-identical to the upload, revision text sha256 checked, extraction method recorded; `docs/foundation/reports/2026-11-03-cpt-studio-harness-install.md` | a scanned PDF (OCR) on the installed release |
| [ ] | 2.2 PDF upload-security repairs and parser safeguards on the applicable paths; encoding, checkbox and extraction failures addressed; an unreadable symbol never becomes a negative clinical fact | IN PROGRESS | — | — | establish CPT Studio's own PDF paths (the rebuild's P1 is installed, but it is a different application); the pypdf 6.21.4 reader repair is deferred (interpretation 68) |
| [ ] | 2.3 Each service represented separately: date, status, anatomy, extent, technique, lesion identity, provider role, exact evidence | IN PROGRESS | — | — | round-4 Wave 1 repair cycle 2 in progress |
| [ ] | 2.4 Shared interpretation defects repaired without patient-specific exceptions; reviewers not fed one interpretation as unquestionable truth; source text and page evidence kept | IN PROGRESS | — | — | cycle 2 drops and narrow fixes; harness input contract |

## Stage 3: three genuine participants

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [ ] | 3.1 Corti receives the supported source and returns proposals; selected codes, alternatives, evidence, raw response and metering preserved unrewritten | IN PROGRESS (verified live 2026-11-03: proposals, the selected code, exact evidence, alternatives and credits) | live `41e03656df61` | the walk's 3 Corti runs: HTTP 200; the selected code with exact evidence spans; alternatives listed as never selectable; credits recorded | raw-response preservation not separately checked live |
| [x] | 3.2 Astra independently examines the source: service facts, proposed codes, missing services, clarification needs | PASS (verified live 2026-11-03) | live `41e03656df61` | 3 independent Astra readings (`gpt-6-astra` returned exactly), each read in the reading schema (services, codes, not-coded items, clarifications); `docs/foundation/reports/2026-11-03-cpt-studio-harness-install.md` | — |
| [x] | 3.3 Fable independently examines the source before seeing Astra's or Corti's conclusions | PASS (verified live 2026-11-03) | live `41e03656df61` | 3 independent Fable readings (`claude-fable-5-1` returned exactly), each before any peer review. 2 were read; hw-03's was not used (an extra `reason_detail` field breaks the reading schema), as recorded on the page and in the reports; `docs/foundation/reports/2026-11-03-cpt-studio-harness-install.md` | Fable's schema conformance: 1 of 3 live readings refused |
| [x] | 3.4 Each participant's model or endpoint, input revision, request identity, output and usage recorded | PASS (verified live 2026-11-03) | live `41e03656df61` | every walk run records its endpoint, requested and returned model, revision, request and response identity, response bytes and usage (14 runs, 14 exchanges); `docs/foundation/reports/2026-11-03-cpt-studio-harness-install.md` | — |
| [ ] | 3.5 Initial assessments independent and FROZEN: Corti, then Astra, then Fable may run in sequence, but each first assessment is built from the same source revision alone, recorded immutably, and fixed before any participant is shown a peer's conclusion (owner, 2026-11-01) | IN PROGRESS (the order verified live 2026-11-03) | live `41e03656df61` | each walk document ran extract, analyze, predict, astra, fable, assess, then astra_peer, fable_peer, assess | the immutability of a first assessment not separately checked live |
| [x] | 3.6 Peer review after the freeze: each model participant is then shown the frozen peer conclusions and CPT Studio's open questions, and answers with verbatim evidence; its peer-review output is recorded separately and never replaces its frozen first assessment; reconciliation follows | PASS (verified live 2026-11-03) | live `41e03656df61` | peer reviews ran after the first assessment as separate runs, each with no unverified quote, and the second assessment followed: hw-01 and hw-02 both used; hw-03 Astra's used, Fable's not sent (its first reading was not read) | — |
| [ ] | 3.7 A documented service Corti omitted can be proposed by Astra or Fable, keeping its actual origin and evidence; never relabelled as Corti's output, never approved automatically | IN PROGRESS | — | engine merge being built (origin `participant`) | build; prove |

## Stage 4: retrieve, validate and reconcile

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [x] | 4.1 Actual reference retrieval: source identity, retrieved passages, release and effective dates, tool traces | PASS (verified live 2026-11-03) | live `41e03656df61` | (a) Fable's `cms_code_facts` calls retrieved 8, 32 and 16 CMS facts and used 3, 4 and 0, each with source, release and effective dates, in the reports' PARTICIPANT REFERENCES (Astra made no call); (b) the assessment traced each approved code's PFS RVU26D and MUE 2026-Q4 facts, and reference validation 6 passages per document | two kinds kept apart (owner, 2026-11-01): (a) the references each PARTICIPANT actually retrieved through its tools and actually cited, with the tool trace; (b) the references the later RECONCILIATION retrieved. Each passage dated (source release and effective window) |
| [ ] | 4.2 Proposals checked against documented services, authorized CPT guidance and payer, bundling and modifier rules | NOT RUN | — | — | — |
| [ ] | 4.3 The complete service inventory reconciled against all three outputs, including services Corti omitted | NOT RUN | — | — | — |
| [ ] | 4.4 Disagreements resolved by source evidence and rules, not majority; contradictions kept; focused questions only where needed | NOT RUN | — | — | — |
| [x] | 4.5 Proposed, reference-supported and reviewer-approved codes kept distinct; no automatic approval from agreement | PASS (verified live 2026-11-03) | live `41e03656df61` | hw-01 and hw-02: all three participants gave the same code, and each encounter stayed ready_for_review until the reviewer's own approval (HTTP 201) made it reviewed | — |
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
| [x] | 6.1 The verified release installed on cpt.quillmd.com with rollback evidence and preservation checks; served revision verified | PASS (verified live 2026-11-03) | live `41e03656df61` | six phase receipts ok through the ruled-act door; the pre-app dump (29 TABLE DATA); rollback image `88544c7cd33f` kept; the must-not-change cross-check (22 containers, 41 volumes, the database container, nginx, co-tenants, app.quillmd.com); /health/ serves `41e03656…`; `docs/foundation/reports/2026-11-03-cpt-studio-harness-install.md` | — |
| [ ] | 6.2 Understandable per-document progress (Corti, Astra, Fable, reference validation, clarification, final status); detailed traces in the administrative view | IN PROGRESS (per-document progress verified live 2026-11-03) | live `41e03656df61` | each walk document's page showed the six rows as the API reports them (Corti, Astra, Fable, reference validation, clarification, final) and the peer-review rows | the administrative trace view not walked |
| [x] | 6.3 Fresh synthetic documents uploaded through an ordinary authorized account; all three participants and reference retrieval proven to execute live | PASS (verified live 2026-11-03) | live `41e03656df61` | hw-01 to hw-03 uploaded through `demo-reviewer` (a human reviewer membership); every Corti, Astra and Fable run HTTP 200; reference retrieval traced; `docs/foundation/reports/2026-11-03-cpt-studio-harness-install.md` | — |
| [ ] | 6.4 Clarification, review and synthetic decisions completed; persistence after reload; actual reviewed reports downloaded and checked against saved state | IN PROGRESS (review, reload and reviewed downloads verified live 2026-11-03) | live `41e03656df61` | 3 approvals (HTTP 201) persisted after reload; reviewed TXT and CSV downloaded and checked against the saved state (verify_downloads 94, 94 and 92 checks, 0 failed) | no clarification arose, so answering one was not walked |
| [x] | 6.5 Automated synthetic decisions labelled accurately | PASS (verified live 2026-11-03) | live `41e03656df61` | each walk approval recorded as "Demo reviewer (synthetic demonstration)" (human) with its note "session-made synthetic acceptance-test approval, not a human review" kept verbatim (interpretation 63) | — |
| [ ] | 6.6 Desktop and mobile verified, including genuine failure and unavailable-provider states | IN PROGRESS (desktop and mobile screenshots of each walk document, 2026-11-03) | live `41e03656df61` | 1440x1000 and 390x844 screenshots per document | genuine failure and unavailable-provider states not walked |

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
| Functional completion | Does the installed harness run Corti, Astra and Fable live, retrieve references, reconcile, and carry a synthetic review through to a reviewed download? | ESTABLISHED: verified live 2026-11-03 by the session on three fresh synthetic documents (`docs/foundation/reports/2026-11-03-cpt-studio-harness-install.md`); the owner's acceptance stays the owner's |
| Clinical validation | Is the coding accurate, as independently established (a qualified coder's adjudication of a predeclared set)? | NOT ESTABLISHED: no independent adjudication exists |
| Content-use permissions | May CPT content be used as the product uses it (D3, D4)? | NOT ESTABLISHED: owner decisions open |

The complete doctor-facing CPT demonstration is NOT READY while any required dependency (D1 to D4) is unresolved.

## External dependencies (one consolidated request)

Sent to the owner 2026-11-01 ~21:30Z. Each dependency blocks only its own live stage; engineering continues meanwhile.

| # | dependency | needed for | protected destination | status |
|---|---|---|---|---|
| D1 | An Anthropic API key with access to `claude-fable-5-1`. A dedicated key inside the existing authorized account QuillMD uses is preferred; QuillMD's key is acceptable if the owner prefers it. It cannot be copied out of `rebuild/.env` by this session | 1.3, 3.3, 3.4, 6.3 | `/etc/cpt-studio-provider-sources/anthropic.env`, root:root 0600 in a root 0700 directory, one line `ANTHROPIC_API_KEY=<key>`; the installer copies it unread to `/etc/cpt-studio/` (10150:10150 0400), mounted into the worker only | RESOLVED 2026-11-02 (placed by the owner; copied by the secrets phase, `docs/foundation/mutations/20261102-cpt-studio-participant-credentials.md`); verified live 2026-11-03 |
| D2 | An OpenAI project API key from an authorized OpenAI project with access to `gpt-6-astra` on the Responses API. No Codex or desktop session token | 1.3, 3.2, 3.4, 6.3 | `/etc/cpt-studio-provider-sources/openai.env`, same ownership and mode, one line `OPENAI_API_KEY=<key>` | RESOLVED 2026-11-02 (placed by the owner; copied by the secrets phase, `docs/foundation/mutations/20261102-cpt-studio-participant-credentials.md`); verified live 2026-11-03 |
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

## Harness repair, 2026-11-05 (owner directive of 2026-11-05)

The owner's directive of 2026-11-05 ("Complete the CPT Studio GI core and multi-agent harness repair, install it on
https://cpt.quillmd.com, and verify the actual customer workflow"), verbatim with the session's interpretation (a)-(k)
in `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`. Integration and deployment owner: session a12d8fb3. The
sections above are kept as the history of the 2026-11-01 directive; this section is the acceptance contract of the
repair.

**Marks (owner, 2026-11-05).** `[ ]` not completed; `[x]` completed and verified, with evidence; BLOCKED names the exact
dependency and the work that can continue independently. Every tick names its revision, its test or live observation,
and its evidence path. Earlier tests, replays and access checks never stand in for fresh installed acceptance.

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [x] | 1. Baseline: project instructions read, preflight run, isolated worktree, no concurrent deployment writer; served revision, configuration and preservation baseline recorded | DONE (live read 2026-11-05 09:03-09:16Z) | served `b0dc3446c64c`; `main` `8645fd54` (no runtime file differs) | `docs/cpt-harness/repair-20261105/stage1-baseline.md`; preflight GO `docs/preflight-reports/preflight-20261105T090526Z.md` (shared tree, untracked by convention) | the preserved counts are compared again at stage 9 |
| [x] | 2. The harness traced for 88d9db32: Corti, Astra and Fable first assessments, peer reviews, references and the final reconciliation; where each missing code was lost, held or made informational | DONE (live records read-only 09:07Z; reproduced offline on `main`) | live records of `b0dc3446c64c`; offline `main` `8645fd54` | `docs/cpt-harness/repair-20261105/stage2-trace-88d9db32.md`: Corti omitted 43249, 45390, 45385 in both answers; Astra and Fable each proposed all six; D14 made the three alternatives; 45381's hold and 45380's anatomy are reader defects; the decompression item is a catalogue gap | — |
| [ ] | 3. Shared interpretation repaired: tattoo versus resection negation, future localization versus future performance, comparison anatomy, lesion ownership; genuine contradictions, failed, historical, planned and other-provider services stay protected; nothing hardcoded | **PARTIAL** (kept partial by the owner's second message, 2026-11-05; carried into its item 4). Partly delivered, installed. Comparison anatomy and lesion ownership repaired; **tattoo versus resection negation and future localization versus future performance NOT delivered** (dropped in refutation round 6); protected services kept protected (nothing READY beyond the previous live revision over 3,050 adversarial rows) | `e6d451f03d86` (installed 2026-11-05T19:15:30Z) | HARNESS.md "Refutation round 1" to "Refutation round 7"; ACCURACY-RESIDUALS.md rounds 1 to 7; tests/test_h2_refutation_r1.py (PackageSentenceTests, MarkedAdverbTests, SecondLesionInOneSentenceTests, RecordedResidualTests and the rest); the seven rounds' lens inputs re-run against main: 0 READY beyond main, 0 D2 flags | the two dropped readings are the owner's to re-open (HARNESS.md round 6 records a restatement-only design) |
| [ ] | 4. D14's blanket prohibition replaced: an explicit Astra or Fable proposal enters human review only after the full source-validation path passes, with equivalent standards whatever its origin; no promotion by quotes, confidence or agreement; raw lists never promoted; no model approves; true origin kept in protected diagnostics; recorded in the contract | **PARTIAL** (corrected 2026-11-05T20:45Z by session a12d8fb3 on new evidence; carried into the second message's item 3). The installed P-ADMIT admits a participant's code only where it accounts for an item Corti's decidable proposals left unresolved, so the standard is not equivalent whatever the origin: on the owner's 39f0ac49 both Astra and Fable proposed 43247, and it was listed as an alternative because Corti's three codes left no open item (`docs/cpt-harness/repair3-20261105/stage1-trace-39f0ac49.md`). The earlier entry, kept: DONE, installed and served. P-ADMIT replaces D14; equivalent standards (D2) held in refutation rounds 1 to 7; live: 88d9db32's 43249, 45390 and 45385 (Astra and Fable's, which Corti omitted) READY through Corti's own validation path; raw alternatives stay informational and are never promoted; no origin on any customer surface | `e6d451f03d86` (installed 2026-11-05T19:15:30Z) | docs/deploy-reports/20261105-cpt-studio-e6d451f0-install-and-walk3.md; 88d9db32 read through the public site (GET only) and scanned; the walk's provenance checks | - |
| [ ] | 5. The complete harness kept: Corti, Astra and Fable participate; first assessments frozen and hashed before peer conclusions are shared; peer reviews stored separately; tool traces and dated provenance kept; a skipped, refused, malformed or failed participant reported as partial completion, never silently substituted | **PARTIAL** (corrected 2026-11-05T20:45Z at the owner's instruction; carried into the second message's items 2, 5 and 6). The complete harness was never proven: Fable's three walk readings were refused by the reading schema, and on h2b the Stop lost Astra's reading and both peer reviews. The earlier entry, kept: DONE, installed. Live on the walk: Corti, Astra (gpt-6-astra) and Fable (claude-fable-5-1) each sent and answered, with request and response hashes, usage and traces; Astra's peer reviews ran after its first reading was frozen (h2a, h2c). Partial participation was reported, never substituted: Fable's three readings were refused by the reading schema (an extra field in not_coded[0]), and on h2b the walk's Stop cut Astra's run short and duplicate prevention refused the resend | `e6d451f03d86` (installed 2026-11-05T19:15:30Z) | docs/deploy-reports/20261105-cpt-studio-e6d451f0-install-and-walk3.md (the walk, the trace, the operator views); the harness's refused and not-sent states as served | Fable's schema refusals and the Stop/resend interaction are recorded limitations, not repaired here |
| [x] | 6. The complete service set reconciled: distinct procedures and lesions, included components, units, potential modifiers; no separate charge for EMR components or prophylactic clipping; decompression investigated without the rejected shortcut; relationships recomputed after clarification and review decisions, on reload and before export | DONE, installed. Live: h2b's EMR lift injection, its own snare and two prophylactic clips are bundled as part of the EMR (no separate charge); a failed snare attempt is not coded; the decompression is listed where no code of its family accounts for it (h2c, 88d9db32); decisions persist after a reload and every download matches them (276 of 276). Recorded: the withheld listing's kindless branch dropped (round 7), moderate sedation outside the coded scope | `e6d451f03d86` (installed 2026-11-05T19:15:30Z) | docs/deploy-reports/20261105-cpt-studio-e6d451f0-install-and-walk3.md; ops/verify_downloads.py 276/276 | - |
| [x] | 7. The doctor-facing page kept simple: CPT numbers, units and modifiers where supported, short source-based reasons, review status, only necessary questions; no provider or model identity, prompt or trace in customer APIs, HTML, accessibility text, browser logs or downloads; truthful stages, elapsed time and failure states | DONE, installed. Every customer API body, header, download and the page bundle scanned on all four encounters (the walk's three and 88d9db32): no provider or model identity, usage, id, hash, trace or rule text; operator URLs 404 to the customer; desktop and mobile screenshots kept | `e6d451f03d86` (installed 2026-11-05T19:15:30Z) | docs/deploy-reports/20261105-cpt-studio-e6d451f0-install-and-walk3.md; /home/claude/cpt-studio-harness2-20261105/acceptance/evidence (screenshots, scans) | - |
| [x] | 8. The finished implementation verified: Linux tests and required CI; an independent refutation of the finished diff with concrete counterexamples (false approvals, negation, time, procedure ownership, multiple lesions, misleading completeness); findings reproduced before repair; failures kept | DONE. Refutation rounds 1 to 7, the last over the whole remaining diff; every finding reproduced before repair, and every failed rule dropped or repaired toward main. Linux full suite 5,905 Django tests OK, ops 524, verification 43, node 131, 63 and 135 (run12). Required CI on the merge commit e6d451f03d86: CI run 42081865874 success (Fresh application tests, on ubuntu-24.04 since PR #1474; Marketing build; Private browser and accessibility); secrets-scan run 42081865855 success; cpt-studio run 42081866049: its checks, migrations and every test pass (5,905 Django, 524 ops, 43 verification, node 131), and its dependency audit is red on pypdf 6.21.2's seven advisories (interpretation 68), as on main since 2026-10-31; cpt-studio is not a required check | `e6d451f03d86` | HARNESS.md rounds 1 to 7; /home/claude/cpt-studio-harness2-20261105/ci/run12/summary.txt; the battery (2 declared movements, 0 undeclared, 0 new violations) and replay (labels only) against main | - |
| [x] | 9. Installed through the project gates with a declared, reversible, available deployment; 88d9db32 re-assessed from retained responses with sends disabled; the prior assessment and decisions kept; served behaviour verified and remaining omissions explained | DONE. Installed blue/green through scripts/run-ruled-mutation.sh from the declaration's checkout: 305 availability samples all 200; no migration; no state recomputed; nothing sent. 88d9db32 re-assessed from its retained responses with nothing sent, the six declared table movements and no other; its prior assessment and decisions kept; served behaviour verified; remaining omissions explained in the record | `e6d451f03d86` (installed 2026-11-05T19:15:30Z) | docs/deploy-reports/20261105-cpt-studio-e6d451f0-install-and-walk3.md; the receipts in /home/claude/cpt-studio-install-20261023 | - |
| [ ] | 10. Fresh live acceptance: a small new synthetic set (Word and PDF), expected services and provisional coding fixed before outputs are read; actual Corti, Astra and Fable participation; review decisions, reload persistence and an actual downloaded report matching them; agent-executed approvals labelled | **PARTIAL** (kept partial by the owner's second message; carried into its items 6 to 8). Run, not all passed. Three fresh synthetic documents (a PDF, two Word), sealed before any code read them: h2a PASS (148 hard checks); h2b and h2c fail 2 and 1 hard checks: the routing reader's family label (historical, uncertain; the same at main), and h2b's peer reviews. All expected codes READY except 43248 (held for a question) and h2b's sedation codes (out of scope); every agent approval labelled; reload persistence and the downloaded reports match the decisions; Fable answered but its readings were refused by the schema | `e6d451f03d86` (installed 2026-11-05T19:15:30Z) | docs/deploy-reports/20261105-cpt-studio-e6d451f0-install-and-walk3.md; evidence.json and downloads-verified.json in /home/claude/cpt-studio-harness2-20261105/acceptance/evidence | the routing label, the Stop/resend interaction and Fable's schema refusals are recorded; none is repaired in this release |

**Verdicts (three, kept separate).** Functional completion, clinical accuracy and content-use permissions are reported
apart. A passing synthetic case is never reported as guaranteed accuracy, and missing reference coverage is never
invented.

## Harness repair 3, 2026-11-05 (owner directive of 2026-11-05, second message)

The owner's second message of 2026-11-05 is recorded verbatim, with the session's interpretation (a)-(k), in
`docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` ("Owner directive, 2026-11-05 (second message)"):
- Astra and Fable are primary code-finding participants.
- Corti is another contributor, not a whitelist or veto.
- An explicit, source-supported proposal reaches human review whatever Corti did with the code.

Integration and deployment owner: session a12d8fb3. The section above stays as the history of the morning's directive,
with its items 3, 4, 5 and 10 now partial. This section is the acceptance contract of the third repair, under the same
marks: `[ ]` not completed; `[x]` completed and verified with current evidence; BLOCKED names the dependency.

| | Item | Status | Revision | Evidence | Remaining action |
|---|---|---|---|---|---|
| [x] | 1. Diagnose the current omission: parsing, admission, interpretation, catalogue, bundling, documentation or display; original result and raw responses preserved | DONE (live records read-only 2026-11-05T20:26-20:40Z; reproduced offline on the installed code) | live `e6d451f03d86`; offline the same code on the throwaway copy `cpth3_base` | `docs/cpt-harness/repair3-20261105/stage1-trace-39f0ac49.md`. 43247 on 39f0ac49 was proposed by both Astra and Fable (first readings, exact quote), never returned by Corti, and refused at **admission**: the gap-filling P-ADMIT found no open item. It found none because the **interpretation** reader has no act for "the bolus was removed" ("food bolus" only). A second **interpretation** defect, inline labels inside the Indications section, held all three Corti codes "uncertain". The owner's six "Not documented" answers then excluded them. Not clinically justified. Runs, raw bytes (hashes verified), both assessments and the answers are preserved | the repairs are items 3 and 4; the final outcome is item 8's reassessment |
| [x] | 2. Fable's response contract repaired without disabling validation or silently discarding clinically meaningful content; raw output preserved and the normalized result validated; a fresh real Fable response accepted and contributing | DONE, installed and verified live 2026-11-06. harness-4 asks for exactly the schema's fields and sets an undeclared field aside before validation (named in the problems by place and size, never read); everything else is validated as before. Live on the fresh walk: both of Fable's first readings (h3a, h3b) were accepted (refused false, no problems, no unverified quote) and contributed (h3a: 43247, 43239, 45385, 45381; h3b: 45385, 45380), and both Fable peer reviews ran | live `fd8040d71e44` (installed 2026-11-06, app phase 05:14:12-05:17:03Z) | `docs/deploy-reports/20261106-cpt-studio-fd8040d7-install-and-walk.md`; the walk's operator traces; `tests/test_participants_reading.py` FableContractTests | - |
| [ ] | 3. Genuinely independent admission: only Astra proposes a supported service; only Fable does; Corti disagrees and the document supports the proposal; models agree on an unsupported, denied or historical service; a number only in an alternative list | **PARTIAL**: installed; verified live in part, and failing live for one act class. Live: 88d9db32's 43249, 45390 and 45385, proposed only by Astra and Fable, are READY on CPT Studio's own reading. ⚠️ **Fails for the food-bolus act:** on the fresh h3a and on the owner's 39f0ac49, Astra's and Fable's explicit, exactly quoted 43247 is listed as not done on the date of service and is not reinstatable, so no reviewer can approve it (F-ACTS was dropped in cycle 4). The single-proposer, Corti-disagrees and agree-on-unsupported cases are proved offline (pinned tests), not on a live document | live `fd8040d71e44` | `docs/deploy-reports/20261106-cpt-studio-fd8040d7-install-and-walk.md` ("What did not reach review"); `tests/test_h3_repairs.py` AdmissionCaseTests; `tests/test_h3_refutation_c3.py` CycleThreeAdmissionTests | the food-bolus act needs a reader rule that holds under refutation; until then this item is not met |
| [ ] | 4. Remaining interpretation defects: tattoo versus resection negation, completed marking versus future localization, historical references inside current reports, the demonstrated Word routing errors; "not snared", "never removed", prior and other-provider procedures and contradictions protected; actions bound to their own procedure, lesion and time; no hardcoding; the rejected decompression experiment not restored | **PARTIAL**: installed. Live: h3b's failed sigmoid hot-snare attempt produced no second 45385 (F-TIME F), and its 2025 referring-facility procedures produced no READY code (F-TIME P); 88d9db32's 45381 is READY with no false tattoo conflict (F-NEG S). ⚠️ **Still undelivered (dropped under the two-cycle rule):** completed marking versus future localization (F-TIME R); the Word routing errors and labelled paragraphs (F-SECTIONS T and L: h3a's three codes held for questions, h3b's routing check failed, both main-equal); the food-bolus act (F-ACTS). The decompression experiment is not restored | live `fd8040d71e44` | `docs/deploy-reports/20261106-cpt-studio-fd8040d7-install-and-walk.md`; `cpt-studio/HARNESS.md` cycles 2 to 4 | the dropped items stay open (owner-visible) |
| [x] | 5. Recoverable Stop/Resume: duplicate prevention kept; the original request's outcome reconciled before a new attempt; no blind resend, no reset identity, no participant lost by a Stop; attempt lineage preserved; recovery proved without duplicate submissions | DONE, installed and verified live 2026-11-06 on h3b. The Stop landed (05:25:03.066Z) while Astra's first exchange was in flight; that exchange's answer was recorded and nothing more was sent. Resume (HTTP 201) continued the tool loop from its verified record with one new exchange. The stopped exchange was not sent again: its request sha256 appears once in the trace, and the chain keeps it as its request identity. No participant was lost: Fable, both peer reviews and the final assessment followed. Both runs are kept, and all 19 Stop and Resume checks pass. The unknown-outcome branch (an exchange whose answer never arrives) is proved offline only | live `fd8040d71e44` | `docs/deploy-reports/20261106-cpt-studio-fd8040d7-install-and-walk.md` ("Stop and Resume on h3b"); the h3b operator trace; `tests/test_participants_loop.py`; `tests/test_harness2_pipeline.py` StopInLoopTests | - |
| [x] | 6. The complete harness proved on a fresh case: usable real Corti, Astra and Fable first assessments, frozen before peer access, peer reviews stored separately; any refused, malformed, interrupted or skipped response is PARTIAL | DONE for participation, verified live 2026-11-06 on h3a: real Corti, Astra (`gpt-6-astra`) and Fable (`claude-fable-5-1`) first assessments, every one usable (nothing refused, malformed, interrupted or skipped). They were recorded, and the first assessment was made, before any peer request (the server's activity: first assessment 05:23:54.78Z, first peer request 05:23:54.89Z). Peer reviews are stored as their own runs. h3b also completed all three, with Astra's first reading interrupted by the deliberate Stop and completed by Resume. ⚠️ **Participation only:** what CPT Studio then did with Astra's and Fable's 43247 on the same document is item 3's failure, and complete three-engine operation is not claimed | live `fd8040d71e44` | `docs/deploy-reports/20261106-cpt-studio-fd8040d7-install-and-walk.md`; evidence.json (provenance checks) in /home/claude/cpt-studio-harness3-20261105/acceptance/evidence-h3 | - |
| [ ] | 7. Review, reconciliation and downloads: relationships recomputed after clarification and review decisions, after reload and before export; valid bundling, distinct-lesion relationships and unresolved modifier and reference limitations kept; saved decisions and an actual download verified; provider identities and traces only in protected operator diagnostics | **PARTIAL**: installed; verified live in part. On h3b both decisions were saved and persisted after a reload, and the approved TXT and CSV were downloaded and verified (166 of 166 checks across the walk's six files). On h3a the approved download was withheld while three codes need a detail. Provider identities, models, usage and traces appear only in the operator view (the customer scan: 27 of 27 checks, 0 hits, operator URLs 404). Not walked: answering a clarification and the recomputation after it. 39f0ac49's question set was not re-checked live | live `fd8040d71e44` | `docs/deploy-reports/20261106-cpt-studio-fd8040d7-install-and-walk.md`; verify-h3/downloads.json and verify-h3/scan/scan-evidence.json in /home/claude/cpt-studio-harness3-20261105/acceptance | a clarification answered and recomputed live; 39f0ac49's question set |
| [ ] | 8. Tested and installed: required Linux tests and CI; an independent refutation of the finished diff; regressions repaired without weakening safeguards; a declared, reversible install; retained cases re-assessed with sends disabled, then a small fresh Word and PDF acceptance set; all previous records, failures and approvals preserved | **PARTIAL**: every step ran, and the acceptance set did not pass. Linux tests and CI on the merge commit: CI 42159987582 and secrets-scan 42159987651 success; cpt-studio 42159987583 passes every test, its audit red on the accounted pypdf advisories. Four refutation cycles over the finished diff. Installed blue/green through the ruled-act door from the committed declaration: 299 availability samples, all 200; the rollback image kept. 88d9db32 and 39f0ac49 were re-assessed from retained answers with nothing sent, and exactly the declared rows moved. Previous records, decisions and answers are kept. The fresh acceptance set was walked: h3a (PDF) fails 2 hard checks and h3b (Word) 1, all routing and main-equal, and h3a's expected 43247 cannot reach review | live `fd8040d71e44` | `docs/deploy-reports/20261106-cpt-studio-fd8040d7-install-and-walk.md`; the receipts in /home/claude/cpt-studio-install-20261023; `docs/foundation/mutations/20261106-cpt-studio-harness-repair3-install.md` | the acceptance failures are items 3 and 4 |
| [x] | 9. Release readiness reported honestly: the corrected checklist and evidence paths, the installed revision, 39f0ac49's code and its verified outcome, proof that Astra and Fable both contributed usable live results, fresh acceptance and download results, the remaining clinical, security, reference and licensing limitations; the PDF advisories resolved or accounted for | DONE: reported in `docs/deploy-reports/20261106-cpt-studio-fd8040d7-install-and-walk.md`. It covers this checklist and the evidence paths; the installed revision `fd8040d71e44`; 39f0ac49's 43247 (listed, not approvable) and its three held codes; Astra's and Fable's live contributions; the walk's acceptance and download results; and the remaining clinical, security, reference and licensing limitations. The pypdf advisories are accounted for, not resolved (`docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md`). The report states that the GI release is not complete | live `fd8040d71e44` | `docs/deploy-reports/20261106-cpt-studio-fd8040d7-install-and-walk.md` | - |

## Completion repair, 2026-11-06 (owner directive of 2026-11-06)

The owner directive of 2026-11-06 is recorded verbatim, with the session's interpretation (a)-(m), in
`docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`. The contract is `cpt-studio/HARNESS.md`, "Completion repair
(2026-11-06): the completion contract", criteria C1 to C9. This section is the live state: one owner, one table and
the progress log below.

**Marks.**
- Status is NOT RUN, IN PROGRESS, PASS, FAIL or BLOCKED.
- Kind is IMPLEMENTED, VERIFIED OFFLINE or VERIFIED LIVE.
- `[x]` only when the item's acceptance evidence passes.
- A passed item is reopened when later evidence disproves it.

### Checkpoint

| field | value |
|---|---|
| owner | session 30a58364 (integration and deployment) since 2026-11-07T15:15Z; a12d8fb3 ended at ~11:59Z with its hold taxonomy half done, and the work was recovered from its records |
| objective | the installed website assesses an uploaded GI PDF or Word document with Corti, Astra and Fable, supported proposals reach review, decisions persist, and the download matches them |
| installed | `aeae34bebbe5` at https://cpt.quillmd.com since 2026-11-08 (app phase 06:54:55-06:57:47Z; declaration `docs/foundation/mutations/20261108-cpt-studio-recall-round-install.md`; record `docs/deploy-reports/20261108-cpt-studio-aeae34be-install-and-walk.md`); rollback image `cpt-studio:73dcf8b4b40a` |
| candidate | branch `fix/cpt-studio-structure-round-20261108` (the structure round: U14, U16 and U18 repaired at twin parity; labels gi-routing@12, gi-services@7); not yet merged |
| current stage | the structure round integrated offline: U14 (direct-reach twin), U16 (full twin) and U18 (computed heading twin) each refuted in two cycles and kept, with the integrator's narrowing completions; the judge equals the installed figures in every row; c4b and c4c read every expected code READY offline, c4a 45385 (its other three codes stay held as its twin holds them); U24 withdrawn after both its hold forms were refuted; U25-U27 open; the final refutation pass over the integrated diff next |
| next action | the final refutation pass over the integrated diff, the full suite on the final head, the PR and its citation, the merge, the install by declaration, then the blind c5 walk |

### Unresolved defects (each closed only by acceptance evidence)

| id | defect | evidence | status |
|---|---|---|---|
| U1 | Astra's and Fable's explicit 43247 for a food-bolus removal ("the bolus was removed") is listed as not done and is not reinstatable. Two causes: the act's vocabulary (services.py:252) and its binding with no part family and no site while two families are present (services.py:3907-3940, :5118-5134) | d44a77b3 (h3a), 39f0ac49; stage-1 trace; corpus D\|AB-B1 to B5, D\|CASE-d44a77b3 | OPEN |
| U2 | procedure narratives after inline labels are read as part of the Indications (sections.py:398, :405, :409-410, :752; detect.py:2162-2164), and the services reader folds that doubt over its own performed reading (services.py:5943-5959) | d44a77b3 and 39f0ac49; stage-1 trace; corpus D\|ARCH-D1a | OPEN |
| U3 | a failed sub-act's "was unsuccessful" or "could not be passed" is read as the examination's incompleteness (cues.py:450-451, :470; detect.py:5856-5913, :6492, :7724-7729); an EGD's extent is rewritten too (detect.py:6020-6022) | e888f9ce (h3b); corpus WRONG FLAG entries (e888f9ce, a1, a2, d1, d2, D2a) | OPEN |
| U4 | a report title with an aside is silent (cues.py:727), and an instrument's own course is never a family mention (detect.py:115-122). U3 masks it: repairing U3 alone turns e888f9ce PLANNED (detect.py:6502), so U3 and U4 are one repair | e888f9ce; corpus D\|ARCH-D9, D\|RT-c1, D\|ARCH-D1b | OPEN |
| U5 | a completed marking for future localization is read as future (F-TIME R dropped); routing reads d44a77b3's tattoo "planned: future" | HARNESS.md "refutation cycle 2"; repair 2 round 6; corpus group A F-TIME R (35) | OPEN |
| U6 | false READYs: the base's 53 (with "The polyp was left in place.", C3-4-4, 5, 8, 10, 11 and 12); a failed act sharing the Procedure line promoted to performed (services.py:5181-5183); F1, F-NEG S reading three of the earlier repair's counterexamples READY (services.py:542-546, :857-859, :2724); F5's "It is unknown whether ..." | corpus groups B and A (F5), D\|RT-f1, f3, D\|ARCH-D3a | OPEN |
| U7 | false holds: the base's 66, the competition holds F4 (4), and the stage-1 minimal pairs (11) | corpus groups C, A (F4) and D | OPEN |
| U8 | asymmetries: a participant's code for a doubted act is listed where Corti's is held (`engine._in_doubt`); every participant alternative is non-reinstatable (engine.py:3935) | L4-4; stage-1 trace | OPEN |
| U9 | "not documented" and "does not establish" said from absence, not a passage: engine.py:549, :719-722, :3381-3382; reconcile.py:236-238; checks.py:579, :705, :743; customer_api.py:456-467; review_view.py:455-458 (the summary contradicts the reader's own performed biopsy) | stage-1 trace (c1-questions) | OPEN |
| U10 | every proposal question offers only excluding answers (answers.py:475-478, :648-660); a held code's only action is Reject (review.py:431-437) | 39f0ac49: three codes excluded, reviewed report with no billable code | OPEN |
| U11 | no answer recomputes the assessment (answers.py:705-711; the engine has no member-answer input); stored questions stay open while the customer page says answered (serializers.py:155-156); answers bind only to (revision, code, family, fact), so 39f0ac49's engine@7 answers exclude engine@8's codes (models.py:430-446; answers.py:347-362) | stage-1 trace (c1-questions) | OPEN |
| U12 | one fact, three readers: section kind, act status (copied, then counted again as a second opinion), date binding, performer, extent, lesion, segmentation; each with a measured disagreement | stage-1 trace, "One fact, three readers"; corpus group D | OPEN |
| U13 | adjacent: the interventions fact lists a failed attempt's "hot snare" (detect.py:5921-5935); "right and left colon" reads as the descending colon (services.py:102, :3713); "the polyp was left in place" leaves the disposition unknown (services.py:6004-6018) | e888f9ce; stage-1 trace | OPEN |
| U14 | walk finding 3: a coordinated reach after a relative aside ("advanced into the stomach, which was normal ..., and through the pylorus to the second portion of the duodenum") reads the first landmark's incomplete extent; codes stay READY with a false incompleteness warning | c2b; ACCURACY-RESIDUALS.md "The walk round"; two forms of a continuation reader refuted and dropped under the two-cycle rule | IN PROGRESS (the structure round, 2026-11-08: a long reach read through its DIRECT-REACH TWIN, u14a3 - offline, c4c reads D3 and 43239 READY; a lead aside set off by punctuation reads no motion, fail closed; parity residuals in ACCURACY-RESIDUALS.md "The structure round"; installs with the round; closed only by acceptance evidence). Before: two forms of a continuation reader refuted and dropped (the walk round); the blind c4 walk (2026-11-08): c4c's EGD reach read no extent (43239 held) |
| U15 | walk finding 2: in a report of both examinations a site-less dilation past the binding's cut ("the scope was withdrawn over the wire. Savary-Gilliard dilators ... were then passed over the wire") is held - 43248 needs clarification | c2a; ACCURACY-RESIDUALS.md "The walk round"; the binding's exceptions and the device-tract binding each refuted twice and dropped under the two-cycle rule | OPEN |
| U16 | walk finding 4: a bolus "captured and brought out through the mouth" states no removal the reader reads - 43247 needs clarification | c2b; ACCURACY-RESIDUALS.md "The walk round"; the out-words as done participles and the route-bound removal each refuted twice and dropped under the two-cycle rule | IN PROGRESS (the structure round, 2026-11-08: a removal today's narrative and Impression corroborate read as its FULL TWIN reads it, u16c3 - offline, c4b's 43247 READY; installs with the round; closed only by acceptance evidence). Before: two approaches each refuted twice (the walk round); the blind c4 walk (2026-11-08): c4b's bolus "captured ... and brought out through the mouth" (43247 held) |
| U17 | a guide wire's brand name or a habitual statement read as a dilation done, inside a label's binding (43248 READY on 6f306af1 and 73dcf8b4) | the walk round's fourth lens (parity notes A1_ctl_inside, Aocc_usually_inside); ACCURACY-RESIDUALS.md | OPEN |
| U18 | the labelled release refused on ordinary content (N1 "from both"; N3 a consent sentence; N2 a hard-wrapped "score 8:"; latent N1 signals) | c3a; ACCURACY-RESIDUALS.md | IN PROGRESS (the structure round, 2026-11-08: a held labelled paragraph released only where the installed readers, run on its computed HEADING TWIN, read every fact the same, u18d + the guard's span bound - offline, c4a's paragraphs released and 45385 READY; c4a's 43239, 43248 and 45381 stay held as the twin holds them (U19's organ-list form, U15, the tattoo's status); withdrawn, as installed, after a field line with no final period, a U14 motion inside the paragraph, or blanks before the colon; installs with the round; closed only by acceptance evidence). Before: two release-gate variants refuted (the recall round); the blind c4 walk: c4a refused by N1 on "at the bite block", the colonoscopy paragraph by P4 after it |
| U19 | a reach stated by findings, not by a reach verb (a landmark list with its verb after it; an organ-by-organ findings list; a verbless depth sentence) | c3a, c3b, c3c; ACCURACY-RESIDUALS.md | IN PROGRESS (the recall round: the findings-stated reach, implemented and verified offline - development 36 -> 31 held, the c3 organ-list shapes still read as installed; parity residuals in ACCURACY-RESIDUALS.md; installs with the round); the structure round (2026-11-08): c4a's "The rest of the esophagus, the stomach (including retroflexion) and the duodenum to the second portion were normal." still reads no reach (43239 held; its heading twin holds it too) |
| U20 | numbered "PROCEDURE n - X" headings open no section (under HISTORY every act reads historical) | c3c; ACCURACY-RESIDUALS.md (the recorded gap a) | OPEN (the recall round: two mechanisms refuted twice each and dropped - the numbered part inside the shared layout, and a same-length reading twin; HARNESS.md "The recall round") |
| U21 | a stated date of service in a form the reader does not read ("16-Nov-2026", "9 November 2026", a weekday before the date, a head "Date of Operation:", a head "Exam date:" the reader reads but never sends) leaves the document undated: every code held for the date | held-out corpus: 10 of 24 documents, 17 of 25 holds; owner decision 2026-11-07 (read the unambiguous forms; not two-digit years) | IN PROGRESS (merged `aeae34bebbe5`: on the held-out corpus undated documents 10 -> 0 and held codes 25 -> 20, newly held 0; installs with the round; closed only by acceptance evidence) |
| U22 | the participant and peer stages send on a context an earlier version recorded without remaking it (a chain queued across an install, resumed after a Stop, or swept) | the recall round's refutation of the gi-context@4 retirement (refute/retire: flows #0 and #1, data #0); pre-existing on the installed release for @1 to @3 | OPEN (unreachable on the live copy: no in-flight or stopped chain on an earlier context) |
| U23 | a member's answer, withdrawal or reconciliation on an encounter whose context an earlier version recorded is applied without a re-assessment: the overlay applies an answer to the stored assessment (a false 'reviewed' with an approved export where the current engine reads differently), a withdrawal leaves a blocker nothing clears, a reconciliation's participant attempt is not made | the same refutation (flows #2 and #3, data #1 and #2); the live controls a8e50085, fbdd6d27, 30d3f32d and 212ed78d ('reassessing': false); an unchanged context save or an addendum reads the encounter under the current rules | OPEN (43 live encounters' contexts are @1 to @3) |
| U24 | an installed false READY: "<n> <units> back" read by no reader, so an earlier act told with it reads as today's ("Some months back a 6 mm polyp in the sigmoid colon was removed with a cold snare": 45385 READY; its "ago" twin held in every layout) | found by the structure round's u24 lenses; design-r2/corr/u24_m4.py, u24_resolve.py; HARNESS.md and ACCURACY-RESIDUALS.md "The structure round" | OPEN (two hold forms integrated and refuted: the reading form gained 48 false READYs, the outcome hold a rival code's READY through the competition and 567 non-parity holds; WITHDRAWN from the round; the next approach recorded: a final hold decided by the installed engine's reading of the whole ago twin) |
| U25 | an installed false READY: a report that disowns itself is read as written ("... was removed with a cold snare. Entered on the wrong patient; please disregard.": 45385 READY) | found by u18a's release lens; design-r2/briefs/u25.md | OPEN (two designs refuted and dropped: a broad disowning reader; explicit self-reference only) |
| U26 | an installed false READY (the directive's item 4: "a polyp explicitly left in place"): a removal instrument's transit read as the removal ("A cold snare was passed through the channel, and the polyp was then left in place because she takes apixaban.": 45385 READY) | found by u18c's release lens; design-r2/corr/left_in_place.py | OPEN (the inventory, the code's evidence reading and the outcome hold each refuted or unsound - HARNESS.md "The structure round"; its sandbox design-r2/u26d kept for the next round) |
| U27 | an installed false READY: a revisit to a prior act's object read as that act ("The stent in the distal esophagus was reached and was in good position.": 43266 READY; the polypectomy site "reached and was clean": 45385 READY) | found by u18c's release lens; design-r2/corr/object_noun.py | OPEN (as U26; its sandbox design-r2/u27d kept) |
| U28 | an installed blind spot: a today word inside a dated lead's aside outranks the lead's date ("On 10/14 - unlike today - the gastroscope was advanced to the third portion of the duodenum.": D3, 43239 READY) | found while deciding U14 (design-r2/corr/u14_leadaside.py) | OPEN (not created by the round: U14's direct-reach twin is this sentence, and U14's own lead-aside guard holds the long form) |
| Q1 | owner question (class (a)): does 43247 cover a food bolus pushed into the stomach? 13 corpus entries wait on it | corpus RULING entries | OWNER |
| Q2 | owner question: two dilation techniques on one stricture (an NCCI question; NCCI unconnected) | corpus | OWNER |
| L1 | pypdf 6.21.2's seven denial-of-service advisories: accounted for, not resolved | `docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md` | LIMITATION, reported until resolved |
| L2 | NCCI PTP unconnected; D3 to D5 open | External dependencies above | LIMITATION, reported separately |

### Items

| | Item | Status | Kind | Revision | Evidence | Next |
|---|---|---|---|---|---|---|
| [x] | 1. Establish the exact remaining failures (C1) | PASS | VERIFIED OFFLINE | `fd8040d71e44` (branch `studio/` identical) | `docs/cpt-harness/completion-20261106/stage1-trace.md`; `tests/test_completion_corpus.py` | - |
| [ ] | 2. Repair the shared document interpretation (C2) | IN PROGRESS | IMPLEMENTED, VERIFIED OFFLINE | `443740630` | `cpt-studio/HARNESS.md` "Stages 2 to 5"; `docs/cpt-harness/completion-20261106/corpus-repin.md` | install; the walk (C7) |
| [ ] | 3. Preserve equal proposal eligibility (C3) | IN PROGRESS | IMPLEMENTED, VERIFIED OFFLINE | `443740630` | `docs/cpt-harness/completion-20261106/table-repin.md` (no participant row reads differently from Corti's selection) | install; the walk (C7) |
| [ ] | 4. Fix false positives as well as false holds (C4) | IN PROGRESS | IMPLEMENTED, VERIFIED OFFLINE | `443740630` | corpus: no FALSE READY beyond the installed baseline; FALSE READY 57 to 35, FALSE HOLD 81 to 59 (39 and 51 at integration; cycles 2-4 re-pinned, the differential round moves none) | install; the walk (C7) |
| [ ] | 5. Make questions and statuses truthful (C5) | IN PROGRESS | IMPLEMENTED, VERIFIED OFFLINE | `443740630` | `tests/test_completion_answers.py` (the chain, the binding, D7 unchanged) | install; the walk (C7) |
| [x] | 6. Prove the repair against retained evidence first (C6) | PASS | VERIFIED LIVE | `6f306af1b030` | the four retained encounters re-assessed on the installed revision read exactly as predicted (39f0ac49 43239, 45380, 45385, 43247 READY; d44a77b3 43239, 45385, 45381, 43247 READY; e888f9ce 45385, 45380 READY, no incompleteness flag; 88d9db32 its six READY); `docs/deploy-reports/20261107-cpt-studio-6f306af1-install-and-walk.md` | re-run after any repair (reopened if disproved) |
| [ ] | 7. Complete meaningful independent acceptance (C7) | FAIL | VERIFIED LIVE | `6f306af1b030` | the walk on cpt.quillmd.com: blind c2 1 of 3 (c2c pass; c2a, c2b fail), c1 1 of 3 (c1a pass; c1b, c1c fail); every failure a hold or an instrument/privacy finding, no false READY; Stop/Resume, answers, addendum, reload persistence and downloads observed working; `docs/deploy-reports/20261107-cpt-studio-6f306af1-install-and-walk.md` | the next round, then a fresh blind set c3 |
| [ ] | 8. Install and verify the served result (C8) | IN PROGRESS | VERIFIED LIVE | `6f306af1b030` | installed via the ruled-mutation door, every declared row matched, nothing sent, rollback image kept; the served walk found the addendum response carrying an internal revision id (finding 7, pre-existing) | with the next round's install |
| [ ] | 9. Close with evidence of the result (C9) | NOT RUN | - | - | - | last |

### Tests, provider runs, usage and receipts

- **Stage 1 (VERIFIED OFFLINE, `fd8040d71e44`):**
  - the four retained cases recomputed in memory, each identical to its stored assessment, twice and independently;
  - the corpus's 815 inputs measured twice (the lens and the session), all readings identical;
  - `tests.test_completion_corpus`: 3 tests OK in 7.4 s; mutation-proved (bare "bolus": 82 failures, the file
    restored byte-identical);
  - the export traced with the report's own snapshot, read-only.
- **Tests on the candidate (`89fe6328f38d`, VERIFIED OFFLINE):**
  - the full CI-like suite: 6,229 Django tests OK in three chunks, ops 524 OK, verification 43 OK, the node suites 131, 65 and 135 passing, check and makemigrations clean (second run, 2026-11-06T14:33:40Z to 14:50:18Z);
  - the completion corpus re-pinned (627 entries; no FALSE READY beyond the installed baseline), the refutation
    tables re-pinned with every moved row classified, the freeze gate on the full corpus (holds), the H4 battery
    (10 declared movements, 0 new violations), the H1 replay (the labels alone), the Corti-only parity (byte-identical
    to harness repair 3's pins once the labels are set back), the installer suites (350 OK).
- **Provider runs and usage in this repair:** none sent.
- **Deployment receipts:** none yet. Earlier receipts are in /home/claude/cpt-studio-install-20261023.

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
- **2026-11-03 ~00:55Z (session cd048041): refutation round 5 repaired.** 20 findings, all reproduced, one major (the
  reports printed CPT Studio's own, inverting reading of a participant's peer answer as its answer), none blocking. D10
  (the reports print no peer-answer value), D11 (the Clarification row only counts), D12 ("proposed" only with a located
  quote, everywhere) and D13 (one unlisted count) are recorded in HARNESS.md 12.13 with the round's other repairs and
  W1, a walk-tool false rejection fixed at integration. A narrow sixth refutation of round 5's diff comes before the PR
  is made ready.
- **2026-11-03 ~07:30Z (session cd048041): refutation round 6 and the owner's D10/D12 meaning check repaired.** Round 6:
  12 findings, all reproduced, all minor. Its repairs are the D12 account in the engine, the reports and the trace; the
  Clarification row's null count while an addendum's revision is unassessed; listedText; and the access check's own
  words. The meaning check: 15 findings, all reproduced, 10 of them blocking. In each blocking one a code was READY on a
  verbatim quotation of a failed act, a denial, another procedure's sentence, a pathology addendum, or an indication or
  history line. The session's D14 closes the harness path: in this release a participant's code is never a proposal.
  The integration repaired three sentences D14 made false. The same readers' false READY on Corti's own selections is
  pre-existing on the installed Corti-only path (I1-pinned). Two of its classes were already accepted residuals (r1
  release-0 and release-1). It is recorded in HARNESS.md 12.14 as the first target of the shared-reader repair, and
  pausing the live demonstration is put to the owner. The shared-reader repair's design recommends that no rule
  release the three false holds now, and it found two more installed false READYs. 4.6 stays NOT DONE. D14's owner
  question and the release-standard question (the round-4 standard or parity) are open. Before the
  PR is made ready, a narrow seventh refutation of `de6418fc6..` the integrated head runs as the standing gate
  requires.
- **2026-11-03 ~09:30Z (session cd048041): refutation round 7 repaired.** The narrow seventh refutation of round 6's and
  the meaning check's repairs filed 14 findings, all reproduced, two major. D14's core promise held: no participant's
  code became a proposal or changed how a Corti proposal is decided. The repairs, each with a failing pin and a mutation
  proof (HARNESS.md 12.15):
  - Only the proposal provider's codes are traced. A participant's alternative had given Corti's 45378 an
    endoscopy-family rule, and reference validation had counted it as a code checked.
  - participants.summary's closing sentence and the participants-only blocker and panel say only what is true.
  - A participant's service is worded with the inventory's not-done reading only where CPT Studio reads it inside the
    quoted passage. Round 6's repair had attached a Plan line's reading to another sentence, in the reviewed report.
  - A participant's verbatim quote is never called an evidence passage.
  - The source panel never titles "Evidence for" a passage its chip says does not show the coded act.
  - The Final status row never says an assessment of an unassessed revision was made.
  - The access check's remaining request count is corrected.
  - Two pins are hardened.
  Because round 7 found a defect that a repair itself introduced, a narrow eighth refutation of round 7's repair commit
  runs before the PR is made ready. 4.6, D3-D5, D14's owner question, the release-standard question and interpretation
  68 stay open.
- **2026-11-03 ~11:00Z (session cd048041): refutation round 8 repaired.** The narrow eighth refutation of round 7's repair
  commit filed 11 findings, all reproduced, two major. I1 held. The repairs, each with a failing pin and a mutation proof
  (HARNESS.md 12.16):
  - Only a decidable proposal's code is traced, never an alternative's. A code the bounded second review selected and
    CPT Studio did not add had been traced, with Corti alone too. That gave 45378 an endoscopy-family rule in the
    reviewed report, and reference validation read "Done 1 code checked" with nothing to decide on.
  - An alternative's card lists no retrieval.
  - A service only a participant reads is worded with the documented-service reading's own located reading of the
    quoted passage, never routing's. Round 7's gate had dropped "declined", "could not be performed" and every other-GI
    family, and had named "the peg" for a quoted upper endoscopy. An act read as performed in the quote is named.
  - The participants-only blocker and panel never say "not the provider". The panel gives a refused or unread
    provider's own check first.
  - participants.summary's closing sentence is merge's own rule.
  - A highlight holding both kinds of passage for one code is titled as overlapping passages.
  Four findings were defects round 7's repairs introduced, so a narrow ninth refutation of this round's repair commit
  runs before the PR is made ready. 4.6, D3-D5, D14's owner question, the release-standard question and interpretation
  68 stay open.
- **2026-11-03 ~12:45Z (session cd048041): refutation round 9 repaired.** The narrow ninth refutation of round 8's repair
  commit filed 10 findings, 9 reproduced (three major); retrieval-3 was not, since no installed system can hold its
  input. I1 held. The repairs, each with a failing pin and a mutation proof (HARNESS.md 12.17):
  - Only a code a reviewer can decide (selected, or excluded and reinstatable) is traced, counted or listed on a card. A
    code excluded with no reinstatement had been counted "Done 1 code checked", and paired with a READY 45378 in a CMS
    endoscopy-family rule in the reviewed report.
  - An act is named beside a participant's quote only where its own mention lies inside the quote. An act whose clause
    only touched the quote's edge had been printed "as performed" beside an attempt that failed.
  - Every place of the quote is read. A PEG mention is named by its act label, and an act's service by its family's
    label.
  - The summary's first clause names a response CPT Studio used.
  - A highlight holding both kinds of passage for one code says so, never that they overlap.
  One assertion in an I1 proof file moved, declared: the superscript code excluded for scope is no longer traced, and
  its sha256 pins are unchanged. Because round 9 again found defects in the previous round's repairs, a narrow tenth
  refutation of this round's repair commit runs before the PR is made ready. 4.6, D3-D5, D14's owner question, the
  release-standard question and interpretation 68 stay open.
- **2026-11-03 ~14:00Z (session cd048041): refutation round 10 repaired.** The narrow tenth refutation of round 9's repair
  commit filed 10 findings, 9 reproduced. One is blocking and predates the harness, on the installed Corti-only path: a
  diagnostic base is not held again when a reviewer reinstates a therapeutic code of its family, so both can be approved
  into a reviewed report. It is recorded (HARNESS.md 12.18), left for its own branch, and reported to the owner with the
  pause question. I1 held. The repairs, each with a failing pin and a mutation proof:
  - Each quote of a participant's service is read alone.
  - No act is named beside a participant's quote. The fallback says only what makes the service missing, which is true
    by construction.
  - Each piece of a highlight split across paragraphs is titled by what it holds.
  - Two more title shapes are pinned.
  The cpt-studio job's time budget is raised to 45 minutes, since the suite outgrew 30. A narrow eleventh refutation of
  this round's repair commit runs before the PR is made ready. 4.6, D3-D5, D14's owner question, the release-standard
  question and interpretation 68 stay open.
- **2026-11-03 ~15:00Z (session cd048041): refutation round 11 repaired.** The narrow eleventh refutation of round 10's repair
  commit filed 6 findings. All 6 were reproduced, every one minor. I1 held. The repairs, each with a failing pin and a
  mutation proof:
  - Where no quote names a not-done reading, the reason also says what the reading reads as done in the quoted words, of
    another family, by that family's label. A quoted service is never left looking denied.
  - An instrument is never named by its family's kind.
  - Four page shapes are pinned. The page code was right.
  A narrow twelfth refutation of this round's repair commit runs before the PR is made ready. 4.6, D3-D5, D14's owner
  question, the release-standard question and interpretation 68 stay open.
- **2026-11-03 ~17:00Z (session cd048041): refutation round 12 repaired; the review ends.** The narrow twelfth refutation
  of round 11's repair commit, one lens, filed 4 findings. 2 were reproduced, both minor, and 2 were not: in those the
  clause truly states the reading's own reading. I1 held. The repairs, each with a failing pin and a mutation proof
  (HARNESS.md 12.20):
  - A quoted mention is named only with its own status, never the whole service's.
  - The clause's first-quote and first-place rules are pinned.
  The repair writes no new sentence; it only narrows round 11's clause. So no concrete finding justifies a thirteenth
  round. A further pre-existing false READY on the installed Corti-only path, an attached prior EGD report's title, is
  verified and recorded for the shared-reader repair. 4.6, D3-D5, D14's owner question, the release-standard question
  and interpretation 68 stay open.
- **2026-11-03 ~20:30Z (session cd048041): installed and walked live; functional completion established.**
  `41e03656df61` (#1459) is installed on cpt.quillmd.com, with Corti, Astra and Fable live (declaration in #1460; the
  image-stop decision in #1461).
  - **The install.** Every phase passed. The image phase met two declared stop conditions: pip ran, and two system
    packages moved to +deb12u1. The cause was the session's own builder prune of 2026-11-02. It was measured (the
    Python distributions are identical; the database driver bundles its own `libsasl2`), and decided and committed
    before the next phase.
  - **The access checks** on the installed release returned `gpt-6-astra` and `claude-fable-5-1` exactly, and Corti
    answered HTTP 200.
  - **The walk.** Three fresh synthetic documents (hw-01 PDF, hw-02 DOCX, hw-03 paste) went through the ordinary
    reviewer account. Each reached its reviewed report: 45385, 43239 and 45331 approved; persisted after reload;
    reviewed TXT and CSV downloaded and checked (94, 94 and 92 checks, 0 failed). All three were within the declared
    bounds. 14 runs and 17 recorded vendor requests; the participants' estimate is US$0.78, and US$0.94 with the access
    checks.
  - **Fable's hw-03 reading** was not used: an extra `reason_detail` field breaks the reading schema, so it failed
    closed and its peer review was not sent. It is recorded as a participant outcome, not a hold and not a pipeline
    failure. No hold arose in the walk.
  - **Rows updated with live evidence:** 1.3, 3.2, 3.3, 3.4, 3.6, 4.1, 4.5, 6.1, 6.3 and 6.5 PASS. 2.1, 3.1, 3.5, 6.2,
    6.4 and 6.6 are IN PROGRESS, each naming what the walk did not exercise. D1 and D2 are RESOLVED (2026-11-02).
  - **Still open:** clinical validation and content-use permissions; the installed false READYs (HARNESS.md 12.14,
    12.20) and the base not held again (12.18), all unchanged (I1); pypdf 6.21.2's advisories (interpretation 68, not
    waived). 4.6, D3 to D5, D14's question and the release-standard question are open, none approved. Report:
    `docs/foundation/reports/2026-11-03-cpt-studio-harness-install.md`.

- **2026-11-05T09:20Z (session a12d8fb3): the harness repair begins (owner directive of 2026-11-05).** Stage 1 recorded
  (served `b0dc3446c64c`, configuration, the preservation counts, no concurrent writer) and stage 2 traced from the
  protected records of 88d9db32: Corti selected 43239, 45380 and 45381 in its first answer and again in the owner's
  second review of 07:43Z, which named the dilation, the decompression, the EMR and the snare; Astra and Fable each
  proposed all six documented services independently; D14 listed 43249, 45390 and 45385 as alternatives. The repair
  package's `repair.patch` applies cleanly to `main`; its focused modules pass on Linux (125 tests) and fail on unpatched
  `main` as reported (8 failures, 1 error). Re-assessed offline from the retained responses, with nothing sent, it
  clears 45381's false tattoo conflict and corrects 45380's anatomy, and it also holds 45380 on Corti's actual passage
  "...; it was not excised by snare." (a release that refuses on any overlapping not-done act): repaired in stage 3.
  D14's owner question is answered by the directive; 4.6, the release-standard question, D3-D5, interpretation 68 and
  decision (m) stay open.

- **2026-11-05T11:00Z (session a12d8fb3): stages 3, 4 and 6 built and measured offline.** The package's patch and the
  negation release committed; P-ADMIT, the two reconciliation rules, the refused-response rule, the customer list's
  dedup and the label bump in one commit. The integration's own findings, each repaired with a pin before commit:
  - the meaning-check battery reached a READY 45385 on "The polyp was left in place." under a polypectomy title, now
    refused admission by the evidence condition (P-ADMIT);
  - a refused Corti answer beside admitted codes read `complete_pending_review`;
  - competition judged on the whole-service item made an EGD's dilation and biopsy codes compete;
  - 88d9db32's 45381 claimed the EMR's lift injection as its act;
  - the customer page listed a suggested code again as not suggested;
  - the pipeline tests' engine stub never passed the participants.

  The full chunked suite on the working tree: 5,858 Django tests with 2 failures, both D14 pins of a member's
  conflicting date, re-pinned and passing; ops 524, verification 43, node 131, 63 and 135. H4 battery 0 movements and
  H1 replay EQUAL against main. Next: the refutation pass over the finished diff (item 8).

- **2026-11-05T12:40Z (session a12d8fb3): refutation round 1 done and repaired (`e88afe58b`).** Six read-only lenses
  over `3907cd592` reported sixteen findings, twelve blocking. Fifteen were reproduced on the committed head before
  repair; the minor sixteenth (fa-2) is declared behaviour and its claim is corrected. HARNESS.md "Refutation round 1
  (2026-11-05)" has the table.
  - **Why the repairs are in the readers.** Every false READY came through a reader both paths read: P-ADMIT let a
    participant fill a gap that D14 had left as a conservative alternative.
  - **The repairs' own over-reach,** found by the suites and narrowed before commit:
    - svc-42's tube replacement and R8 R5 Z1's restatement (targeted suites);
    - in the full suite, 17 failures, all mine: a checked form twin, a rectal EUS's biopsy label, an impression's two
      polyps, a form question's "?", engine @4's plan-label ruling, and a future service.
  - **Proof:** 28 mutants killed, restores verified by sha256.
  - **I1:** the H4 battery against main moved 6 codes, all declared, measured after the code, with 0 new violations; the
    prophylactic hemostatic clip rows move from READY to held (`cux-r5-binding.json` amendment); the H1 replay differs
    by the version labels alone.
  - 88d9db32, re-assessed offline from its retained responses, is unchanged and nothing was sent.
  - **Recorded, not repaired:** five limitations (ACCURACY-RESIDUALS.md, "Harness repair, refutation round 1").
  - **Next:** CI on the push, then a narrow second refutation round over the repairs.

- **2026-11-05T13:40Z (session a12d8fb3): refutation round 2 done and repaired (`90856a7d8`).** Three read-only lenses
  over the repairs at `5b1dc0466` (escape, over-reach, and cost with completeness and the customer surfaces) reported 27
  reproduced findings, 11 of them blocking. Round 1's phrase-level repairs had failed in both directions.
  - **Decision:** admission keeps the directive's literal standard: equivalent eligibility, READY exactly where Corti's
    own selection would be. Holding every admitted code for confirmation was rejected, because a held performed-status
    code offers a member no confirming answer.
  - **The two-cycle rule:**
    - dropped: `LESION_SITED`, `NOT_TO_BEFORE`, `NONE_AS_OBJECT`, `NO_YIELD_AFTER`, the act-list decompression additions
      and the other-role filter in `match`;
    - narrowed: the release, the resection technique, the lift injection, "hemostatic", the withheld listing,
      decompression, "marked", the distance and the size comparison;
    - fixed: the cost overrun (120 s to 1-5 s).
  - **Proof:** 29 mutants killed, restores verified.
  - **Measured:** full suite 5,891 Django OK; battery the same 6 declared movements; replay labels only; 88d9db32 offline
    unchanged, with nothing sent; the installer's state recomputation changes no encounter.
  - **Next:** CI on the push, and a narrow differential round 3 over round 2's rules: no new READY beyond main, and
    equivalent standards.

- **2026-11-05T14:25Z (session a12d8fb3): refutation round 3 done and repaired (`cb123f3a4`).** One read-only
  differential lens over round 2's rules at `40e183346` tested two claims, 306 inputs on both paths with and without a
  primary code, against main `8645fd54`.
  - **D2** (a participant's code READY only where Corti's own selection is) held in all 612 runs.
  - **D1** (nothing READY beyond main, apart from the package's own marking forms) failed in three families, each a
    releasing rule. Each is reverted toward main:
    - the stage-3 negation release is main's rule exactly;
    - decompression uses main's vocabulary, with the bare verb read only in a failure or attempt frame;
    - the package's coordinated "marked ... and not resected" is read at its exact shape only.
  - **Measured:** the lens's 651 rows re-run with 0 D1 and 0 D2 flags; 5 mutants killed, restores verified; full suite
    5,893 Django OK; battery the same 6 declared movements; replay labels only.
  - **88d9db32 offline,** nothing sent: five codes ready, including the three participant codes. Corti's own 45380 is
    held again beside the snare's denial. This is a recorded cost: the release offers no reviewer confirmation, so the
    member's path is an addendum or a rejection.
  - **The pass stops here.** Every remaining rule is main's, holds, or lists, apart from the repair package's own
    purpose rule and its coordinated form at its exact shape.
  - **CI:** CI and secrets-scan are green on `40e183346`. The cpt-studio job's tests pass and its audit is red on the
    seven pypdf advisories (interpretation 68).
  - **Next:** CI on this push, then the PR out of draft, the merge, and the install declaration.

- **2026-11-05 (session a12d8fb3): refutation rounds 4 to 7, and the install declared.**
  - Round 4 (the author's probe and two lenses), round 5 and round 6 attacked the repair package's two releasing
    readings and the newest rules.
  - Every round found blocking false READYs, each reproduced before repair. Under the two-cycle rule the package's
    coordinated-denial and purpose readings were dropped (round 6), and so was its bare "excised" (round 5).
  - Round 7 attacked the whole remaining diff. The withheld listing's kindless branch was dropped, and bundling now
    happens only at one certain lesion.
  - **Measured on `e6d451f03d86`:** 3,050 adversarial rows from seven rounds, 0 READY beyond main, 0 D2 flags. 88d9db32
    offline: five codes ready, including the three participant codes; 45381 held by the tattoo conflict, as on the live
    site; the decompression listed.
  - **The required "Fresh application tests" check:** ubuntu-latest moved to Ubuntu 26.04 and ffmpeg 8 mid-session, and
    the rebuild's audio tests failed there. PR #1474 pins that job to 24.04.
  - **Not delivered:** directive item 3's tattoo-versus-resection and future-localization readings.
  - **Next:** the install, the 88d9db32 reassessment and the fresh walk.

- **2026-11-05T19:35Z (session a12d8fb3): installed `e6d451f03d86`, 88d9db32 re-assessed, fresh walk run.**
  - **The install:** blue/green, with 305 availability samples all 200, no migration, no state recomputed and nothing
    sent. Every receipt matched the declaration.
  - **88d9db32:** five codes ready, including the three Corti omitted; 45381 held by the tattoo conflict; the
    decompression listed. Its prior assessment and decisions are kept.
  - **The walk:** h2a PASS; h2b and h2c fail on the routing reader's label (main-equal) and on h2b's peer reviews.
    - Fable answered all three documents and its readings were refused by the schema.
    - Downloads: 276/276.
    - Usage: Corti 0.143 credits; an estimated $1.70 (Astra $0.34, Fable $1.35) plus unestimated Astra runs; no
      confirmed figure.
  - Record: `docs/deploy-reports/20261105-cpt-studio-e6d451f0-install-and-walk3.md`.

- **2026-11-05T20:45Z (session a12d8fb3): the owner's second message received and recorded; stage 1 traced.**
  - **Recorded:** the message verbatim, with interpretation (a)-(k), in
    `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` and as a RULINGS.md row. The morning section's items 3, 4, 5
    and 10 are now partial: 4 and 5 are corrected from ticks, with their reasons, and the earlier entries are kept.
  - **Stage 1:** the owner's latest test is 39f0ac49 ("GI_Procedure_Note_05.pdf", 20:09Z). Its omitted code is 43247.
    - Astra and Fable both proposed it in their first readings; Corti never returned it.
    - It was refused at admission (the gap-filling P-ADMIT), because the documented-service reader has no act for
      "the bolus was removed".
    - Inline labels left both procedures "uncertain", and that held Corti's three codes. The owner's "Not documented"
      answers excluded them.
    - Not clinically justified. Record: `docs/cpt-harness/repair3-20261105/stage1-trace-39f0ac49.md`.
  - **Next:** item 2 (Fable's contract), then items 3 and 4, then item 5.

- **2026-11-05T22:30Z (session a12d8fb3): items 2 to 5 built and tested; the refutation pass is running.**
  - **Built**, as local commits on the repair line (`e55c33ea7` Fable's contract, `f32a18a2d` Stop and Resume,
    `1974c8cb1` admission and readers): P-ADMIT2; F-SECTIONS T and L, with an attached report's title kept as history;
    F-ACTS; F-TIME N, B, C, P, I and F with the fronted frame; F-NEG S; F-TIME R. The competing question offers no
    detail answer. Contracts: `cpt-studio/HARNESS.md`, "Harness repair 3".
  - **Measured:** `tests/test_h3_repairs.py` 22 OK (each claimed rule fails on the base); the affected modules 187 OK; the
    H4 battery against origin/main `406843018`: 2 movements, both declared releases toward the rows' truth, 0 new
    violations. A first battery run found one new false hold (R8 D10, an attached prior report's title); it is repaired
    and pinned.
  - **Found on the way, and repaired:** the served readers read "Prior to this procedure, ...", "At the referring
    facility, ...", "Per outside report, ...", "If ... was removed, ...", "It is unknown whether ...", "Ink never
    injected ...", "Tattoo ink is to be injected ..." and "..., but the polypectomy was unsuccessful" as acts done
    today, READY on Corti's path too.
  - **Running:** six refutation lenses in write-disabled sandboxes at `1974c8cb1` (the releasing rules; the holding
    rules' escapes; false holds; admission and competition; sections and acts; Stop and Resume), and the chunked full
    suite.
  - **Offline reassessment from retained responses** (`reassess_offline.sh` on a fresh restore of this evening's
    read-only dump; runs 124 to 124, sent 113 to 113, nothing sent), at `1974c8cb1`:
    - **39f0ac49:** 43239, 45380, 45385 READY, and **43247 READY** (origin participant, Astra and Fable), no unresolved
      item, no open question. The installed revision listed 43247 as an alternative and held the other three.
    - **88d9db32:** 45380, 45381, 43239, 43249, 45390, 45385 READY (45381's false tattoo conflict gone); the gastric
      decompression stays unresolved as unsupported (no code accounts for it; the rejected experiment is not restored).
  - **pypdf 6.21.2:** its seven advisories are denial-of-service only and are accounted for, not resolved
    (`docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md`); no readiness for wider uploads is claimed.
  - **Next:** reproduce every finding before repair, apply the two-cycle rule, then CI, the install declaration, the
    install, the reassessments and the fresh walk.

- **2026-11-06T00:20Z (session a12d8fb3): refutation round 1 repaired and pinned; the full suite's regressions repaired; cycle 2 running.**
  - **Round 1:** six lenses over the stage commit `1974c8cb1` reported 41 findings, and every one was reproduced before
    its repair. Every lens input and control is pinned in `cpt-studio/tests/test_h3_refutation_r1.py`: 214 engine cases
    on both paths, plus the database cases (competition, Stop and Resume). That module fails 185 subtests on the stage
    commit and passes on the repaired tree. Committed as `8b186df05` (local), with the record in `cpt-studio/HARNESS.md`,
    "Harness repair 3, refutation round 1".
  - **Residuals recorded, none a regression against the base:** L1-4's plain "tattoo was requested" (Corti's path),
    L2-1i, "the small ones not banded", L3-10's event times, and L5-2's pathology addendum (Corti's path). Also ⚠️
    **L4-4**: Corti's own-passage release is not open to a participant's code, and Corti's same code with another
    passage decides that code. This is a provider asymmetry the directive rules out, recorded as open; it is visible,
    never READY.
  - **The full suite after round 1:** 5,989 Django tests; ops, verification and the node suites all passed. It failed
    21 subtests: one was the freeze test's timing, and twenty were this repair's own regressions, now repaired.
    - F-TIME P read before a plan section dated the act, and "at the hospital" counted as another facility.
    - "per the patient's permission" counted as another source.
    - A numbered part of the same document ("PART 2 - PROCEDURE NOTE" with its own date line) read as an attached
      report. ⚠️ This was a **date-channel** change that neither the freeze corpus nor the 58 retained texts carried;
      the suite found it.
    - Three digest pins moved through the labels alone (I1 checked at `e6d451f03d86`'s labels).
  - **Measured on the repaired tree:**
    - the battery: 3 movements, all declared;
    - the replay: identical but for the labels;
    - the freeze: holds with 18 declared patterns;
    - the 58 retained texts' context facts: identical.
  - **Running:** the second refutation cycle (five lenses: the releasing rules; the holding rules in both directions;
    sections and the date; admission and competition; acts and Stop/Resume) in sealed sandboxes at `8b186df05`. Also
    the full suite again, this time recording every text it hands the date reader, for a base-against-head date and
    routing differential over all of them.
  - **The sandbox self-test's ARM 6 is stale:** it checks a Node package (`packages/auth`) that `0354cbb9f` retired. In
    its place each sandbox was proved, by a Python positive control, to import its own tree's code. Every write-safety
    arm passed.

- **2026-11-06T01:45Z: harness repair 3, refutation cycle 2 applied and the full suite green; cycle 3 running.**
  - **Cycle 2:** five lenses at `8b186df05` reported 43 findings. Each input was measured on this tree, the round-1
    tree, the stage commit and the base before anything was decided.
  - **Dropped under the two-cycle rule:** F-TIME R, F-SECTIONS T and L, and F-ACTS' first vocabulary. ⚠️ Directive
    item 4's "completed marking versus future localization" and the Word walk's title routing are therefore
    **undelivered**: their inputs read as the base reads them.
  - **Rebuilt, smaller:** F-ACTS predicate-bound; the provider-neutral admission; competition by act identity.
  - **Repaired at the cause:** the holding rules B, F, P, C and N.
  - **The full suite after cycle 2 found four real defects, repaired:**
    - a participant's code for a failed act was held, not listed (the meaning check's D14);
    - the fronted frame dated a done act by its purpose's "future" (svc-21, 88d9db32);
    - a doubted dilation's code claimed the done one (L4-2);
    - the chain-mode edge is now mutation-proved.
  - **Then green on the repaired tree:** 6,001 Django tests, 524 ops tests, 43 verification tests and the three node
    suites.
  - **Gates against `406843018`:** the battery has 3 declared movements and 0 new violations; the replay is identical
    but for two labels; the freeze holds.
  - **Pins:** `tests/test_h3_refutation_c2.py` pins all 156 cycle-2 inputs through the pipeline's own date, and none
    is READY on either path where the base is not.
  - **The retained cases, predicted offline** (a throwaway copy, nothing written or sent):
    - 88d9db32: six codes READY, three of them Astra's and Fable's only (43249, 45390, 45385), each an act done today;
    - 39f0ac49: four codes held alike, 43247 among them, now reaching review but not READY.
  - **Recorded open, each the base's own:**
    - "The polyp was left in place." under a procedure line naming the polypectomy reads READY on Corti's path;
    - two dilations of one ring with two instruments compete;
    - the asymmetry for acts stated not done (Corti's selection held, a participant's code listed).
  - **Committed as `b32222c8f` (local).** Refutation cycle 3 is running now: four lenses in sealed sandboxes at that
    commit, over the rebuilt and repaired parts only.
  - Items 3, 4 and 5 stay PARTIAL.

- **2026-11-06T03:05Z: refutation cycles 3 and 4 applied; the release policy decided every finding.**
  - **The findings:** cycle 3 (four lenses at `b32222c8f`) reported 25 and cycle 4 (three lenses at `7e3924a3c`, the
    last) reported 18. Each was reproduced on this tree before its repair.
  - **The policy** (HARNESS.md, cycle 3):
    - an input READY where the base is not, or two approvable codes for one act, is always repaired, and a releasing
      rule refuted twice is dropped;
    - a false hold this diff introduced is narrowed toward the base;
    - the base's own false READYs are recorded.
  - **Dropped:** F-ACTS, refuted in cycles 3 and 4. ⚠️ **39f0ac49's 43247 stays listed**, as on the installed
    release: "the bolus was removed" is no documented act without a rule that released false removals in two cycles.
  - **Narrowed:** the provider-neutral admission, to an act stated done inside a doubted service.
  - **Competition** errs toward competing.
  - **Returned to their cycle-2 forms:** four holding narrowings that opened false READYs. The false holds they had
    fixed are recorded instead.
  - **Over every cycle's inputs on this tree (539):** one input is READY where the base is not (L3-9, judged correct),
    no act has two READY codes, and every admission row leaves Corti's codes and the completeness as alone.
  - **Pins:** `tests/test_h3_refutation_c3.py` and `tests/test_h3_refutation_c4.py` with their fixtures; the round-1
    tables and the cycle-2 and cycle-3 fixtures are regenerated.
  - **The retained cases, predicted offline:** 88d9db32 has six codes READY (three of them Astra's and Fable's only),
    and 39f0ac49 has three held and 43247 listed.
  - Items 3, 4 and 5 stay PARTIAL.

- **2026-11-06T04:40Z: harness repair 3 merged, and its install declared before the act.**
  - **Merged:** PR #1477 is merged as `fd8040d71e44` (branch head `84707acd5`; byte-identical `cpt-studio/` tree
    `0eac8315dd89`).
  - **Citation on the merge commit:**
    - CI run 42159987582 and secrets-scan run 42159987651 pass;
    - cpt-studio run 42159987583 passes every test (6,011 Django, 524 ops, 43 verification), with its audit red on the
      accounted-for pypdf advisories.
  - **Declaration:** `docs/foundation/mutations/20261106-cpt-studio-harness-repair3-install.md`, committed before any
    phase runs.
  - **Image precheck:** dependency layers CACHED; dpkg list identical to the live image's.
  - **Offline prediction** (read-only dump 03:08:47Z, nothing sent):
    - 88d9db32 goes needs_clarification to ready_for_review, with six codes READY (three Astra's and Fable's only);
    - 39f0ac49 holds Corti's three codes by six questions and lists 43247.
  - **Live baseline:** re-read at 04:37:46Z, unchanged since the dump.
  - Item 8 is in progress; the install follows.

- **2026-11-06T05:40Z: installed `fd8040d71e44`, the retained cases re-assessed, the fresh walk run. The GI release is
  not complete.**
  - **Installed** through the ruled-act door, exactly as declared: 299 availability samples, all 200; nothing sent;
    only the declared rows moved.
  - **The retained cases** read as predicted:
    - 88d9db32 is ready_for_review, with six codes READY, three of them only Astra's and Fable's;
    - 39f0ac49 holds Corti's three codes by six questions and lists 43247.
  - **The fresh walk:**
    - h3a (PDF) fails 2 of 112 hard checks;
    - h3b (Word, with a Stop and Resume) fails 1 of 140;
    - all three failures are the routing reader, which this release left unchanged (main-equal);
    - the downloads pass 166 of 166 checks, and the customer scan 27 of 27 with 0 hits.
  - **Done:**
    - item 2: Fable's harness-4 readings were accepted on both documents;
    - item 5: Stop and Resume proved live without a duplicate send;
    - item 6: the complete harness ran on h3a (participation only);
    - item 9: the report.
  - ⚠️ **Not met:** on h3a, as on 39f0ac49, Astra's and Fable's explicit, exactly quoted 43247 for the food-bolus
    removal is listed as not done and cannot be approved. The owner's central requirement fails for this act class
    while F-ACTS stays dropped.
  - Items 3, 4, 7 and 8 stay PARTIAL.

- **2026-11-06T06:55Z: the owner's completion directive received and recorded; the contract put into the harness
  before implementation.**
  - The directive is recorded verbatim, with interpretation (a)-(m), in the rulings file, plus its index row.
  - The contract is in `cpt-studio/HARNESS.md`, criteria C1 to C9.
  - The state is in "Completion repair, 2026-11-06": checkpoint, defects U1 to U12, limitations L1 and L2, and items 1
    to 9.
  - Preflight GO: `docs/preflight-reports/preflight-20261106T064528Z.md` (shared tree, untracked by convention).
  - Stage 1 is in progress.
- **2026-11-06T08:30Z Completion repair, stage 1 PASS (VERIFIED OFFLINE).** The four retained cases recompute identical
  to their stored assessments on the installed code. Five read-only lenses traced every core defect to FILE:LINE, and
  the session reproduced each headline claim before recording it (`docs/cpt-harness/completion-20261106/stage1-trace.md`).
  The counterexamples are pinned in `tests/fixtures/gi4/completion/corpus.json`: 611 entries, with the guard that no
  entry becomes a false READY that was not one on `fd8040d71e44`. New, by measuring:
  - U3 masks U4, so they are one repair;
  - F1, a kept rule's false READYs;
  - U11's answer reuse;
  - U13's adjacent misreadings;
  - two owner coding questions (Q1, Q2).
  Next: the repair's design and its bounded implementation.
- **2026-11-06T08:50Z Completion repair, stages 2 to 5 started.**
  - Preflight GO: `docs/preflight-reports/preflight-20261106T082530Z.md`.
  - Five builders run in isolated worktrees from `b452c6c4`, each with a written brief
    (`/home/claude/cpt-studio-completion-20261106/build/briefs/`): `wip/cptc-r1-structure`, `wip/cptc-r2-outcome`,
    `wip/cptc-a-acts`, `wip/cptc-q-admission` and `wip/cptc-q2-answers`.
  - Every brief carries the stage-1 causes, the refuted attempts' counterexamples, and the same measures: the corpus
    ledger with its no-new-false-READY invariant, the focused suites, the full suite, the retained-case recompute, and
    the freeze where layout or routing moves.
  - No version label moves on a builder branch. The owner integrates and declares once.
- **Correction to the two entries above (appended, not rewritten).** Their stamps, 08:30Z and 08:50Z, were estimated,
  not read from the clock. The clock and the records give:
  - stage 1's commit `b452c6c4` at 08:18:43Z;
  - the build workflow's script written at 08:35:59Z;
  - this checkpoint's commit at 08:36:20Z;
  - the clock read 08:39:35Z when the error was found.
  The checkpoint table now carries the read times. Later entries use the clock.
- **2026-11-06T08:41Z Completion repair: the fresh acceptance set is written and sealed, before any code read it and
  before the repair's code existed.**
  - Sealed (mode 0400, directory 0500) in `/home/claude/cpt-studio-completion-20261106/acceptance/sealed/`, with these
    sha256 prefixes:
    - c1a-procedure-report.txt `976be07404d0fe93` (PDF): labelled EGD and colonoscopy paragraphs after an Indications
      line, the bolus's antecedent, a completed marking for a later resection, an outside history sentence;
    - c1b-colonoscopy.txt `477dbbd5679ac420` (Word): a title with an aside, a failed hot snare attempt whose polyp was
      left in place, a repeat colonoscopy in the Plan, an outside EGD in the history, Stop and Resume;
    - c1c-flexible-sigmoidoscopy.txt `2e59f3a1c00fa967` (PDF): a labelled colonoscopy paragraph of another occasion
      (negative), and a genuinely missing extent, answered "Not documented" and recomputed, then confirmed by a
      physician's addendum on a new revision;
    - expectations-c1.json `f131fd2a0bce250a`.
  - The expectations are the session's provisional reading, supported per code by the stored CMS references
    (PFS RVU26D, MUE 2026-Q4). They are not a coder's adjudication. NCCI is not connected.
  - The builders' briefs do not name the set, and no code reads it before the walk.
- **2026-11-06T14:50:46Z Completion repair: the five builders integrated, measured, and the full suite green on `89fe6328f38d`.**
  - Builders (workflow `wf_33ae45a0-361`, finished 2026-11-06T12:25Z): R1 structure, R2 outcome, A acts, Q1 admission,
    Q2 answers; merged serially into `fix/cpt-studio-completion-20261106` (R1 `7d42e2cd`, R2 `3815eaa6`, A `22e79e5c`,
    Q1 `cc38fb1d`, Q2 `2a46a267`), each merge re-measured before the next.
  - The integration's own rules, each committed with its measurement: the dilation technique (43249 READY on a Savary
    dilation was a base false READY made reachable on the walk's h2c document), one evaluation in competition, the
    another-act hold removed, one subject reading, a dated history in the indication, another act's doubt (narrowed to
    a distinct lesion record after the first full suite measured 31 genuine holds released), the retrieval trace for
    admitted codes, the rollback hazard's wording, the labels (gi-routing@9, gi-services@6, cpt-studio-validation@9,
    gi-catalogue@2).
  - The first full suite on the integrated tree (`3bb8b723`) failed 41 and errored 4: attributed rule by rule in memory
    and repaired (`f4b34778`, `89fe6328`); the second (6,229 Django tests OK in three chunks, ops 524 OK, verification 43 OK, the node suites 131, 65 and 135 passing, check and makemigrations clean (second run, 2026-11-06T14:33:40Z to 14:50:18Z)).
  - An independent acceptance set c2 was written by an agent blind to the repair and sealed at 2026-11-06T14:11:22Z
    (mode 0400, directory 0500) in `/home/claude/cpt-studio-completion-20261106/acceptance/sealed-c2/`, sha256
    prefixes: c2a.txt `358e42f28f26a4e1` (PDF), c2b.txt `811efefbb15f9518` (PDF), c2c.txt `2c884ef1a2d1462b` (Word),
    expectations-c2.json `7174de3cdfb579c5`. Its author returned only these hashes; no one has read it. The session
    wrote set c1 itself and knows its content, so c2 is the independent acceptance evidence and c1 is walked beside it.
  - No provider request has been sent in this repair.
- **2026-11-06T16:15Z Completion repair: refutation cycle 1 over the integrated diff, and its repairs.**
  - Workflow `wf_5ea89702-382`: seven lenses in write-disabled sandboxes at `179fdff9`; six returned 44 findings
    (structure 8, admission 8, outcome 8, acts 8, answers 7, consistency 5; the cost lens had not returned). The owner
    session reproduced every finding on the head and the base (`verify/refute1/`): 17 NEW false READYs among them.
  - Repaired fail-closed in `34b8d0c9e` and `95392c99f` (HARNESS.md "Refutation of the integrated diff, cycle 1"; pinned
    in `tests/test_completion_refutation_c1.py`, a mutant of one repair failing its pin). The first acts repair moved
    seven purpose-marking corpus entries to FALSE HOLD; routing's own purpose rule was kept and narrowed instead.
  - The install prediction (a read-only dump restored on the test server, the installer's own one-shots, nothing sent)
    measured the stored-answer rule of the repair turning three reviewed encounters back to needing details at the state
    recompute alone; the rule now binds an earlier-form answer by its own question's words, and on the cycle-1 commit the
    state recompute after migration 0013 changes no encounter and the rollback read changes none.
  - Measured: corpus invariant 0 new false READYs; freeze gate holds; H4 battery 10 declared movements unchanged; H1
    replay the labels alone; the four retained cases as required; the walk tool's new hard checks (expected codes, the
    member's answer, a conflict question) and the manifest builders for c1 and the blind c2 (the latter written from the
    schema the c2 author was given; c2 still unread).
  - No provider request has been sent in this repair.
- **2026-11-06T20:10Z Completion repair: refutation cycle 2, the two-cycle rule, and the change of approach.**
  - Workflow `wf_3e6e5e6d-2f1`: five lenses over cycle 1's repairs returned 37 findings (structure 8, outcome 8, acts 8,
    admission 7, answers 6), 20 of them false READYs; every structure, acts and admission finding reproduced exactly on
    the three trees (`verify/refute3/`). The cycle-1 word readers had leaked and over-held at once.
  - The owner's two-cycle rule applied: the refuted patches abandoned, the approach changed per mechanism, the requirement
    kept (HARNESS.md "Refutation of the integrated diff, cycle 2"). Measured first: every structure false READY of both
    cycles, and the instrument rule's O1/O3/O4, has a twin the installed release reads READY too (layout parity);
    ablations showed which releases the corpus and the retained cases need.
  - Five builders (`wf_f7121d1f-985`: parity, outcome, acts, admission, answers), each in its own worktree; the owner
    session integrated them and added: the another-act release abandoned; the closed observation form for "not
    performed"; units on the documented match; readiness held on a withdrawn answer; the removed-only form beside a
    listing; two specific techniques as two instances; the listing rule judging only removable lesions (found by the
    replay gate: h2-10).
  - Measured on `ae3b19b8`: corpus re-pinned beside its declaration (8 moved; FALSE READY 39 to 35; 0 new false READY);
    parity 65 pairs, one recorded exception (corpus 137's 43247, the heading form's own false hold); the retained cases as
    required; freeze gate holds; battery 10 declared movements (0 undeclared); replay the labels alone. The first full
    suite on the integrated head (`7a4c4c41`) failed 49 subtests, each classified and re-pinned (`d4f4ecff`), none a
    regression.
  - No provider request has been sent in this repair.
- **2026-11-06T21:15Z Refutation cycle 3 answered (offline only):**
  - Six lenses at `844fe54c` (`wf_bab4d28d-c76`, about 35 minutes) returned 32 findings: parity 7, closed forms 7,
    outcome 4, admission 5, answers 4, cost 5. Every engine-level input was reproduced on this head, the installed base
    and the cycle-1 head before any change; the answers lens's scripts were re-run.
  - Each release was disabled in memory and the corpus read, to see which requirement rests on which release. The
    releases nothing required rests on were abandoned to the base reading; the required ones were closed whole; routing
    now gives a failure to a sub-act only where the services reader reads that act failed; a released label is read as
    its heading twin's name. Commit `acadc296`; HARNESS.md "Refutation of the integrated diff, cycle 3".
  - The full suite at `844fe54c` had one failure, harness 3's judged-release list still naming X2 and X3 after their
    re-pin (fixed in `a5e9b5f5`).
  - 844fe54c was pushed (origin confirmed); CI on it: the `cpt-studio` workflow's tests pass and its dependency audit
    fails on pypdf 6.21.2, as on main since #1449 (L1).
  - Install predictions on `844fe54c` over a fresh read-only dump: the retained cases 4/4/2/6 READY, nothing sent,
    RECOMPUTE_STATES unchanged.
- 2026-11-06 23:45Z - refutation cycle 4 over cycle 3's repair (`52a5f774`): five lenses (structure 4, closed 8, outcome 5,
  answers 3, cost 3 findings), every one reproduced on three trees before any change (`verify/refute5/`).
  - Repair under the two-cycle rule: the services reader's failure words are the installed three; a sub-act's failure only
    in the closed attempt form (bounded: 350 KB in 1.5 s); the observed-only removal exclusion abandoned; the instrument
    rule's named section read at the name's place; the labelled binding stops at a scope sentence outside its tract and
    its own sentence reads as the twin's; a consumed failure stays the family's mention (performed by its section); the
    engine reads only fingerprinted answers to decision-independent questions, other codes' fingerprints kept.
  - Differential scan (1,862 inputs from every lens of cycles 1-4, three trees): no open release; every READY added over
    52a5f774 is READY on the base. Parity residuals recorded (purpose, reach, bolus; ACCURACY-RESIDUALS cycle 4).
  - Corpus re-pinned beside `completion-refutation-c4-corpus.json` (5 moved, ADM C3-2-1, to FALSE HOLD); retained 4/4/2/6
    READY byte-identical to 52a5f774; freeze holds, battery 6 declared movements, replay labels alone; the completion and
    h3 refutation suites (401 tests) pass.
- **2026-11-07T00:34Z Completion repair: the differential round over cycle 4's repair, answered (offline only).**
  - Workflow `wf_f8f66730-784`: three lenses at `e273dc5a` (routing 3, structure 6, answers 1 findings). Each was asked
    only whether the new head is worse than the installed base or the previous head in a must-fix class. Every finding
    was reproduced on the three trees first.
  - Repair `443740630`, every change toward the installed reading or its twin:
    - the instrument rule's name read in segments, and no instrument-named narrative under a named procedure, findings
      or technique heading;
    - the labelled binding cut at the first later scope sentence, with a combined report part past it;
    - the closed form read in fixed steps (200 KB in 2.7 s; it was 64 s) and ended only at its full stop or "; the polyp
      was left in place.";
    - the consumed failure gated by I8 and I12;
    - base_included and separate_em answers bound by key.
  - The final scan (2,568 lens inputs of cycles 1-5, three trees): 234 READYs the base does not read, each bounded by a
    twin the base reads READY or a release cycle 3 measured; none is open. 22 needed their twins measured by hand (the
    routing lens's U3 and cancellation groups) and are now pinned with them (`completion-c5-cases.json`, 309 inputs).
    The I8 mutation fails 48 pins; 6 caught it before.
  - The corpus moves nothing (FALSE READY 35, 0 new; FALSE HOLD 59); the retained cases read 4/4/2/6 READY,
    byte-identical; freeze holds, the battery has 6 declared movements, and the replay differs by the labels alone; the
    install predictions are identical to cycles 3 and 4; the full suite green on `443740630` (6,390 Django tests, ops 524, verification 43, node 135/65/135; check and makemigrations clean).
  - No provider request has been sent in this repair.
- **2026-11-07T02:45Z Completion repair: installed as `6f306af1b030` and walked; the acceptance failed.**
  - PR #1480 merged as `6f306af1`; its declaration (#1481, `a7d2b517`) committed at 01:49:43Z before the act. Every phase
    ran through the ruled-mutation door and matched its declaration: image fully cached (packages identical to the
    live image), 301/301 availability samples 200, migration 0013 only, states_recomputed unchanged, verify clean (the
    vhost differs only in its proxy_pass port), the reassess making exactly the declared rows, e888f9ce's two
    invalidations included. Nothing was sent.
  - The walk (Corti, Astra, Fable, concurrency one): blind c2 1 of 3, c1 1 of 3; no false READY anywhere. Findings
    1-7 are in `docs/deploy-reports/20261107-cpt-studio-6f306af1-install-and-walk.md`, each cause read from the live
    records and reproduced offline; findings 1-4 read the same or worse on the installed base (not regressions).
  - Usage: c2 15 runs (+0.145872 Corti credits), c1 19 runs (+0.129748); no unknown outcome left.
- **2026-11-07T06:30Z The walk round: repaired, refuted three times, ready for its PR.**
  - Branch `fix/cpt-studio-walk-round-20261107` from `a7d2b517`: findings 1 (the labelled release: P1, P2 installed plus
    consent/time-out and two preparation statements, P3, N1), 2 (a Savary dilation bound by its upper-tract device),
    4 (a bolus "brought out through the mouth" as the bolus phrase's own removal), 5 (another polyp's closed-form
    failure set aside only beside the code's own cited act on a lesion told apart), 6 (the walk's list check) and 7 (the
    addendum response) repaired in the shared readers and the engine; finding 3 OPEN (U14).
  - The first form of finding 5 consumed the failure in routing; the full suite's 66 pinned failures showed it reopened
    the abandoned another-act release, and the approach changed. Refutation round 1 (four lenses, 14 findings) closed
    every open rule to the installed one plus what the walk needs; round 2 (two lenses, 8 findings) refuted three
    mechanisms a second time, and the owner's two-cycle rule was applied to each (patch abandoned, approach changed,
    requirement kept - finding 3 left open rather than shipped a third time); round 3 attacks the changed approaches.
  - Measured on `f8f72354`: the lenses' 2,821 inputs, re-run with their own probes, lose no READY the installed release
    reads and drop no incompleteness flag; the 2,763-input scan differs from installed by one READY the base reads; the
    corpus moves nothing (FALSE READY 35, 0 new); the walk documents offline: c2a 43248, c2b 43239 and 43247, c1b 45385
    READY; full suite green (6,416 Django tests, ops 524, verification 43, node 135/65/135); freeze holds, the battery
    has 6 declared movements, the replay differs by its labels alone; the install predictions (on `bf5a815d`) match the
    installed reading, nothing sent.
- **2026-11-07T07:45Z The walk round, round 4: the two narrowed rules refuted a second time and dropped.**
  - Refutation round 3 (one lens, `f8f72354`) found 4 defects in the two changed approaches (their first refutation),
    repaired in place (`cb3d7bfb`). Round 4 (one lens, `cb3d7bfb`, about 330 probes) found 6 (4 HIGH), each reproduced
    on the three trees: a guide wire's brand name read as a dilation where the stricture was not dilated, a generic
    "is usually performed" read done, and an 81.8 s assessment on an admitted input (device binding); "by Dr. <another
    physician>", "taken out ... by the emergency physician" and a bolus that fell back read 43247 READY (route-bound
    removal). Under the two-cycle rule both patches were abandoned (`32003524`): services.py and reconcile.py are the
    installed modules again (gi-services@6); findings 2 and 4 stay OPEN (U15, U16) beside finding 3 (U14).
  - Measured on `32003524`: the four rounds' inputs (1,675, 1,146 and 635) lose no installed READY and drop no
    incompleteness flag, and their new READYs are a strict subset of `cb3d7bfb`'s (the remainder: exactly the dropped
    rules' readings); the 2,763-input scan differs from installed by one READY the base reads; the corpus moves nothing;
    offline, c1b 45385 is READY and c1a and c2 read as installed; freeze holds, the battery has 6 declared movements, the
    replay differs by its labels alone.
- **2026-11-07T10:18Z The walk round installed as `73dcf8b4b40a`.** Declaration committed `545afba7` 08:49:25Z, landed by
  #1484 (`9842ed9c`); phases 10:12-10:18Z through the ruled-mutation door; every declared row matched (no migration,
  nothing sent, availability 300/300, the four retained encounters as predicted, co-tenants unchanged).
- **2026-11-07T10:20-10:35Z The walks.** Blind c3: 0 of 3, holds only - U18 (the release's paragraph gates), U19 (a
  reach stated by findings), U20 (numbered PROCEDURE headings under HISTORY); traced by an analysis workflow (analyst per
  document, skeptic per claim, all surviving) and verified with minimal pairs; 6f306af1 and the base read the same.
  Corti, Astra and Fable proposed the expected codes on all three documents. c1: 1 of 3 - c1b's Stop not exercisable on
  an identical re-upload (retained results reused, 18 s), c1c's addendum a walk-tool race; findings 5, 6 and 7 verified
  live. Usage: c3 15 runs (Corti 0.186388 credits; Astra 51,002/8,817 and Fable 166,232/19,450 tokens); c1 11 of 15
  runs reused, 4 peer reviews sent. The blind set c4 was sealed at 10:40Z (unread).
- **2026-11-07T15:15Z Resumed by session 30a58364 (owner and integrator).** Session a12d8fb3 ended at ~11:59Z with its hold
  taxonomy half done (5 of 6 analysts; the a3 analyst and the clustering lost); nothing else was running, and PR #1485 (the
  walk record) had merged as `b285e5f0`. Preflight GO. The taxonomy was finished (a3, a clustering into 15 repair clusters,
  a completeness critic).
- **2026-11-07 The recall round's method.** A development corpus (24 synthetic reports by six blind authors, one style each;
  installed 36 of 45 expected codes held, 3 careless false READYs) and a held-out corpus (24 more, six new styles, read by no
  designer; installed 25 of 44 held, 17 of them in the 10 documents whose date of service the reader does not read). A judge
  (the corpus, the 2,568-input differential scan, the corpus pins, the freeze, battery and replay gates, 734 pinned reader
  tests) reproduced every installed figure on an unmodified copy before judging any candidate.
- **2026-11-07/08 Eight designs, each refuted in two cycles** (two fresh lenses per cycle; a mechanism refuted twice
  dropped): numbered headings inside the shared layout (a date sent, releases beyond the base's twin) DROPPED; a competing
  shared heading grammar DROPPED; template field scope, instrument shorthand and attribution, and the act vocabulary
  ABANDONED (one corpus hold each, every sub-rule refuted); the hold-only false-READY rules DROPPED (a length read as a
  diameter, competitions consumed); two labelled-release variants DROPPED (word-list leaks, quadratic costs); a same-length
  reading twin for numbered headings DROPPED (the same regression in both cycles: parts the installed reading already read
  rewritten, correct READYs lost). KEPT: the findings-stated reach (U19), its second-cycle findings all bounded by parity, its
  cost bounded - development 36 -> 31 held, the held-out corpus unchanged, the scan and pins unmoved, the freeze holding.
- **2026-11-07T21:00Z Owner decision (asked with the held-out evidence): the date reader may read more unambiguous date
  forms** - a day-first date with a month name and a four-digit year, a weekday before a readable date, "Date of
  Operation:" and "Exam date:"; never a two-digit year or "11-09-2026". Recorded in RULINGS.md and the rulings archive before
  any dependent code (`ab786b3b0`). The first design read the new labels anywhere (a prior surgery's, an imaging study's and a
  recall date each sent) and was refuted; the repair reads them in the document's head only; interpretation (b') appended
  (`c3eb64c55`).
- **Walk tooling for c4, before c4 was read:** the withdrawal wait (`cd5212b9f`); the c4 builder carries Stop and Resume on a
  fresh document and gives each code a family question holds its own details entry.
- **2026-11-08T02:00-03:30Z The integrated diff, proved and refuted.** The full CI-like suite on `000fb24f6` passed (6,483
  Django tests, ops 524, verification 43, node 136/65/135); PR #1486 opened as a draft and its CI passed on `eee099ad7`
  (the cpt-studio job's tests all green, red only on pypdf 6.21.2's seven accounted advisories, L1). The mandatory refutation
  pass over the finished diff (interaction, regression, parity audit) found one defect of the integration: gi-context@4 had
  been kept current on a false premise; it is retired and pinned. The rest is bounded by parity or hold-side and recorded.
- **2026-11-08T03:51-05:00Z The retirement refuted before merge, and reverted.** PR CI on `7b4fb3d53` passed (6,485
  Django tests, ops 524, verification 43, node 136; red only on L1). The final pass had not seen the retirement, so a
  refutation pass ran over it before merge (two lenses: stage flows, and a restored live copy through install, member
  actions and rollback).
  - It found two HIGH send-door gaps the retirement does not close (pre-existing for @1 to @3) and five MEDIUM
    regressions it causes on live encounters.
  - The class it addressed is absent from the live data: none of 31 contexts reads differently under @5, and both controls
    are detected.
  - gi-context@4 stays current. The class is bounded by that measurement (repeated at each install, a stop condition)
    and by structure.
  - New open defects: U22 and U23 (pre-existing on the installed release).
- **2026-11-08 Merged as `aeae34bebbe5` (PR #1486, merge commit `aeae34bebbe57d907ac7870e2456904a6515a2a0`); the declaration.** CI on the PR head
  `0b8926213` and on the merge commit as cited in `docs/foundation/mutations/20261108-cpt-studio-recall-round-install.md`. The declaration names the install (preflight, image,
  app, verify, reassess), its predictions and baseline, and the gi-context@4 comparison as a stop condition.
- **2026-11-08T06:53-07:16Z Installed and walked.** The install of `aeae34bebbe5` ran through the ruled-act door from
  `015c3ff7`.
  - Every declared row matched: the gi-context@4 comparison on the pre-app dump 0 of 31, no migration, nothing sent,
    301 of 301 availability samples 200, states unchanged, the four reassessments as predicted.
  - The blind c4 walk failed 0 of 3, on holds only, each on a recorded open finding: U18 (c4a), U16 (c4b), U14 (c4c).
  - c1c failed on the walk tool's own wait, while the product behaved correctly.
  - Record: `docs/deploy-reports/20261108-cpt-studio-aeae34be-install-and-walk.md`.
- **2026-11-08 The structure round (integration branch `fix/cpt-studio-structure-round-20261108`).** The c4 walk's three
  holds were repaired against twin parity: the installed release's own reading of the same document in a form it already
  reads.
  - U14: the direct-reach twin (u14a3).
  - U16: the full twin's corroborated removal (u16c3).
  - U18: the computed heading twin (u18d), with the guard's span bound (u18d2).
  - Each was refuted in two cycles by fresh lenses, and each kept form is narrowing-only. The judge equals the installed
    figures in every row.
  - Offline, c4b and c4c read every expected code READY. c4a reads 45385 READY, and its 43239, 43248 and 45381 stay held as
    its heading twin holds them.
  - Four installed false READYs were found (U24-U27). U24's two hold forms were integrated and then refuted, so U24 is
    withdrawn. The lesson is recorded in HARNESS.md "The structure round": a hold that lowers a reading or a match state is
    read by the resolve order, the competition and the second review's admission. U25-U27 are open, and U28 is a recorded
    installed blind spot.
  - Labels: gi-routing@12, gi-services@7.

