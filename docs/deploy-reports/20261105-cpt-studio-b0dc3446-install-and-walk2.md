# Install record: CPT Studio b0dc3446 (the leave-note fix and walk corrections) at cpt.quillmd.com, and the second acceptance walk (2026-11-05)

Evidence written after the act, judged against its declaration:
`docs/foundation/mutations/20261105-cpt-studio-leave-note-install.md`. The declaration was committed as `7da4475a` at
03:41:10Z and landed by PR #1470 as `7e8602e1`; the act ran from a detached checkout of that commit. Receipts are in
`/home/claude/cpt-studio-install-20261023`. Session a12d8fb3. The first install and walk are recorded in
`docs/deploy-reports/20261105-cpt-studio-24c49a50-install-and-walk.md`.

## Installed

Revision `b0dc3446c64c840cd01e9f37b8de3bad7aa954d4` (the merge commit of PR #1469). Image `cpt-studio:b0dc3446c64c`,
`sha256:b29413df09c1…`. It replaces `24c49a5032d5`, whose image is kept as the rollback image.
`https://cpt.quillmd.com/health/` serves `{"status": "ok", "service": "cpt-studio", "data_mode": "synthetic-only",
"release": "b0dc3446c64c840cd01e9f37b8de3bad7aa954d4", "database": "ok"}`.

| phase | when (UTC) | result against the declaration |
|---|---|---|
| preflight (session) | 04:03 | GO: disk 75%, 24 GB available, load 0.6, no OOM, co-tenants green |
| byte-identical check | 04:03 | exit 0 in the act's checkout |
| preflight | 04:03:52 | ok: tree `descendant-without-runtime-change`; active port 9151, idle 9150; vhost `f816a27d…` |
| image | 04:04:15 | ok: **all 8 steps came from cache**, the application copy and `collectstatic` included, because the declared precheck had built the identical `cpt-studio/` tree (`5f3e1f74`) minutes earlier. apt and pip did not run (the one match in the 47-line build log is a cached step's own header). The image's `CPT_STUDIO_RELEASE_SHA` and revision label are `b0dc3446…`; it runs as uid 10150; its 166 packages are identical to `24c49a5032d5`'s; pypdf is 6.21.2; both static copies of `app.js` carry the new notes |
| pre-app reading | 04:05:03 | equal to the declaration's baseline in every count; jobs_active 0; no reserved, sending or unknown run; last audit event 77 minutes old |
| pre-app dump | 04:05:10 | `pre-app-b0dc3446c64c-20261105T040510Z.dump` (0600, 2,304,093 bytes, sha256 `cdb84903518bd062…`), 39 TABLE DATA entries as declared; kept |
| app | 04:05:19 to 04:08:10 | ok. "No migrations to apply". 0 unrunnable stages. S1 to S5 as declared. The switch went from 9151 to 9150, and the vhost from `f816a27d…` to `259b895d…`, both as declared. HTTPS answered 200. Availability: 297 samples, 0 not 200, releases 24c49a50 then b0dc3446. Drain 130.5 s, 0 connections. states_recomputed `{"encounters": 51, "changed": {}}`. No leftover container. `nginx -t` passed with the same two pre-existing co-tenant warnings it printed at this act's preflight and at the first install (`quillmd:24`, `voice.kasitcorp.com:28`), so none is new |
| counts after app | 04:08 | equal to the pre-app reading. `studio_workerbeat` stays 1 row, now revision `b0dc3446`. Provider runs and audit events since the app started: 0 |
| operator checks | 04:09 | `/health/` on 9150 and public both serve b0dc3446. The served `app.46635bc18042.js` carries both notes. `/api/session` answers 409 `client_outdated` without the client header and 200 with it. `/ops/` answers 404 to review-agent and 200 to ops-agent. Sign-outs ended both sessions |
| verify | 04:10:09 | ok: "installed b0dc3446c64c verified; co-tenants and app.quillmd.com unchanged" |

**Observations, none a departure from a declared row:**

1. **The image had nothing left to build.** The declaration expected apt and pip to come from cache. The application copy
   and `collectstatic` did too, because the declared precheck had built the same tree minutes earlier. The release sha
   and labels are set after the last cached layer, and were checked.
2. **The operator checker failed twice on its first run, both its own defects.** It looked for the page's script on the
   sign-in page, which names none. Its header-less probe went through the shared sign-in helper, which adds the client
   header to every request (`ops/verify_login.py` `Transport.send`), so the probe was not header-less. Both were fixed,
   and the re-run passed every check. Only the re-run is counted as evidence.
3. **Login attempts rose by 4** between the post-app reading and the walk: the operator checker's two runs, each signing
   in twice.

The owner used the demo between walk 1 and this act: one upload and seven detail answers, 02:41 to 02:47Z. The
declaration's baseline was read after that, and no other encounter was touched during the act or the walk.

## The second acceptance walk (04:10:49 to 04:12:55Z)

`ops/verify_browser.cjs` from the act's checkout, the revision's own corrected walk, through review-agent with ops-agent
beside it. Two documents, both UI-state cases authored to reach those states; neither is accuracy evidence. The
author's expectations were sealed at 01:36:10Z before the offline prediction read either document.

**fresh-fail** (`4593c5b9`): PASS, 50 of 50 hard checks.
- The upload was acknowledged, then reading failed in 8 s, before any provider request: operator state
  `extraction_failed`, provider runs 0.
- The failed panel showed "Processing could not finish": reading did not finish, nothing else started, it ran for 1 s,
  no step was active and nothing animated.
- The plain error read "We could not read the text of this document. Upload a clearer copy, or paste the text instead."
  and offered "Upload a new document". The new leave note was shown: "You can leave this page — the document stays in
  Documents."
- No codes were served. The original is still served, byte-identical (sha256).
- Both viewports, the customer contract and vocabulary, the direct-URL probes and every scan passed.

**fresh-f3** (`72806166`): the workflow worked end to end. The walk reported 2 hard failures, a soft warning, and 148
hard checks passed.
- The upload was acknowledged, and it carried its client key (now detected).
- A reload while processing kept the same encounter and jobs, and sent nothing twice.
- **Stop** was requested 7 s after the upload and answered HTTP 200. The stopped panel showed its steps and the notice
  "Processing was stopped before it finished.", which the corrected walk read in the notice. It also showed **the leave
  note this install added**, "You can leave this page — the document stays in Documents.", and Resume. Nothing was sent
  while stopped.
- **Resume** answered HTTP 201. There were 5 provider runs, each sent once.
- 45385 was suggested, "Needs a detail", with one question in "A few details needed": "How far was the instrument
  advanced?", offering Not documented, Cannot confirm, and "Add to the documentation (physician)".
- The walk answered **Not documented**, the honest answer that asserts no clinical fact, in one save (HTTP 201):
  - it is held as the member's attributed context, not a revision;
  - it is asked once and persisted after a reload;
  - the answer sent nothing;
  - 45385 then reads **Excluded**, "A needed detail is not documented", and no code becomes approvable on an
    undocumented detail.
- Provenance checks passed: Corti is identified by endpoint, adapter version and identity, and Astra and Fable name
  their models. Every scan passed, along with the direct-URL probes.

| check | cause | whose |
|---|---|---|
| `clarification.extent` | the manifest expected the extent question at service scope; it is held on the code (proposal scope), as the offline prediction had shown (`open=[]`, `clar: ["extent"]` on 45385). The customer sees one row either way | **the manifest's** (the author's) |
| `after_details.dom.details_panel` | after the save the row shows "Saved: Not documented — by, when" and "Change this answer" (app.js savedAnswer), and the walk held it to an open row's answer buttons; its test drew a saved row by pasting a "Saved" line beside the buttons, a page no browser draws | **the walk's**: fixed in the PR that lands this record |
| soft `viewport.desktop.touch_targets` | "Save answers" is 134x41 px at 1440x1000, under 44 px; at 390x844 it is 318x44 | **the page's**, minor, desktop only |

**Mobile controls, read-only.** Walk 2 measured the panel at 390x844 only after its own save. So the open controls were
measured on an existing synthetic document of the review agent's (`2526aea5`, 2026-10-31), GET only, with no control
clicked:
- 2 rows, one of them open;
- 6 controls, each on screen, on top, enabled and at least 44x44 px: the date input, "Remove the entered date", "Not
  documented", "Cannot confirm", "Add to the documentation (physician)" and "Save answers";
- no horizontal scroll;
- 9 requests, none a write but the sign-in and sign-out.

The first two attempts lost the panel to a re-render; the measurement passed on attempts 1 and 3, and only attempt 3
took its screenshot.

**Independent checks.**
- `ops/verify_downloads.py`: fresh-f3's draft TXT and CSV, 56 of 56. fresh-fail has no downloads by design; the one
  "incomplete" is that.
- `ops/scan_customer.py` (GET only) over both encounters: pass.

**Counts against the declared bounds** (SELECT only, read per walk encounter):

| | fresh-fail | fresh-f3 | bound for fresh-f3 |
|---|---|---|---|
| provider runs | 0 | 5, each sent once | at most 5 |
| exchanges | 0 | 6 | at most 16 |
| jobs | 1 | 10 | at most 12 |
| assessments | 0 | 2 | at most 4 |
| member answers | 0 | 1 | 1 |
| decisions | 0 | 0 | 0 |
| reports | 0 | 2 (the draft TXT and CSV) | the HTTP 201s |
| second-review runs | 0 | 0 | 0 |

fresh-fail met its +0 bounds. Finding confirmations stay at 0, and jobs_active is back to 0. No other encounter was
touched during the walk.

**Measured usage, fresh-f3:**
- Corti: 0.034272 credits;
- Astra: 5,217 input and 1,259 output tokens;
- Fable: 29,322 input and 2,811 output tokens;
- no US-dollar estimate is recorded by the system.

Across both walks: Corti 0.083024 credits; Astra 17,674 input and 2,724 output tokens; Fable 67,445 input and 6,078
output tokens.
