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
| [ ] | 3. Shared interpretation repaired: tattoo versus resection negation, future localization versus future performance, comparison anatomy, lesion ownership; genuine contradictions, failed, historical, planned and other-provider services stay protected; nothing hardcoded | IMPLEMENTED (offline, not installed); refutation round 1 (six lenses over `3907cd592`: 16 findings, 12 blocking; 15 reproduced, each repaired in the shared readers; HARNESS.md "Refutation round 1 (2026-11-05)"); rounds 2 and 3 over the repairs (HARNESS.md "Refutation round 2" and "Refutation round 3"): the rules that did not converge dropped under the two-cycle rule, and round 3's three releasing families reverted toward main | `70f18d1bb`, `278aa4d2b`, `e88afe58b`, `90856a7d8`, `cb123f3a4` | the patch verified (rulings interpretation (f)); tests/test_advanced_gi_binding.py, tests/test_h2_negation_scope.py; round 1's repairs pinned on both paths in tests/test_h2_refutation_r1.py and tests/test_h2_marking_tense.py (time-1: a future marking; neg-1..3: "nothing", the zero numeral, "not to", "none of", "yielded no", a tattoo named as a place, "marked" only as instrument; own-1..3: a distance landmark, a comparison aside, a sized anaphor, another role's entry; fa-1: a procedure line over a body that says not done, failed or planned); 28 mutants killed, restores verified by sha256; H4 battery against main 6 declared movements, 0 undeclared, 0 new violations (`tests/fixtures/gi4/declarations/h2-repair-r1.json`); H1 replay differs by the version labels alone; 88d9db32 offline unchanged through round 2; round 3 restored main's negation release, so 88d9db32's 45380 is held again (recorded: ACCURACY-RESIDUALS.md "Harness repair, refutation round 3") | installed behaviour (item 9) |
| [ ] | 4. D14's blanket prohibition replaced: an explicit Astra or Fable proposal enters human review only after the full source-validation path passes, with equivalent standards whatever its origin; no promotion by quotes, confidence or agreement; raw lists never promoted; no model approves; true origin kept in protected diagnostics; recorded in the contract | IMPLEMENTED (offline, not installed); refutation round 1 (six lenses over `3907cd592`: 16 findings, 12 blocking; 15 reproduced, each repaired in the shared readers; HARNESS.md "Refutation round 1 (2026-11-05)"): every false READY it found came through a reader both paths read, repaired there; codes compete only for one act their passages show (multi-4) | `3907cd592`, `e88afe58b` | contract and as-built record: `cpt-studio/HARNESS.md`, "GI core and harness repair (2026-11-05)"; tests/test_h2_participant_admission.py (16), tests/test_h2_customer_admission.py (the real engine through the pipeline; every customer surface scanned); the meaning-check battery: every input a not-admitted alternative with Corti's proposals and the reconciliation unchanged; 88d9db32 offline at `cb123f3a4`: 43249, 45390, 45385 admitted and ready beside Corti's 45381 and 43239; Corti's own 45380 held by main's negation release (round 3); round 3's differential: a participant's code READY only where Corti's own selection is, in all 612 runs | installed behaviour; fresh live acceptance |
| [ ] | 5. The complete harness kept: Corti, Astra and Fable participate; first assessments frozen and hashed before peer conclusions are shared; peer reviews stored separately; tool traces and dated provenance kept; a skipped, refused, malformed or failed participant reported as partial completion, never silently substituted | NOT RUN | — | — | verify on the installed release and in fresh acceptance |
| [ ] | 6. The complete service set reconciled: distinct procedures and lesions, included components, units, potential modifiers; no separate charge for EMR components or prophylactic clipping; decompression investigated without the rejected shortcut; relationships recomputed after clarification and review decisions, on reload and before export | IMPLEMENTED (offline, not installed); refutation round 1 (six lenses over `3907cd592`: 16 findings, 12 blocking; 15 reproduced, each repaired in the shared readers; HARNESS.md "Refutation round 1 (2026-11-05)"): an EMR's own snare is its technique (multi-1), a lift told apart is still part of the EMR (own-4), "hemostatic" alone is never control of bleeding (multi-3, closing ACCURACY-RESIDUALS' prophylactic-clip row), a biopsy of a polyp then removed is part of the removal (multi-2), a decompression done, attempted or failed is listed where no code of its family accounts for it (compl-1; round 2 dropped compl-2's other families, recorded; round 3 reads the verb's bare form only in a failure or attempt frame) | `3907cd592`, `e88afe58b`, `90856a7d8`, `cb123f3a4` | an act no code of its family accounts for listed `unsupported` (the upper endoscopy's decompression: the only such pair in the catalogue), never bundled or hidden; an act part of another (an EMR's lift injection) never a code's act, a code with only such acts held (`act_included`); 88d9db32 offline: the lift injections and the clip listed as part of the EMR, 45381 on the tattoo alone, distinct-lesion modifier considerations on 45380, 45385, 45390 | recomputation after decisions, on reload and before export: verified live (items 9, 10) |
| [ ] | 7. The doctor-facing page kept simple: CPT numbers, units and modifiers where supported, short source-based reasons, review status, only necessary questions; no provider or model identity, prompt or trace in customer APIs, HTML, accessibility text, browser logs or downloads; truthful stages, elapsed time and failure states | IMPLEMENTED (offline, not installed) | working tree after `278aa4d2b` | admitted codes are ordinary numbered codes (structured fields and fixed sentences only); a code the list suggests is never listed again as not suggested; tests/test_h2_customer_admission.py scans every customer response and download for every role; 88d9db32's customer JSON offline: six codes, no identity word | the walk's customer scan and screenshots on the installed release (item 10) |
| [ ] | 8. The finished implementation verified: Linux tests and required CI; an independent refutation of the finished diff with concrete counterexamples (false approvals, negation, time, procedure ownership, multiple lesions, misleading completeness); findings reproduced before repair; failures kept | IN PROGRESS: round 1 (six lenses, 16 findings) repaired at `e88afe58b`; round 2 (three lenses over the repairs, 27 findings) repaired at `90856a7d8` under the two-cycle rule (the rules that did not converge dropped, their inputs pinned as recorded residuals under the equivalent standard); round 3 (a differential lens over round 2's rules, 306 inputs, both paths, against main) repaired at `cb123f3a4`: D2 held in all 612 runs; D1's three releasing families (decompression's verb, the coordinated marking, the stage-3 release) reverted toward main; the lens's 651 rows re-run with 0 D1 and 0 D2 flags | `cb123f3a4` | round 1 and 2 inputs in tests/test_h2_refutation_r1.py (31 tests, `RecordedResidualTests` among them); 29 round-2 mutants killed, restores verified; required CI on `5b1dc0466`: CI success, secrets-scan success, cpt-studio's 5,887 Django, 524 ops and 43 verification tests pass and its dependency audit stays red on pypdf 6.21.2 (interpretation 68); Linux full suite on the round-2 tree: 5,891 Django tests OK, ops 524, verification 43, node 131, 63 and 135 (run5, 13:20-13:34Z); H4 battery 6 declared movements, 0 undeclared, 0 new violations; H1 replay differs by the labels alone; required CI on `40e183346` (round 2): CI success, secrets-scan success, cpt-studio's 5,891 Django, 524 ops and 43 verification tests pass and its audit stays red on the same seven pypdf advisories (interpretation 68; the cpt-studio workflow is not a required check); round 3: 5 mutants killed, restores verified; Linux full suite on the round-3 tree 5,893 Django tests OK, ops 524, verification 43, node 131, 63 and 135 (run6, 14:04-14:18Z); battery the same 6 declared movements; replay labels only | required CI on `cb123f3a4`'s push |
| [ ] | 9. Installed through the project gates with a declared, reversible, available deployment; 88d9db32 re-assessed from retained responses with sends disabled; the prior assessment and decisions kept; served behaviour verified and remaining omissions explained | NOT RUN | — | — | — |
| [ ] | 10. Fresh live acceptance: a small new synthetic set (Word and PDF), expected services and provisional coding fixed before outputs are read; actual Corti, Astra and Fable participation; review decisions, reload persistence and an actual downloaded report matching them; agent-executed approvals labelled | NOT RUN | — | — | — |

**Verdicts (three, kept separate).** Functional completion, clinical accuracy and content-use permissions are reported
apart. A passing synthetic case is never reported as guaranteed accuracy, and missing reference coverage is never
invented.

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
