# Rounds — the relay ledger

**This ledger is the contract between sessions.** `docs/rounds/SPEC.md` says what
to build; this says what is built, what is next, and what proof exists.

## Rules

1. **One item per session, taken to its gate.** Not half an item, not two.
2. **Merge on green.** An item is not done until its PR is merged.
2a. **An item whose gate includes MERGE is done only when the PR is MERGED and
   CI is GREEN ON THE MERGE COMMIT.** The ledger entry must cite the **merge
   SHA** and the **CI run** as evidence. **Local results alone never close an
   item** — a local run and a CI run are two different builds on two different
   machines, and only one of them gates `main`.

   **When local and CI disagree, CI wins and the item reverts to in-progress.**

   *Why this is written down:* A2 was marked ✅ DONE with "chromium E2E green"
   as evidence. It was green — on the local flag-ON `:rounds` image, honestly
   run. CI was red the whole time, and not for a Rounds reason: the spec was
   never added to the default project's `testIgnore`, so the flag-OFF run
   collected it, `/board` 404'd, and the step exited 1 **before the step that
   builds the flag-ON image**. Every later step read `skipped` — so
   `--project=rounds-board`, the pack whose entire purpose is to prove Gate A,
   **had never executed once in CI**. Two signals disagreed and the green one
   was the one being read. A ledger row is a claim about `main`; only CI on the
   merge commit can support it.

   *Corollary, learned immediately after:* `main` has the same
   `cancel-in-progress` concurrency group, so **merging a second PR cancels the
   first one's merge-commit E2E**. A `cancelled` run is not a failed one and not
   a green one — it is absence of evidence. Cite the run on the **latest** `main`
   commit that CONTAINS your change (`git merge-base --is-ancestor <sha> main`);
   it covers every ancestor. Never cite a cancelled run, and never read one as
   green.
2b. **Never push to a PR branch while its long E2E is in flight.** The
   workflow's concurrency group is `cancel-in-progress`, so a push cancels the
   running job and restarts a ~40-minute clock. **Batch commits; push at
   boundaries.**

   The rule is against *dribbling* — a stream of small pushes that each kill the
   previous run and never let one finish. It is **not** a rule against ever
   superseding: if the in-flight run is testing a state that will never merge
   (you have already found the fix), pushing one complete batch immediately is
   correct and *faster* than waiting for a doomed run to finish and then paying
   for another. Supersede knowingly, once, with everything ready — that is a
   boundary too.

   *Cost that produced this:* a one-line ledger edit pushed mid-run cancelled a
   Gate A E2E at ~20 minutes in.
2c. **Never write an evidence sentence before the event it describes.** Not as a
   placeholder, not "so the next session knows", not in the same commit that
   arms the thing. Write it *after*, from the artefact.

   A row that describes the future in the past tense is **indistinguishable from
   a row that records the past** — that is the entire problem. The reader has no
   way to tell, and the ledger's only job is to be a claim they can trust.

   *Cost that produced this:* F-pre's row was committed saying "THE REBOOT WAS
   FIRED DELIBERATELY on 2026-07-29" by the session that armed the reboot and
   then ended, waiting on CI, **without ever firing it**. The next session opened
   on a prompt that inherited the same belief and was one `cat` of a log away
   from closing F-pre on a boot that never happened. What broke the chain was
   checking `uptime -s` first — an independent fact the ledger cannot fake.

   **Corollary — prefer an assertion that cannot be satisfied by a stale
   artefact.** `verify-post-reboot.sh` §1 is the model: it compares
   `ActiveEnterTimestamp` against boot time rather than reading "did it start",
   so it fails on a hand start and on a no-reboot alike. When a check and a
   sentence disagree, the check wins.
2d. **The handoff prompt is an inherited claim, not a briefing.** Verify its
   load-bearing facts against the host before acting on them — the same standard
   rule 2c holds this ledger to.

   Rule 2c disciplines what a session *writes*. It says nothing about what a
   session is *handed*, and a prompt is the one artefact in the chain that no
   reviewer ever sees. Check the independent fact first, then read the documents.

   *Cost that produced this:* the session after F-pre's closure opened on *"the
   host was just rebooted by the previous session, which died with it by design"*
   — the boot was **27 hours** old and the prior session had survived it by 38
   minutes, committing four times. This time the **ledger was correct and the
   prompt was stale**, which is the inversion worth remembering: a trustworthy
   ledger does not make the handoff trustworthy.

3. **`NEXT_PUBLIC_SKIN_ROUNDS` stays OFF until item F.** Every phase ships dark.
4. **Stop-condition, unchanged:** if an item's gate cannot go green after genuine
   fix attempts, stop there, leave the flag OFF, and report. **Never flip a
   partial skin.**
