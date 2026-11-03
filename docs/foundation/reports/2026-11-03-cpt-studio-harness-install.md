# CPT Studio GI coding harness: install and live acceptance walk (2026-11-03)

Session cd048041, the integration and deployment owner. The act's declaration is
`docs/foundation/mutations/20261103-cpt-studio-harness-install.md`. It landed in #1460, and its decision after the
image stop in #1461.

**Result.** cpt.quillmd.com serves revision `41e03656df617d5fab4a551ba7a0d7aea5ca3380` (#1459), image
`sha256:31d8d09721d5…`, with Corti, Astra and Fable live.

**Functional completion is established live,** on three fresh synthetic documents:
- genuine Corti, Astra and Fable responses, with each returned model exactly as requested;
- traced references;
- a saved synthetic review, intact after reload;
- reviewed reports downloaded and checked against the saved state.

**Not established:** clinical validation (no qualified coder has adjudicated a predeclared set) and content-use
permissions (D3 and D4 stay open).

## Phases

Every phase ran through `scripts/run-ruled-mutation.sh` and exited 0, and each receipt says ok. Each receipt is in
`/home/claude/cpt-studio-install-20261023` (untracked).

| phase | receipt | judged against the declaration |
|---|---|---|
| preflight | `preflight-20261103T193306134597Z.json` | Every row as declared. nginx files, the vhost, DNS, Let's Encrypt and the routing table are identical to the 2026-10-31 install's preflight, and so are the two known nginx warnings. check-cotenants exits 0. Only `cpt-studio-web` and `cpt-studio-db` publish 9150 and 55451. No foreign uid-10150 task; 161 GiB free |
| image | `image-20261103T193415728635Z.json` | **Stopped on two declared stop conditions**, then a decision was recorded and committed (#1461); see below |
| pre-app dump | `pre-app-41e03656df61-20261103T201514Z.dump` | 0600, 29 TABLE DATA entries, sha256 `ae5de17e…`. Read immediately before: every count identical to the declared baseline; jobs_active 0; no reserved, sending or unreconciled run; the last audit event 79 hours old |
| app | `app-20261103T201636446797Z.json` | migrate applied exactly 0007 and 0008. No unrunnable stage. `states_recomputed {"encounters": 43, "changed": {}}`. The 80df1831d168 pair was replaced and removed, and no `*-previous` container is left. The new pair has the same hardening, and only the worker mounts the three credential files, read-only. After the phase, the only count changes are migrations 6 to 8 and the five new tables, empty. No provider run, job or audit event was created during the install. `/health/` reports release `41e03656…` |
| passages | `passages-20261103T201745704270Z.json` | 3 sources, 62 passages (4, 16, 42); nothing else moved |
| license-note | `license-note-20261103T201808345481Z.json` | exactly as predicted: 2 rows from the old note to the new, `assessments_with_old_note` 58 |
| verify | `verify-20261103T201827408193Z.json` | https://cpt.quillmd.com/health/ serves `41e03656…` under normal certificate verification, and the four security headers appear once each. Cross-checked independently: the 22 containers outside CPT Studio running at preflight have the same ids and still run, the 41 volumes are unchanged, `cpt-studio-db` is the same container, and app.quillmd.com still serves `c8b54991c…` |

**The image stop.** The image phase's receipt said ok, but pip ran instead of coming from cache. The image's package list
also differs from the recorded one, in exactly `libsasl2-2` and `libsasl2-modules-db` (2.1.28+dfsg-10 to +deb12u1).

The cause is the session's own error:
- An unfiltered `docker builder prune -af` on 2026-11-02, in the owner-requested disk cleanup, deleted the 2026-10-31
  build cache.
- A hand-built precheck image then re-ran apt, and this build reused its layer.
- That precheck's `requirements.txt` context mode (0664) did not match the installer's (0644), so pip ran again here.

What was measured:
- The 23 Python distributions are identical in version and installed-file hashes.
- The database driver loads its own bundled `libsasl2`, identical in both images.
- The system copy is reached only through libldap and libcurl4, which back tesseract's URL input; CPT Studio does not
  use it.

The decision, appended and committed before the next phase, installs the image as built. Image `88544c7cd33f` stays the
rollback image.

## Access checks (the installed release, 2026-11-03T20:16Z)

| participant | endpoint | requested | returned | requests | latency | usage | estimate |
|---|---|---|---|---|---|---|---|
| Corti | `https://api.us.corti.app/v2/tools/coding/` | (no model id) | (none; Corti takes no model id) | 2 (OAuth token, coding) | 5,024 ms | 0.013192 credits | credits, not USD |
| Astra | `https://api.openai.com/v1/responses` | `gpt-6-astra` | `gpt-6-astra` | 1 | 7,906 ms | 1,773 in / 503 out | US$0.0429 |
| Fable | `https://api.anthropic.com/v1/messages` | `claude-fable-5-1` | `claude-fable-5-1` | 2 (one `cms_code_facts` tool call) | 4,630 + 7,242 ms | 7,273 in / 919 out | US$0.1187 |

Each check's output was scanned by the installer's root helper, which found no credential value in it, before anything
was recorded. The checks wrote no database row.

## The acceptance walk

All three documents went through https://cpt.quillmd.com, through the ordinary reviewer account `demo-reviewer`
(manifest sha256 `f6653f63…`, `ops/verify_browser.cjs --acceptance-reviewer --expect-harness --allow-live-provider`),
one at a time. Each approval's note says "session-made synthetic acceptance-test approval, not a human review"
(interpretation 63).

| document | format | encounter | Corti / Astra / Fable | peer reviews | approved (HTTP 201) | reload | reviewed report | assertions | bounds |
|---|---|---|---|---|---|---|---|---|---|
| hw-01 colonoscopy, cold snare | text-layer PDF | `45e69936…` | 45385 / 45385 / 45385 | both used | 45385 | persisted | TXT and CSV downloaded; verify_downloads 94 of 94 pass | 40 pass, 0 fail | within |
| hw-02 EGD, antral biopsy | DOCX | `75bde12b…` | 43239 / 43239 / 43239 | both used | 43239 | persisted | 94 of 94 pass | 39 pass, 0 fail | within |
| hw-03 flexible sigmoidoscopy, biopsy | pasted text | `1c9f052d…` | 45331 / 45331 / reading not used | Astra's used; Fable's not sent | 45331 | persisted | 92 of 92 pass | 39 pass, 0 fail | within |

Every document reached its reviewed report with no clarification, no exclusion and no console error. Processing took
36, 47 and 27 seconds. The bounds are the declaration's: per document, at most 5 provider runs, 16 exchanges, 10 jobs
and 2 assessments, with no second review and no finding confirmation.

**Fable on hw-03.** Anthropic answered: HTTP 200 on both exchanges, `claude-fable-5-1` returned exactly, and an
estimated US$0.1354 was spent. CPT Studio did not use the reading, because the answer breaks the reading schema: its one
`not_coded` entry carries an extra, empty `reason_detail` field. The schema's `not_coded` item allows only
`service_ids`, `code`, `reason` and `evidence` (`additionalProperties: false`). Because Fable's first reading was not
read, its peer review was not sent.

This is the participant failing to conform, not a hold and not a pipeline failure. The harness failed closed as
designed. Corti's assessment is unaffected, because a participant's code is never a proposal in this release (D14). The
page and the reports state it ("answered; the reading was not used", with the reason). The reason names the unknown key
by its length, not its text, by the round-3 redaction rule (I9).

**Traced references.**
- **Fable's tool loop:** retrieved 8, 32 and 16 CMS facts through `cms_code_facts` and used 3, 4 and 0 of them. Astra
  made no tool call.
- **The assessment's own retrieval:** traced each approved code's PFS RVU26D and MUE 2026-Q4 facts. Reference
  validation checked 1 code against 6 passages per document.
- **Not connected, as D3 and D4 stand:** NCCI procedure-to-procedure edits ("AMA licence agreement not accepted"), AMA
  CPT descriptors and guidelines, and payer policies.

## Requests, latency and usage (the walk)

| doc | participant | purpose | HTTP | returned model | requests | latency (ms, per exchange) | input / output tokens | estimate |
|---|---|---|---|---|---|---|---|---|
| hw-01 | Corti | primary | 200 | (none) | 1 | 6,706 | 0.020136 credits | credits |
| hw-01 | Astra | independent | 200 | gpt-6-astra | 1 | 7,631 | 2,026 / 481 | US$0.0300 |
| hw-01 | Fable | independent | 200 | claude-fable-5-1 | 2 | 2,372 + 10,041 | 11,880 / 1,146 | US$0.1761 |
| hw-01 | Astra | peer review | 200 | gpt-6-astra | 1 | 2,599 | 2,342 / 28 | US$0.0248 |
| hw-01 | Fable | peer review | 200 | claude-fable-5-1 | 1 | 1,963 | 4,284 / 93 | US$0.0475 |
| hw-02 | Corti | primary | 200 | (none) | 1 | 8,057 | 0.032804 credits | credits |
| hw-02 | Astra | independent | 200 | gpt-6-astra | 1 | 6,576 | 1,820 / 538 | US$0.0308 |
| hw-02 | Fable | independent | 200 | claude-fable-5-1 | 2 | 3,590 + 10,082 | 15,372 / 1,268 | US$0.2171 |
| hw-02 | Astra | peer review | 200 | gpt-6-astra | 1 | 12,446 | 2,363 / 28 | US$0.0250 |
| hw-02 | Fable | peer review | 200 | claude-fable-5-1 | 1 | 2,044 | 4,367 / 101 | US$0.0487 |
| hw-03 | Corti | primary | 200 | (none) | 1 | 6,239 | 0.023724 credits | credits |
| hw-03 | Astra | independent | 200 | gpt-6-astra | 1 | 5,832 | 1,782 / 466 | US$0.0268 |
| hw-03 | Fable | independent | 200 | claude-fable-5-1 | 2 | 2,524 + 7,569 | 8,841 / 940 | US$0.1354 |
| hw-03 | Astra | peer review | 200 | gpt-6-astra | 1 | 2,305 | 1,728 / 28 | US$0.0187 |

**Walk:** 14 provider runs, every one HTTP 200 and sent once. 17 vendor requests are recorded: 3 Corti coding requests
and 14 participant exchanges, with 4 tool calls. Corti's OAuth token requests are not recorded as runs. The
participants' estimate is US$0.7809 and Corti used 0.076664 credits. **With the access checks,** the participants'
estimate is US$0.9425 against the US$10 stop, and Corti used 0.089856 credits. The estimates come from fixed published
rates dated 2026-11-01 and are not reconciled to an invoice.

## Holds and failures, reported separately

- **Holds in the walk:** none. Each document's one planned code was ready, and no question was asked.
- **Software failures in the install and the walk:** none. Every phase passed, 0 assertions failed, verify_downloads
  found 0 failures, there were 0 console errors and no 5xx.
- **Participant outcome:** Fable's hw-03 reading was refused on schema grounds, failing closed as designed, as above.
- **Deviations from the declaration:** the image stop, caused by the session's own build-cache error and decided under
  the declaration in #1461. It is recorded, not hidden.

## Unchanged by this act (I1), and still open

- **False READYs on the installed Corti-only path:** HARNESS.md 12.14's classes, and 12.20's attached prior EGD report,
  whose title Corti cites for 43235. They are the first target of the shared-reader repair, and pausing the live
  demonstration until then is the owner's decision.
- **The diagnostic base not held again** after a reinstatement (12.18, blocking). Its repair is a review-layer base
  hold. The walk reinstated nothing.
- **pypdf 6.21.2 and its seven advisories** (CVE-2026-119203 to CVE-2026-119209). The `cpt-studio` CI job's pip-audit
  step stays red on them. That is stated, never waived: interpretation 68 is the owner's open question.

## Open owner decisions (none of these is approved)

| item | exact wording | affected | recommendation |
|---|---|---|---|
| checklist 4.6 (class a) | "A documented path by which a source-supported finding corrects the shared date, status or extent interpretation, so that a false hold changes instead of gaining commentary; no promotion by agreement; clinical safeguards kept" — NOT DONE in this release (D7, HARNESS.md 12.10) | Stage 4.6; the reviewed report of any document with one of the three false holds (h4-01 99204, h4-03 43244, h4-06 45385); the dormant confirmation code (HARNESS.md 11.3, 12.5, 12.10) | (i) a reviewer's explicit, recorded override that claims no verification, built as its own change with its own refutation, for the holds the readers cannot honestly release. Reader repairs (ii) stay the route for the false READYs |
| D3 (licensing, 4.2) | "Licensed CPT content: either an AMA licence (descriptors, guidelines), or acceptance that validation uses CMS public sources only and says so" | 4.2 and every sentence that says what validation used | the second option: CMS public sources only, said so. That is what the product does today. The owner's remark that descriptors are not needed fits it, but it is not recorded as the decision until the owner states it |
| D4 (licensing, the product) | "The AMA position (FAQ, updated 2026-07-14): developing and testing products that use CPT needs an AMA licence. CPT Studio holds none, and no source read supports its 'internal synthetic evaluation' note. NCCI PTP edits are reachable only through an AMA point-and-click agreement limited to CMS programs" | 4.2 and the product as a whole | before any use beyond the protected synthetic demonstration, obtain an AMA licence or counsel's written opinion. Until then keep the synthetic-only framing, claim no right to CPT content and accept no agreement (the PTP agreement included) |
| D5 (the harness) | "Corti's public terms (§2.6.1.9) bar customers to 'benchmark or test the Platform for competitive purposes without prior written approval'. ... Whether that is 'for competitive purposes' is not stated; the owner's signed Corti agreement is not available to this review" | every harness@2 run, the reports' side-by-side participant sections, any accuracy comparison | get Corti's written confirmation, or read the signed agreement. Until then publish no comparative metric of Corti against the other two |
| interpretation 68 (class b, pypdf) | "For the owner (class b): stay on 6.21.2 with seven known advisories, or accept round 4's false holds on some glyph-index and EUC-H checklist layouts to clear the audit, or fund further rounds. Nothing here changes what the installed reader does." | Stage 2 (PDF reading); the `cpt-studio` CI job's pip-audit step; the security posture of PDF uploads | stay on 6.21.2 for the protected synthetic demonstration, as an explicitly accepted risk; fund further rounds of the 6.21.4 reader before any wider exposure or any real document |
| D14's question (class a) | "should a participant's own code ever become a selectable proposal again, and on what reader guarantee?" (HARNESS.md 12.14) | the harness path; 3.7 | only after the shared-reader repair passes its own refutation, and re-enabled by the owner |
| the release standard (class a) | "which release standard governs a reader repair, the round-4 standard or that parity standard?" (HARNESS.md 12.14) | the shared-reader repair; X2 for h4-03 | the owner's choice; X2 is to be coded only if the owner rules for the parity standard |

## What is not claimed

- No coding-accuracy figure and no reliable-coding claim: three documents prove the pipeline runs end to end, not that
  its codes are right.
- No reviewer confirmation (4.6, D7). No scanned-PDF (OCR) document was walked, and no clarification arose to answer.
- Failure and unavailable-provider states were not walked, nor was the administrative trace view.
- The 43 existing encounters were neither re-assessed nor re-sent.
- Data at rest is unencrypted and there is no scheduled backup.
- The pre-app dump is the only data-level way back.

## Evidence kept (untracked)

The walk's evidence is in `/home/claude/cpt-studio-gi4-20261031/walk-harness-live/hw-0{1,2,3}-*/`, 0700:
`evidence.json`, `downloads.json`, the downloaded reports and screenshots. They are synthetic, and treated as clinical
exports by the hygiene rule: shredded once the owner has read this report.