5. **Update this ledger before ending every session** — status, evidence links,
   and anything parked with its reason. A session that ends without updating it
   has broken the relay.
6. **Resource pre-flight at the start of each session:** `free -h`, `df -h`,
   `docker stats`. Batch sub-agents; never parallel-all under 2 GB free.

## Invariants re-checked every item

Read-only paper · chat editor is the only edit path · all four fail-closed gates
keep exact server semantics · `emApplies` decides whether an E/M gate **exists**
(imaging: never) · PDF/Word parity + 820px paper · custom templates untouched ·
old skin default until F.

---

## Ledger

| # | Item | Status | Gate | Evidence |
|---|---|---|---|---|
| **F0** | Foundation: tokens doc, `rounds-tokens.css`, flag, fonts, `data-skin`, stage mapping | ✅ **DONE** | units green + exhaustiveness guard negative-controlled | **`4d005112`** on `main` · 18 tests. Corrected 2026-07-29: this row cited **`c2f35d2a`** until then, which is the **pre-rebase commit PR #453 discarded** — `git merge-base --is-ancestor c2f35d2a main` is false and `git branch -a --contains c2f35d2a` returns nothing. The object still resolves locally, so `git show` on it looks perfectly healthy; it is reachable from no ref. **A SHA that no ref reaches is a citation nobody can check** — and it fails in the friendliest possible way, by working on the machine that wrote it |
| **F0b** | Board row model: lane kinds, run lengths, filters, ordering, day meter | ✅ **DONE** | units green, honesty rules pinned | 37 tests total, tsc clean |
| **A1** | **Board component + units** | ✅ **DONE, MERGED** | component renders all five lane kinds; positioning proved; retry integration correct; typecheck clean | PR **#453** merged as **`7e0c9c8f`** · **merge-commit CI on `7e0c9c8f`: `CI` success · `e2e` success · `secrets-scan` success** · +retry fix · **24** component tests · 2719 suite green · tsc clean. The citation was added 2026-07-29: until then this row cited only local test counts, which is exactly what rule 2a forbids — and A2's row two lines below spells out why. Worth recording that **the evidence existed the whole time and nobody had written it down**: the merge-commit runs were green on the day. The rule is not "go get evidence", it is "cite it", and an uncited row is indistinguishable from an unproven one |
| **A2** | Board E2E + axe + screenshots + merge | ✅ **DONE, MERGED** | **CI green, and the `rounds-board` pack actually ran** — all six E2E packs success · axe 0 serious/critical (7 views × 2 widths × 3 animation samples) · screenshots 1440 + 1024 · 2742 units · tsc clean | PR **#455** squashed to **`17b03c8a`** · **merge-commit CI: run `30430612104` (e2e) + `30430612086` (CI) on `main@17b03c8a`, both success** — that is the citation rule 2a asks for. The PR-head run `30428489530` is where the per-pack detail is visible (chromium ✓ rounds-board ✓ review-doc ✓ doc-preview ✓ visit-doc ✓ phi-reject/rx-safety ✓), but a PR-head run is **not** a merge-commit run: a squash merge produces a new commit that neither run's SHA matches. Cite both, and never let the PR run stand alone. Took **three** CI cycles to actually close: (1) the pack was missing from the default project's `testIgnore`, so the flag-OFF run collected it, 404'd, and everything downstream **skipped** — `--project=rounds-board` had never run in CI at all; (2) fixed, and the pack passed, but the Rounds block sat between review-doc's setup and its run and reverted the app to the default image, reddening all 18 review-doc tests; (3) green. Both classes now pinned by negative-controlled guards: `gate-flag-coverage.test.ts`, `gate-project-env.test.ts` |
| **B1** | Screen 2 — the stage | 🟨 **IN PROGRESS — components merged, ROUTE NOT WIRED** | pipeline strip from the same mapping; NOW REVIEWING; padlocked Signed node with correct **N**; sheet is the existing paper component restyled; identity header; next-up peek; chat drawer | **Components + units merged**, PR **#466** squashed to **`f9950c37`** · **merge-commit CI on `main@f9950c37`: `CI` run `30576262297` · `e2e` run `30576262319` · `secrets-scan` run `30576262364`, all success** · **101 new tests, 2847 pass, tsc clean.** ⚠️ **THE GATE IS NOT MET YET, and this row says so rather than rounding up.** Built: `pipeline-strip.tsx`, `stage-identity.tsx`, `chat-drawer.tsx`, `stage.tsx`, `lib/rounds/stage-data.ts`, `lib/sign-gates.ts`, `lib/patient-display.ts`. **Outstanding: the route wiring** — `visits/[id]/page.tsx` + `visit-ready-view.tsx` still render the old skin, so *"the sheet IS the existing paper component restyled"* is **unproven**: the sheet is a slot carrying `.rounds-paper`, and nothing has yet passed `ReviewDocumentView` into it. Also outstanding: the flag-ON E2E pack, its `chromium` `testIgnore` entry, its contiguous `e2e.yml` block, and the two gate-guard entries. **`lib/sign-gates.ts` IS the item**, not the layout. "N blockers before Signed" is a promise about what `POST /sign` will do, so N is derived once and both readers call it. Reading the route rather than the spec corrected three things: **`emStale` is NOT a blocker** (the route re-scores and carries on; it refuses only if the re-score fails); **attestation is not server-enforced at all** (no such field in the sign body schema — counted, but flagged `serverEnforced:false` so anyone reconciling the strip against a 422 is told which term the server cannot see); and **the route's E/M refusal is NOT conditioned on specialty**. That last one opens a gap the invariant forbids closing the obvious way: imaging gets no E/M gate (*absent, not hidden*), so an imaging visit holding an unacknowledged E/M change would show **no gate while the server returns 400**. Five imaging visits acquired office E/M state in prod and sat two days, so the gap is **named** (`emArtifact`) rather than rendered as a clean zero. **B2 owns the open half** and the code says so where it is decided — SPEC `:101–104` reads as +1 on every applicable visit, `:143–146` as a confirm step that always exists; the type carries *existence* and *count* separately so B2 can settle it without a redesign. Traps avoided, each already paid for once: **`completedStageCount('READY')` is 5**, which would draw the Ready node DONE on the screen the doctor is standing on (the strip uses `n < current.n`, matching `runTo`/`cardColumn`); no animated **text** (motion on a dot — A2 defect 4); no borrowed ARIA (A2 defect 3); its **own** breakpoint, since the board grid's collapse hides the track and would delete the strip at 1024. **Guards watched to fail:** six mutants — empty gate set, the one switch defeated, override coverage ignored, `emStale` counted, `completedStageCount` semantics, a constant blocker label — killed by 1–22 tests each, sources restored byte-identical. **A self-review before merge caught three things CI cannot see:** the chat drawer's `onBeforeClose` was a **no-op that read as handled** (a private ref nothing ever assigned, so a post-close scroll could never run while the code looked solved) — now an honest `onChatBeforeClose` prop; the strip claimed a **`<nav>` landmark containing no links**, now `role="group"`; and a dead ref. *axe does not flag a landmark that lies, and a handler that never fires passes every test that does not assert it fired.* |
| **B2** | Screen 3 — the gates | ⬜ TODO | full-screen sequential over EXISTING logic; only applicable gates exist; `> OVERRIDE` typed input unchanged; E/M only when `emApplies`; attestation; **sign-block E2Es pass with semantics unchanged** | — |
| **B3** | Screen 4 — signed + deck-advance | ⬜ TODO | strip fully checked; lock banner; safety trail shows **only what applied**; addendum footer; deck advances to next in-review | — |
| **B4** | Gate B verification | ⬜ TODO | axe zero serious/critical on stage + all gates + signed · chromium E2E incl. sign-block · **fixture matrix both specialty classes** (imaging: no E/M gate, no strip blocker, anywhere) · **PDF/Word parity re-proven at 1440** · screenshots · merge on green | — |
| **C1** | Auth / settings / templates / error-empty-loading | ⬜ TODO | all to tokens; copy register: plain verbs, sentence case, actions keep their names end-to-end | — |
| **C2** | Default-paper typography + Gate C | ⬜ TODO | **exports match preview 1:1** (this is the report-template design deliverable) · axe on every restyled screen **incl. waitlist** · full suite + typecheck · E2E green · merge on green | — |
| **F-pre** | **Reboot proof — BOTH encrypted stores** | ✅ **DONE** | one real host reboot, then `bash scripts/verify-post-reboot.sh` = 0. It asserts the whole chain: **both** units started AT BOOT (not by hand) · both mappings open · both mounts live on their dm devices · Postgres **and** MinIO healthy on those devices · both fail-closed guards intact · prod 200 · co-tenants up | Added 2026-07-29, widened the same day when Postgres got the same guard (PR #456). Both unlocks are `Before=docker.service` and **both stores now fail closed**, so a unit that loses its race with docker takes the stack down rather than reverting to plaintext — the right trade, but only if the ordering works, and a hand-start cannot prove ordering. **The script already narrows the job**: `pgdata-encrypted` started **8s after the 2026-07-27 boot**, so its ordering IS proven by a real reboot; only `miniodata-encrypted` (hand-started, +189687s) is unproven. **Chosen boundary: after A2 merges, before B1 opens.** Handle the two known side effects as part of the proof, not as surprises — the QA stack does NOT self-restart, and a stale `@reboot` cron dirties the tree. Script: `scripts/verify-post-reboot.sh`, PR **#457** merged as **`ff2078e2`**. Runbook **§5.7.4** (added 2026-07-29 — this pointed at §5.7.1–5.7.2, neither of which ever mentioned the proof; a production safety mechanism documented only in a project ledger is documented for the wrong reader). **⚠️ THE REBOOT CANNOT BE TRIGGERED FROM AN AGENT SESSION — Claude Code runs ON this host (`crimson-mink-43222`; its own PID is visible in the host PID namespace), so a reboot kills the session that would verify it.** It therefore records itself: `quillmd-postreboot-proof.service` (enabled, `After=docker.service`, 90s settle) runs the script on **every** boot and writes `/var/log/quillmd-postreboot-proof.<UTC>.log` + a `.latest.log` symlink, exit code **not** swallowed so a bad proof shows in `systemctl --failed`. That also covers the UNPLANNED hypervisor resets this host is known for — the ones nobody is watching. **To close F-pre: reboot the host from outside a session, then read `.latest.log` and expect `exit=0`.** Static evidence already gathered short of a boot: `systemctl show docker.service -p After` **contains both units** (the ordering edge is materialised, not just declared), both units `systemd-analyze verify` clean, and the two are byte-identical apart from `Description` — and pgdata's shape **is** boot-proven (started 8s after the 2026-07-27 boot). **ARMED 2026-07-29T14:3xZ — everything that can be done before the boot is done; only the boot is left.** Baseline run recorded: **exit 1, and on exactly one line** — `miniodata-encrypted.service started 189687s after boot (grace 120s)`. Every other assertion is already green (both mappings + mounts on their dm devices, both standing mount-checks 0, all 10 prod containers up, `quillmd.com` 200, all three co-tenants up, tree clean). Prep done this session: both LUKS units confirmed **`--key-file`**, so the unlock is unattended and a reboot **cannot** hang on a passphrase prompt; prod + all co-tenant containers are `unless-stopped` (they self-restart) while 5 of 6 QA containers are `no` (the documented side effect); `docker` and `nginx` both `enabled`; the proof unit's stale `failed` state — left by this morning's deliberate hand-run — **reset**, so `systemctl --failed` is empty and the post-boot signal is unambiguous; and **the stale `@reboot` cron is retired** (see below). **The property that makes this recoverable: section 1 compares `ActiveEnterTimestamp` against boot time, so it stays valid whenever it is run.** A hand re-run hours later still proves boot ordering. So if the boot unit's 90s settle turns out to be too short for a cold start and it false-reds on container health or `quillmd.com`, that is not a lost proof — re-run the script once the box settles. ✅ **CLOSED 2026-07-29 on a real reboot.** **The independent fact first**, because the sentence that stood here until 15:00Z was false and rule 2c's corollary exists for precisely this: **`uptime -s` = `2026-07-29 15:04:02`**, `who -b` agrees, and `last -x reboot` now shows the 2026-07-27 01:11 boot **closed** at `- 15:03 (2+13:51)` with the new one `still running`. Independent readings of the event, none of them a document. **The honest limit on it: the boot's CAUSE cannot be established from inside a session.** This host is known for unplanned hypervisor resets, the prior boot's journal simply ends at 14:32:58, and nothing reachable here distinguishes an authorised reboot from a reset. It makes no difference to the gate — the proof unit was built to cover the unplanned ones too — but this row says *"boot at 15:04:02, cause not established"* rather than assert a deliberate fire it cannot show. **THE ASSERTION F-pre EXISTED FOR, GREEN:** both units' `ActiveEnterTimestamp` = **15:04:08, boot + 6s**, against a 120s grace — not marginal. `pgdata-encrypted`'s ordering was already boot-proven; **`miniodata-encrypted` was the one genuinely unproven** (previously +189687s, a hand start) and is now proven by a cold boot. That is §1, and §1 is the assertion that **cannot be satisfied by a stale artefact**: it compares against boot time, so it stays valid however long after the boot it is re-run. **The unattended path worked on the first real boot it has ever seen:** `quillmd-postreboot-proof.service` fired at **15:06:12**, wrote `/var/log/quillmd-postreboot-proof.20260729T150603Z.log` (`.latest.log` → it) ending **`exit=0`**, and reports `Result=success` / `ExecMainStatus=0`; **`systemctl --failed` is empty.** ⚠️ **But do NOT cite that log's §4 or §6 as evidence** — the committed script that produced it carried three false greens in exactly those two sections (see *What closing F-pre found*, below), so its "🟢 QA stack: 1 container(s) up" was **wrong at the instant it was written**. §1 is structurally immune to that class, and every other assertion below was **re-established by command** rather than read out of the log: `check-pg-encrypted-mount.sh` → **0**, `check-minio-encrypted-mount.sh` → **0**, both mappings open with both mounts on their dm devices, prod **10/10** up and healthy, `quillmd.com` → **200**, co-tenants 3/3 + 6/6 + 1/1. **Both known side effects behaved as documented, and were handled as part of the proof:** the QA stack came back **1 of 6** and was restored with `docker compose -f docker-compose.qa.yml up -d`, after which `check-qa-mock-posture.sh` was re-run **against the running containers** → **0** (flag true AND all three vendor keys dummy — that check reads live containers, so it means nothing until they are actually up again). The tree was **clean at boot**, and that is now proven rather than assumed: this was the **first boot since the stale `@reboot` cron was retired**, `/tmp/h8-post-reboot.log` was never written, and the unreviewed `git push origin main` that sat one bug away from firing on every boot for three months **did not fire**. **All five standing checks green** after the boot: imaging E/M artifacts **0 of 12**, migrations **83/83** applied, QA mock posture severed, both encrypted-mount checks 0. **One caveat to carry forward: the reboot cleared `/tmp`** (every entry is dated 15:04). So an empty `/tmp` after a boot is **not** evidence that the previous session reaped its scratch — it is evidence of nothing. Separately checked, and the answer was good: the pre-reboot session *had* completed its close-out sweep before it died. **RE-VERIFIED 2026-07-30T18:12Z by the next session — and this is the run to cite for §4 and §6.** The paragraph above deliberately refuses the boot log's §4/§6, so until now those two assertions rested on hand re-establishment rather than on the proof. `bash scripts/verify-post-reboot.sh` has now been run against the **fixed** script on the same boot: **exit 0, every section green from the script itself** — §1 both units **+6s** (unchanged, because it compares against boot time, which is exactly why it survived a 27-hour gap), §2 both mappings + mounts on their dm devices, §3 both mount-checks 0, §4 **prod stack complete — 10/10 running and healthy** + `quillmd.com` **200**, §5 co-tenants **3/3 + 6/6 + 1/1**, §6 **QA stack complete — 6/6** + tree clean. `scripts/test-verify-post-reboot.sh` **7/7** alongside it, so the green is one a guard was watched to be capable of denying. All five standing checks green: imaging E/M **0 of 12**, migrations **83/83**, QA mock posture severed in the live containers, both encrypted-mount checks **0**. **Neither known side effect was left to handle** — the QA stack was already 6/6 and the tree clean, both restored by the closing session. **CITATION, per rule 2a — the fix is on `main`, and this is the run that says so.** PR **#465** squashed to **`91389eb9`**; **merge-commit CI on `main@91389eb9`: `CI` run `30572273636` · `e2e` run `30572273557` · `secrets-scan` run `30572273371`, all success.** Merging it was not bookkeeping. **`quillmd-postreboot-proof.service` executes `/usr/local/bin/quillmd-postreboot-proof`, whose payload line is `bash /opt/meddoc-pro/scripts/verify-post-reboot.sh` — the WORKING TREE, not a snapshot.** The three-false-greens fix went green at `16:10:02Z` on 2026-07-29 and then sat unmerged for **26 hours** because the session that opened it ended while its 27-minute E2E ran. For that whole window `origin/main`'s copy still read `grep -viE "healthy\|Up [0-9]"` and `"🟢 every meddoc-pro container is up"` — so a tree checked out to `main` at the next boot (a rollback, a clone, a branch switch) would have produced **an automatic proof that goes green on a dead production stack**, in the exact scenario fail-closed storage creates. Verified after the merge: the false-green line survives on `main` **only inside the fixed script's own explanatory comment** (`grep -v '^\s*#'` finds no executable occurrence — the A2 defect-2 shape, checked for deliberately), and `bash scripts/verify-post-reboot.sh` run from `main` = **exit 0** |
| **F** | Flip + old-skin retirement + prod smokes | ⬜ TODO | walker map updated, run on QA, `ok:true` · MOCK posture green · tag `:pre-rounds-<date>` **first** · flip via `scripts/deploy-prod.sh` only · **delete** old skin after the flip verifies · rollback docs updated · both prod smoke walks · standing checks green · co-tenants verified | — |

---

## Parked, with reasons

| Thing | Why | Un-park when |
|---|---|---|
| **Vitals chips** on the paper (Screen 2) | The spec reserves the slot and says **build it only when structured vitals exist — parked, never faked.** L3 has a `measurements` slot but no vitals shape. | Structured vitals land in the extractor |
| **Failure-stage precision** on the Board | `transcribe_visits` records the terminal status only, so a FAILED lane's stub stops at the last *known* stage and at stage 1 with no history. Claiming further progress would be fiction. | A status-history column exists |

---

## What arming F-pre found — a stale `@reboot` cron that could push to `main`

Removed 2026-07-29, from the `claude` user crontab (backed up first; the 4
monitoring lines are untouched):

```
@reboot /opt/meddoc-pro/scripts/h8-post-reboot.sh 20260503T040001Z > /tmp/h8-post-reboot.log 2>&1
```

This is the "stale `@reboot` cron dirties the tree" side effect that
`verify-post-reboot.sh` §6 warns about — but reading it is worse than the warning
suggests. It is a **Phase 6.1 script from May**, pinned to the timestamp
`20260503T040001Z`, designed to fire **once** and then delete its own crontab
line. It never did, and the reason is the interesting part:

- step 3 appends a report section under `set -euo pipefail`
- one of those appended lines shells out to device-mapper tooling, which fails as
  non-root — *"Cannot initialize device-mapper, running as non-root user"* is the
  last line in the tracked report
- `set -e` kills the script **there**, before step 4 (self-remove) and step 5

Step 5 is `git add` → `git commit` → **`git push origin main`**.

So an **unreviewed auto-push to a protected branch, from a boot script, on every
boot** has been sitting one bug away from firing for three months — and the bug
is the only thing that has prevented it. It would also land in the worst possible
way for this ledger: a push to `main` cancels any in-flight merge-commit E2E
(rule 2a's corollary), so the first symptom would have been a *cancelled* run
that nobody could explain.

It has been superseded since 2026-07-29 by `quillmd-postreboot-proof.service`,
which does the same job properly — no git writes at all, exit code not swallowed,
and it records the **unplanned** hypervisor resets too. The script stays in the
repo; only the cron line is gone.

**The generalisation:** a one-shot `@reboot` job that self-removes on success is
a job that runs forever if it ever fails. Its cleanup must not sit downstream of
its work.

---

## What CLOSING F-pre found — the proof was still lying, in three more places

PR #459 was titled *"the reboot proof reported success on a failed proof,
twice"*. Running it against a real boot found **three more**, and they are all
one defect wearing three hats:

> **Each check asked "is anything wrong?" of a set whose size it never
> established. On an empty set, nothing is wrong.**

1. **§4 passed on a DEAD production stack.** `docker ps -a --filter name=meddoc-pro-`
   returns nothing, the grep filters nothing, the emptiness test passes, and the
   script prints **"🟢 every meddoc-pro container is up"**. Negative-controlled
   against a filter matching nothing: green, exit 0.

   This is the worst of the three, because of *where* it is blind. Both stores
   now **fail closed** — the whole point of the trade this proof exists to
   validate is that a lost boot race **takes the stack down** rather than
   reverting to plaintext. So the one scenario the proof must catch is precisely
   the one it reported as perfect.

2. **§4 could not see an `unhealthy` container — twice over.** `grep -viE
   "healthy|Up [0-9]"` drops `unhealthy` because it *contains* `healthy` as a
   substring; and `Up [0-9]` matches any running container whatever its health
   says. A simulated `postgres` at `Up 13 minutes (unhealthy)` was filtered out
   as fine.

3. **§6 passed on the partial QA stack — and did, on the day.** It tested
   `-eq 0`. Exactly **one** of the six QA services (`gotenberg`) is
   `unless-stopped`; the other five are `restart: "no"` and are *the documented
   side effect the section exists to surface*. The boot log reads **"🟢 QA stack:
   1 container(s) up"** with five down. The section written to report the side
   effect reported success on it.

**Fixed** in `scripts/verify-post-reboot.sh`: the expected service set is now
derived from the compose files, each service resolved to its container and
required `running` + (`healthy` | no healthcheck). Unreadable compose is a
**red**, not a green — "I could not check" must never render as "🟢".

**Pinned** by `scripts/test-verify-post-reboot.sh`, which builds a throwaway repo
with synthetic compose files naming services that have no containers, and
asserts the proof still *can* go red. It passes 7/7 against the fixed script and
fails **7/7** against the pre-fix one — a guard nobody has watched fail is not
known to be a guard.

Two things that fell out of building it, both worth more than the fix:

- **The first draft of the harness silently tested nothing.** Its "dead stack"
  fixture named services `postgres` and `transcribe-md` — which resolve to
  `meddoc-pro-postgres-1` and `meddoc-pro-transcribe-md-1`, the **real, running,
  healthy** containers. The control passed by finding production. A negative
  control whose fixture can collide with the live system is not a control.
- **And then one control passed for the wrong reason.** Against the pre-fix
  script, "overall exit is 1 on a dead stack" went green — but because the temp
  dir was not a git repo, so §6's tree check failed and set the exit code. §4
  was still blind. The harness now `git init`s the fixture so §4 is the only
  thing that can red it. *An assertion that can be satisfied by something other
  than the thing it names is the same bug as the one it is testing for.*

**The same imprecision had already infected this ledger's reasoning.** The F-pre
row's easiest-to-read tell was *"both known reboot side effects are ABSENT — the
QA stack is UP"*. That inference is **unsound**: `meddoc-qa-gotenberg-1` is
`unless-stopped` and survives every boot, so "the QA stack is up" is true after a
reboot too. It reached the right answer that day for a reason that does not
generalise. The sound form is **"the QA stack is FULLY up, 6 of 6"** — a partial
stack reading as a whole one is the identical defect, in prose instead of bash.

---

## What VERIFYING F-pre found — the prompt was the stale artefact, and the fix was on a branch

F-pre was already closed and closed correctly. The next session opened on this,
verbatim:

> *"The host was just rebooted by the previous session, which died with it by
> design."*

Both halves are false, and `uptime -s` said so before anything else ran:

- **The boot was `2026-07-29 15:04:02` — 27 hours earlier, not "just".**
  Every container on the box reads `Up 27 hours`, and `last -x reboot` shows that
  boot `still running`.
- **No session died with it.** Four commits land *after* it — `15:25`, `15:32`,
  `15:36`, `15:42` — and the last one closes F-pre. The session that produced
  them survived the boot by 38 minutes and then simply ended.

Nothing was lost, because the one assertion that mattered is the one built not to
care: §1 compares `ActiveEnterTimestamp` against boot time, so re-running it a day
later re-proves the same +6s. **Rule 2c's corollary paid for itself a second
time** — but note *what* was wrong this round. Last time the ledger carried the
false sentence. This time **the ledger was right** (it says "boot at 15:04:02,
cause not established" and refuses to cite its own log's §4/§6) and the **handoff
prompt** was stale. Rule 2c disciplines what we *write*; it says nothing about
what we are *handed*. Hence rule 2d.

**And the fix was live only by accident of checkout.** `quillmd-postreboot-proof.service`
runs `/usr/local/bin/quillmd-postreboot-proof`, a thin wrapper whose payload line
is `bash /opt/meddoc-pro/scripts/verify-post-reboot.sh` — **the working tree**,
not a snapshot. PR **#465** carried the three-false-greens fix, went green at
`16:10:02Z`, and then sat **open and unmerged for 26 hours** because the session
that opened it ended while its 27-minute E2E was still running. So for that whole
window `origin/main`'s copy still read:

```
unhealthy=$(docker ps -a --filter "name=meddoc-pro-" ... | grep -viE "healthy|Up [0-9]")
...
note "🟢 every meddoc-pro container is up"
```

Had the tree been on `main` at the next boot — a checkout, a rollback, a clone —
**the automatic proof would have gone green on a dead production stack**, in the
exact scenario fail-closed storage creates. The unmerged branch was the only
thing standing between the host and that. This is precisely the failure state
`AGENTS.md`'s branch-cadence rule names: *production running code that `main`
does not have.* A boot unit that executes the working tree makes "merge promptly"
a **safety** property, not bookkeeping.

**Generalisation, and it is the same shape as the three false greens above:** a
green from a checker is a claim about *the checker that ran*, not about the one
in version control. Pin the payload or merge the fix — an unmerged guard guards
one directory.

---

## What A2 found (read before B1 — the same traps apply)

**Six** defects, none visible in a screenshot. (It said "five" until 2026-07-29:
`0b` was found while fixing `0` and appended without moving the count. A ledger
that miscounts its own findings is exactly the thing this file exists to prevent
— so, six.) **`0` is the one to read first, because B1 adds another flag-ON pack
and will meet it again:**

0. **A new flag-ON spec must be added to the DEFAULT project's `testIgnore`,
   not just given its own project.** `rounds-board.spec.ts` got its own project
   and its own image build — both correct — but the `chromium` project still
   collected it. Against the flag-OFF app `/board` 404s by design, so five tests
   failed and the step exited 1.

   The five red tests are not the damage. **Everything downstream reads
   `skipped`**: the flag-ON image is never built and `--project=rounds-board`
   never runs, so the pack that exists to prove the gate never executes. CI
   reports the pack red for the one reason that has nothing to do with it, while
   a local run against the flag-ON image is genuinely green — and the local one
   is the one that gets believed. See rule 2a.

   Now pinned from both sides in `gate-flag-coverage.test.ts`: the flag-ON image
   carries the flag, **and** the flag-OFF run never sees the spec, for every
   project in the config. Negative-controlled: 9ms, naming the cause.

   *Aside, from fixing it:* the first cut of the guard's glob matcher used a
   placeholder character and wrote four literal **NUL bytes** into the source.
   Every test passed — NUL separates as well as a space — but git reclassified
   the file as binary and stopped diffing it, so a guard about reviewability
   would have landed unreviewable. `file <path>` says `data` instead of
   `JavaScript source`; `git diff --stat` says `Bin`. Do not build regexes by
   splitting on a placeholder.

0b. **And then the fixed pack broke a DIFFERENT one.** The Rounds block was
   inserted between "recreate app on the review-doc image" and "run review-doc",
   ending with a step that put the app back on the DEFAULT image "for the
   remaining packs". The app is ONE container, so every recreate replaces the
   last: review-doc ran flag-OFF and all 18 of its tests failed.

   Every symptom pointed away from the cause — **the rounds pack passed**, and
   the pack that went red was one the branch never opened, so it reads as a
   product regression. ~25 minutes of a 55-minute job to find out.

   **A uniform failure across every test in one pack is almost never the
   product. It is the environment.** `gate-project-env.test.ts` now asserts that
   nothing recreates the app between a pack's setup and its `--project=` run.
   There is deliberately **no shared "restore" step** — every pack recreates the
   app on its own image as its last setup step, because a shared restore is just
   a second place for the image to be wrong.

   **B1 adds another flag-ON pack, so it meets 0 and 0b both.** Put its spec in
   `chromium`'s `testIgnore`, and keep its build + recreate + run contiguous,
   ending with its own run — do not add a cleanup step after it.

And the four from the board itself:

1. **The Dockerfile did not declare `ARG NEXT_PUBLIC_SKIN_ROUNDS`**, so
   `--build-arg` was silently discarded ("were not consumed"), the flag never
   inlined, and the image tagged `:rounds` rendered the OLD skin. Now declared,
   and the flag-coverage guard has a `rounds` entry that goes red if the build
   arg is dropped (negative-controlled).
2. **A source-grep guard tripped on my own comment.** The board re-typed the
   imaging conjunction; the fix is `!emAppliesToSpecialty(s)` — and then the
   explanatory comment quoting the banned expression tripped the same grep. Do
   not quote banned strings in comments.
3. **`role="row"` / `role="columnheader"` with no table ancestor** → axe
   `aria-required-parent`, critical. The board is a VISUAL matrix, not tabular
   data; half-applied table semantics are worse than none.
4. **Two contrast failures that only exist on dark**: critical red as small text,
   and the signed card's patient name in `--rounds-signed`. Both now have
   AA-safe variants. **A pulsing opacity animation on TEXT also fails** — axe
   samples mid-cycle, and text at 35% opacity really is unreadable at that
   instant. The pulse moved to a dot. Gate B should sample axe across the
   animation cycle the same way (3 samples, ~550ms apart).

## A2, specifically — what was already wired for you

- `RoundsBoard` takes `BoardLane[]` and nothing else. To put it on a page you
  need a server component that queries the queue, maps rows through
  `toBoardLane`, applies `laneMatchesFilter` + `sortLanes`, and passes the
  result. **The existing whole-queue search and pagination must be carried over,
  restyled — the designs' bans lose to shipped features** (SPEC.md, Screen 1).
- Test ids already in place for the E2E: `rounds-board`, `rounds-board-empty`,
  `rounds-lane-<id>`, `rounds-lane-card-<id>` (with `data-lane-kind` and
  `data-critical`), `rounds-retry-<id>`, `rounds-stage-count-<stageId>`,
  `rounds-board-legend`.
- The board collapses to one column below 1100px and hides the track: five
  columns stop being readable, and the position information degrades to the
  stage kicker, which is honest, rather than to five unreadable slivers. The
  **1024 screenshot** in Gate A will therefore show the collapsed layout — that
  is correct, not a regression.
- ~~Confirm the retry route exists~~ — **DONE, and it found a real defect.**
  `/api/visits/[id]/retry` exists and accepts POST, but it is a **JSON API
  route**. The board's first cut used `<form action=… method="post">`, which
  would have NAVIGATED the browser to a page showing `{"ok":true}` — the button
  appears to work, the board vanishes, and nothing throws. A screenshot of the
  click looks fine. Now a client `fetch` (`retry-button.tsx`), with the
  form-vs-button contract pinned by tests so it cannot come back as a
  "simplification". 409 `STILL_PROCESSING` is surfaced as information, not as an
  error the doctor should retry into a duplicate job.

## Notes for whoever picks this up

- The five stages are **derived** from the ten real statuses in
  `src/lib/rounds/stages.ts`. `unmappedStatuses()` is asserted by a test: add a
  status to the Prisma enum without placing it there and the build fails. That
  guard exists because the failure mode is silent — those visits would simply
  stop appearing on the board, with nothing erroring.
- `--rounds-signed` is grey but a **completed track run draws green**. That is
  deliberate, not an inconsistency: the card is finished business and recedes;
  the line is a successful journey and should read as one across the board.
- E/M has **two** tokens; never fill a button with `--rounds-em` — the lighter
  `--rounds-em-fill` exists so amber clears AA against dark label text.
- Fonts load **unconditionally**, not behind the flag: `next/font` resolves at
  build time, so a conditional import is not a thing that exists.
