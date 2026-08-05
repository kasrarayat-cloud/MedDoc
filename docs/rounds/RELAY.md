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

   **⚠️ THE MERGE-COMMIT EXPECTED SET IS **SIX**, NOT SEVEN — DO NOT READ THE
   MISSING SEVENTH AS A FAILURE.** `a11y.yml` is `pull_request`-only
   (`.github/workflows/a11y.yml:24`), so **`axe-core sweep` does not exist on a
   merge commit** and never will. A PR head therefore carries seven check-runs
   and its merge commit carries six:

   > `test` · `unit tests` · `npm audit` · `dev-dependency advisories` ·
   > `TruffleHog` · `Playwright E2E`

   Counting the absent axe sweep as a missing check is exactly as wrong as not
   noticing a pack that silently `skipped` — both are the same error, an
   expected set that does not match the thing being read. **Cite the six by id,
   and cite the axe run separately from the PR head** (that is where it ran and
   where it passed). Verified on R1: PR #507 head carried 7, merge commit
   `7f5fddeb` carried 6, all green.

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

7. **A GATE'S OWN CHECK IS AN ARTEFACT, AND IT GETS VERIFIED LIKE ONE.**

   B4 closed six clauses. **Every one of them had already been "closed" once**, by
   a check that reported success and *could not have reported anything else*:
   screenshots deleted before anything could upload them, an axe walk parked at a
   blocked step it could not pass, an ownership rule reading a display
   truncation, a gate with no positive control, an invariant guard with no
   fixture behind it, and a parity re-proof running on a build where the skin
   does not exist.

   None of them was carelessness, and none was visible in a passing run. Each was
   the same question asked the wrong way round: *"is anything wrong?"* of a set
   whose size was never established.

   So the standing rule, which costs one sentence per check:

   > **Before citing a check, say what it would have taken for it to fail — and
   > then make it fail.** If you cannot make it fail, you do not have a check,
   > you have a sentence.

   > **COROLLARY — A PROCESS CHECK MUST EXCLUDE ITS OWN COMMAND LINE.**
   > `pgrep -f`, `pkill -f` and friends scan every process's arguments —
   > INCLUDING the shell that is running the check. So `until ! pgrep -f
   > "docker build …"` never exits: the waiter's own `bash -c` line contains the
   > pattern, so the condition it is waiting on is true because it is asking.
   > And `pkill -f "playwright test"` kills the run you just launched, plus
   > itself. **Two instances in the R1 session**, costing a deadlocked wait and
   > a destroyed test run that then read as flake.
   >
   > Match by **PID or process group**, never by your own pattern: capture PIDs
   > first (`ps -eo pid=,comm=,args= | awk '/needle/ && $2 ~ /^(node|chrome)$/'`)
   > and signal those, or wait on a FILE the job writes rather than on the job's
   > own existence. This is the same defect as item F's walker reading
   > PRODUCTION's container logs to classify a QA click, and as the `-maxdepth 6`
   > sweep that sampled and reported an inventory: **an answer about a set whose
   > boundary was never established — here, a boundary that includes the asker.**

   In practice that is: a **positive control** beside every zero, a **mutation**
   watched to redden every new guard, and a **non-vacuity assertion** on any set
   an absence is measured over. All three were used in B4 and all three found
   something. The imaging-trail mutation is the sharpest example — on
   `:rounds-mutant` the NEW test reddened and the PRE-EXISTING one still passed,
   which is not a nice-to-have detail, it is the entire finding.

   *Corollary — `NODE_ENV` IS THE WRONG GATE FOR ANYTHING A TEST MUST REACH,
   and it is the pattern already in this codebase.* The QA stack RUNS a
   production build, so `if (NODE_ENV === 'production') notFound()` makes a
   route 404 exactly where the E2E packs run. Measured: `/dev/rx-warnings`
   returns **404 on QA** against a `/login` control at 200, and no E2E spec
   references any `/dev/` route. **Copying the existing pattern would have
   shipped a door onto nothing that looked like progress** — the tell is that
   the gate's condition is true in the environment you need it false in. Gate
   on a BUILD FLAG the CI image carries and production's compose omits, and
   prove BOTH directions on real builds.

   *Corollary — SUBSTRING ASSERTIONS ARE VACUOUS MORE OFTEN THAN THEY LOOK.*
   C1-c's label/href pairing test asserted
   `label.toLowerCase()).toContain('board')` for the flag-ON case. **The
   flag-OFF label is "Back to dashboard", and 'dashboard' CONTAINS 'board'** —
   so a label reverted on both branches passed cleanly and the flag-ON half
   asserted nothing at all. Reading the test could not show it; mutating the
   value and watching the assertion **fail to notice** is what did. Prefer
   `toBe` over `toContain` whenever the expected value is knowable, and when a
   substring really is the right shape, check that the two candidates are not
   substrings of each other.

   *Corollary, learned the same day:* **a probe can be over-strict and that is
   also a defect.** B4's first `aria-hidden-focus` probe flagged 18 elements in
   the override-modal state — the dialog primitive marking the background while
   it traps focus, i.e. the correct pattern. The cure was not to delete the
   check: it was to narrow it AND **assert the trap in its place**, with a
   non-vacuity guard on how many modal states were seen. Skipping a case and
   asserting nothing where it was is how a state ends up measured by nothing.

   *Corollary — A WAIT IS A CHECK, AND A NON-VACUITY GUARD TURNS AN UNANSWERABLE
   QUESTION INTO AN INFINITE ONE.* Rule 7 says make the check fail. It says
   nothing about what a check should do when it **cannot answer at all**, and
   that gap has now cost two sessions.

   C1-d's merge-commit CI was waited on for **five hours after it had already
   gone green**, by this loop:

   ```bash
   until [ "$(gh run list --commit 46d7ee6c --limit 10 | grep -c 'in_progress\|queued')" -eq 0 ] \
      && [ "$(gh run list --commit 46d7ee6c --limit 10 | wc -l)" -gt 0 ]; do sleep 60; done
   ```

   **`gh run list --commit` takes a FULL 40-CHAR SHA.** Measured across lengths
   7/8/12/20/39/40 the result counts are `0,0,0,0,0,3`: a short SHA is not
   resolved, and it returns an **empty list, exit status 0, and empty stderr** —
   no diagnostic of any kind. So condition 1 was satisfied *vacuously* (nothing
   to match in an empty stream) and condition 2 could never be satisfied at all.

   **The sharp part is that condition 2 is the RIGHT guard, and it is exactly why
   the loop hung.** `wc -l > 0` is a non-vacuity assertion — this rule's own
   prescription — and it did its job: it refused to read an empty set as green.
   But a loop's only vocabulary for "I cannot answer" is *sleep and ask again*,
   so a permanently unanswerable question became a permanent wait. **A check that
   cannot distinguish "not yet" from "never" will wait forever on "never".**

   **Second instance of one class.** The first was `a9a2a8fa` — `page.waitForURL`
   defaults to `waitUntil:'load'`, and the login form is a React 19 server action
   that resolves to a SOFT navigation, so no `load` event is ever fired. It sat
   its full 20s while the login had **already succeeded**, and read as "login
   refused". Both times the awaited signal was **structurally unreachable**,
   silence was read as *not yet*, and the underlying event had in fact already
   passed. Both times the diagnosis was inverted: the thing being waited on was
   blamed, and the waiter was trusted.

   So, beside the positive control and the mutation: **every wait gets a
   deadline and a distinct outcome on it.** Not a longer timeout — a *third*
   answer. `done` / `still running` / **`cannot tell, and here is the raw
   output`**.

   And prefer the query that **fails loudly instead of emptily**. Measured,
   both directions:

   | query | short SHA | SHA that does not resolve |
   |---|---|---|
   | `gh run list --commit <sha>` | `[]`, **exit 0**, empty stderr | `[]`, **exit 0**, empty stderr |
   | `gh api …/commits/<sha>/check-runs` | `total_count: 6`, exit 0 | `HTTP 422 · No commit found for SHA` , **exit 1** |

   That is the whole difference, and it is not about SHA lengths. One of these
   answers "nothing matched" and "I could not look" with the **same bytes and the
   same exit code**; the other cannot be made to confuse them. When a check
   reports an absence, ask which of the two it just told you.

   *Corollary — A FAILURE MESSAGE THAT CANNOT BE DIAGNOSED IS ITSELF A DEFECT,
   AND THE FIRST SUSPECT FOR AN INTERMITTENT ONE IS YOUR OWN PROCESS.*

   C1-e spent **three rebuild cycles** on one `color-contrast` hit that reported
   four selectors and no colours, then **four wrong hypotheses** on an
   intermittent auth failure. Both were the same mistake: reasoning about a
   system that was willing to be measured.

   The contrast one broke the moment the harness printed what it already knew.
   `rounds-axe.ts` was collecting axe's `targets` and discarding its `data`, so
   the `fgColor`/`bgColor`/`contrastRatio` axe computes for free never reached
   the failure message. With the pair printed, the answer was that **none of the
   three candidate rules was the cause** — the values were not in the palette at
   all, they were tokens COMPOSITED mid-animation. **Before theorising about
   which rule decides a pixel, make the failure say what it measured.**

   The intermittent one broke only after checking what *else* was running: two
   of that session's own Playwright invocations were racing each other against
   one QA container. Everything before that — accumulated users, animation
   timing on auth, a cold container — was a theory about the product, and the
   product was fine. **An intermittent failure is a claim about a system
   boundary nobody has drawn yet.** Draw it: what else touches this container,
   this port, this database, right now? Ask that BEFORE the second hypothesis,
   not after the fourth.

   And say which it was in the ledger. "The pack flakes" would have sent the
   next session hunting a defect that does not exist — the inverse of rule 2c's
   harm and just as expensive.

   *Corollary — A CLOSED LOOP CANNOT DETECT ITS OWN BLIND SPOT, and it reports
   the fact in green.*

   `gate-rounds-bridge` carried a debt entry saying `--color-linear-sage` had
   **4** foreground sites, and an assertion whose whole job was to catch that
   number going stale. C1-f forked two of them and wrote **2**. The tree held
   **3**.

   The regex is the small half: it required a value to START with `var(`, so
   `color: checked ? 'var(--color-linear-sage)' : …` was never in its universe
   — and neither was `var(--a, #fallback)`, which is the shape flag-safety
   guidance RECOMMENDS, so the blind spot was set to **grow**.

   The large half is that **the staleness assertion recomputed the count with
   the SAME regex.** It confirmed the number the matcher would produce, not the
   number in the file. Every other foreground assertion asks that same matcher,
   so they all agreed with each other and the guard was green about a figure it
   had generated itself.

   So, beside the positive control and the mutation: **a matcher's answers get
   pinned by fixtures the matcher did not produce.** `matcher shapes` states
   PLAIN / TERNARY / FALLBACK / COLOR-MIX / skin-fork by hand, with negative
   controls (`backgroundColor` ends in `color` — the substring trap, third
   sighting). A regression then reddens THERE, naming the shape that stopped
   being seen, instead of quietly shrinking what the guard covers.

   *Found by reading an abandoned local WIP branch from an earlier session that
   had attempted this item and never pushed. Its diagnosis was right and would
   have died with the branch — so: **before starting an item, list local
   branches.** `git branch -vv` costs nothing and this one held a correct
   finding about work that had already merged.*

   *Corollary — A REQUIRED GATE CAN VANISH FROM THE CHECK LIST INSTEAD OF GOING
   RED, and every question you would think to ask answers "fine".*

   A cosmetic step rename put `C1-d/e/f: auth` into `e2e.yml`. A colon-space in
   an unquoted YAML scalar starts a mapping, so the file stopped parsing.
   GitHub then listed the run by **filename** rather than its `name:`, failed it
   before any job started with no log to fetch, and **never created the
   `Playwright E2E` check-run at all.** The PR showed **six checks, all green.**
   *Is anything pending?* No. *Did they pass?* Yes.

   Rule 2a's corollary already says a `cancelled` run is absence of evidence.
   This is worse, because nothing looks absent: the gate simply left the set
   being asked about. **Enumerate the workflow RUNS for the ref and assert the
   expected SET, never "are any checks pending?"** — the same move a `clone
   --mirror` makes for `refs/pull/*`, where a plain clone looks clean either
   way.

   `gate-workflows-parse` now parses every workflow file in 13ms and names the
   file and line. It **fails loudly if the YAML parser itself is unavailable**
   rather than skipping, because a guard that silently stops running is the
   defect it exists to catch.

7c. **INVESTIGATE, DO NOT RESTORE — any baseline mismatch touching a
   non-smoke account.** A smoke run compares counts before and after. When the
   after does not match, the reflex is to "restore the baseline"; on a LIVE
   production database that reflex deletes real clinical work.

   *Cost that produced this rule (avoided, not paid):* R3 batch 1's prod
   verification baselined `transcribe_visits` at 23 and read **24** afterwards,
   with the smoke cleaner reporting `visits=0` deleted. The extra row belonged
   to `kasra.rayat@gmail.com` and was created at 07:12 **during the session** —
   ordinary clinical activity by a real doctor. A "restore to 23" would have
   destroyed a live note, and the cleaner was right to leave it: it scopes every
   delete to the fixture's own user and practice.

   So: a mismatch is a QUESTION, and the first move is `select … join users` to
   learn WHOSE row it is. Only rows owned by the synthetic fixture are ever
   candidates for removal, and the cleaner already enforces that — the danger is
   a human reaching past it.

7d. **A SHARED COMPONENT MUST ACCEPT EVERY CONTEXT ITS PREDECESSORS CARRIED.**
   Diff the callers' dropped props and params BEFORE the replacement lands, and
   assert both directions in the migration test — carries when given, omits when
   there is none. See `AGENTS.md` § "Shared components — diff the callers BEFORE
   you replace them" for the two R4 reference implementations: context as a prop
   (`RoundsNewVisitCta.patientId`) and treatment on the component
   (`rx-tab.tsx`'s own host).

   *Cost that produced this:* R4 was an entire round spent on two defects that
   were the same mistake in two shapes, both from consolidations that were
   otherwise right, and neither visible to the census — a class sweep cannot see
   a missing query param or an unhosted third mount.

7e. **A THIRD MID-ROUND HIGH ADVISORY RAISES THE POSTURE QUESTION.** Two were
   absorbed one at a time (`brace-expansion` 2026-08-03, `fast-uri` the same
   day) — both transitive, both published upstream between one green run and the
   next, both fixed rather than waived. That is a coincidence. A third is a
   pattern, and the response is to raise pinning or an audit schedule with the
   owner, not to keep absorbing them mid-round.

7f. **THE FONT ESCALATION IS SPENT.** CI's Turbopack build failed three times on
   one `bricolage_grotesque` Google-font fetch inside its sandbox; the evidence
   that it was environmental (no font/layout/config file in the diff, identical
   build green locally) bought exactly ONE re-run, and that re-run passed.
   **Recurrence means vendoring Bricolage Grotesque, not retrying harder.**

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
| **B1** | Screen 2 — the stage | ✅ **DONE, MERGED** | pipeline strip from the same mapping; NOW REVIEWING; padlocked Signed node with correct **N**; sheet is the existing paper component restyled; identity header; next-up peek; chat drawer | **Components + units merged**, PR **#466** squashed to **`f9950c37`** · **merge-commit CI on `main@f9950c37`: `CI` run `30576262297` · `e2e` run `30576262319` · `secrets-scan` run `30576262364`, all success** · **101 new tests, 2847 pass, tsc clean.** ✅ **THE GATE IS NOW MET.** Built: `pipeline-strip.tsx`, `stage-identity.tsx`, `chat-drawer.tsx`, `stage.tsx`, `lib/rounds/stage-data.ts`, `lib/sign-gates.ts`, `lib/patient-display.ts`. **Outstanding: the route wiring** — `visits/[id]/page.tsx` + `visit-ready-view.tsx` still render the old skin, so *"the sheet IS the existing paper component restyled"* is **unproven**: the sheet is a slot carrying `.rounds-paper`, and nothing has yet passed `ReviewDocumentView` into it. Also outstanding: the flag-ON E2E pack, its `chromium` `testIgnore` entry, its contiguous `e2e.yml` block, and the two gate-guard entries. **`lib/sign-gates.ts` IS the item**, not the layout. "N blockers before Signed" is a promise about what `POST /sign` will do, so N is derived once and both readers call it. Reading the route rather than the spec corrected three things: **`emStale` is NOT a blocker** (the route re-scores and carries on; it refuses only if the re-score fails); **attestation is not server-enforced at all** (no such field in the sign body schema — counted, but flagged `serverEnforced:false` so anyone reconciling the strip against a 422 is told which term the server cannot see); and **the route's E/M refusal is NOT conditioned on specialty**. That last one opens a gap the invariant forbids closing the obvious way: imaging gets no E/M gate (*absent, not hidden*), so an imaging visit holding an unacknowledged E/M change would show **no gate while the server returns 400**. Five imaging visits acquired office E/M state in prod and sat two days, so the gap is **named** (`emArtifact`) rather than rendered as a clean zero. **B2 owns the open half** and the code says so where it is decided — SPEC `:101–104` reads as +1 on every applicable visit, `:143–146` as a confirm step that always exists; the type carries *existence* and *count* separately so B2 can settle it without a redesign. Traps avoided, each already paid for once: **`completedStageCount('READY')` is 5**, which would draw the Ready node DONE on the screen the doctor is standing on (the strip uses `n < current.n`, matching `runTo`/`cardColumn`); no animated **text** (motion on a dot — A2 defect 4); no borrowed ARIA (A2 defect 3); its **own** breakpoint, since the board grid's collapse hides the track and would delete the strip at 1024. **Guards watched to fail:** six mutants — empty gate set, the one switch defeated, override coverage ignored, `emStale` counted, `completedStageCount` semantics, a constant blocker label — killed by 1–22 tests each, sources restored byte-identical. **A self-review before merge caught three things CI cannot see:** the chat drawer's `onBeforeClose` was a **no-op that read as handled** (a private ref nothing ever assigned, so a post-close scroll could never run while the code looked solved) — now an honest `onChatBeforeClose` prop; the strip claimed a **`<nav>` landmark containing no links**, now `role="group"`; and a dead ref. *axe does not flag a landmark that lies, and a handler that never fires passes every test that does not assert it fired.*  **CLOSED 2026-07-31 — the route wiring merged.** PR **#470** squashed to **`6f421301`** · **merge-commit CI on `main@6f421301`: `CI` run `30594495440` · `e2e` run `30594495441` · `secrets-scan` run `30594495474`, all six checks success** — that is rule 2a's citation, on the merge commit, not the PR head. **2848 → 2878 (+30), tsc clean.** The gate's six claims are all now proven on a route: the strip, NOW REVIEWING, the padlocked Signed node carrying the same N as the rail, the sheet as the EXISTING paper component, the identity header, the next-up peek and the chat drawer. **The seam is the item, not the layout:** the gate set is computed SERVER-side in `VisitBody`, because two of `signGates`' three inputs are only correct there — the raw specialty ID (`findSpecialty('Ultrasound').id` is `'unspecified'` with no throw, the substitution that once made every ultrasound visit persist an office E/M level) and the raw `emPendingChange` (already coerced to a display pair by then, and the coercion fails CLOSED, so feeding it back invents a blocker on every visit with a pending change). Computing on the server means the wrong value is not within reach of the right call. **ONE note renderer:** `paper` is hoisted to a const and passed through the sheet slot as the SAME element — never keyed, never conditionally mounted, because `ReviewDocumentView` holds the in-session E/M confirm in local state. **Three defects found and fixed inside B1's own work, none of them by CI:** (1) an adversarial pass (5 lenses, 16 raised, 14 refuted under challenge) confirmed a deferred scroll that could STRAND — `handleChatScrollTo` deferred whenever the skin was active, with no check the drawer was open, and `ChatEditorPanel.send`'s continuation is not cancelled on unmount, so a reply landing after Escape recorded a target nothing would flush; it then fired on the NEXT unrelated close. Both halves user-visible: an announced navigation that silently did not happen, and a later unexplained scroll mid-review. The drawer now reports `onOpenChange` and the view defers only while it is actually over the sheet. (2) `RoundsStageIdentity` formatted a timestamp in the render body — `toLocale*` — and B1 is what first put that component through SSR, so prod's UTC container and the doctor's browser disagreed: a React hydration error every load. `<LocalTime>` already existed for exactly this and was not reached for. **Worth recording how it nearly shipped: the E2E deliberately skipped that assertion as 'flaky by timezone' — which was true, and was the symptom.** (3) `RoundsStage` rendered its own `<main>` inside `AppFrame`'s, i.e. two main landmarks, introduced by the wiring, invisible in a screenshot and invisible in CI because `a11y.spec.ts` runs flag-OFF. **And A2 defect 2 caught me again:** an explanatory comment quoting the tag the read-only guard greps for made `indexOf` match the comment — caught by the very guard #468 hardened three hours earlier. **The E2E pack's first version asserted the wrong property and CI was right to reject it:** `not.toBeInViewport()` measures geometric intersection, NOT occlusion — the drawer covers the gate while the gate stays inside the viewport rect, so it read `viewport ratio 1` and failed a correct implementation. A scroll-position assertion was no better (the seeded note fits on screen, so `scrollIntoView` is a no-op). The contract is an ORDER, so it is asserted as one: instrument `scrollIntoView`, record whether the drawer was in the DOM at call time, require zero gate-scrolls before the close and exactly one after. **Proven both ways on real flag-ON builds** — 10/10 green against a freshly built `:rounds` image with all four flags confirmed INLINED by grepping the built chunks from inside the image (0 surviving runtime reads against a positive control of 54 chunks), and RED against a separately-tagged `:rounds-mutant` with the deferral removed, dying at exactly the intended line. Source restored byte-identical; mutant image destroyed. **Left to B4 deliberately:** axe on the stage including the landmark change, screenshots, the full fixture matrix, PDF/Word parity, and a flag-ON a11y run. |
| **B2** | Screen 3 — the gates | ✅ **DONE, MERGED** | full-screen sequential over EXISTING logic; only applicable gates exist; `> OVERRIDE` typed input unchanged; E/M only when `emApplies`; attestation; **sign-block E2Es pass with semantics unchanged** | PR **#473** squashed to **`08162191`** · **merge-commit CI on `main@08162191`: `CI` run `30599395371` · `e2e` run `30599395352` · `secrets-scan` run `30599395360`, all seven checks success.** **2848 → 2924 units, tsc clean.** ⚠️ **The e2e run was checked STEP BY STEP, not just for a green tick** — all eight pack steps EXECUTED (`chromium`, `rounds-board`, `rounds-stage`, `rounds-gates`, `review-doc`, `doc-preview`, `visit-doc`, `phi-reject + rx-safety`), none `skipped`. That is what settles "sign-block E2Es pass with semantics unchanged": each runs on its own unchanged image, and A2 defect 0 is precisely a green gate whose downstream packs never ran. **THE E/M QUESTION B1 LEFT OPEN IS SETTLED: the gate EXISTS on every applicable visit and COUNTS only when the server will refuse.** Three readings agree — SPEC's own N says "applicable UNRESOLVED gates: critical Rx COUNT + …", and *count* plainly is not +1-always for Rx, so it is not for E/M either; SPEC's Gate 2 paragraph establishes the gate's EXISTENCE, which the type already carried separately from its count; and the route decides it — with no pending record the E/M branch is skipped and the sign SUCCEEDS, so a +1 would be a blocker the server does not have. ⚠️ **The ruling is invisible to every pre-existing assertion** (the primary-care fixture already carries a pending change; imaging has no E/M gate), so a silent switch to "+1 always" would redden nothing — hence five new cases that can only pass under it, mutation-proven to redden 7 tests. **Two corrections to the spec's own wording, established by reading the code:** (a) there is **no typed `> OVERRIDE` token anywhere in `src`** — the override is a free-text reason textarea with min/max bounds, and the `> ` prompt exists only in unbuilt mockups. "Unchanged" therefore means restyle, skin-only; adding a literal typed token would be a NEW gate condition and would red `24-rx-clinical-safety`. (b) "Sign & lock" is a step HEADING, not a rename — actions keep their names end-to-end. **Architecture: portals, not remounting.** `RxTab`'s `overriddenIds` and `ReviewDocumentView`'s `emConfirmed` are lazily-seeded local state with no `router.refresh()` behind them, so a sequential flow that re-mounted gates would silently un-clear one — the doctor sent back to re-justify a warning already in `rx_warning_overrides`, and N ticking back up. Stepping back is the NORMAL interaction here, so that is not an edge case. `gateHost` relocates DOM via `createPortal` while the subtree keeps its React position. **Landed so far:** the ruling, `applyGateOverlay` (a COUNT, so partial Rx credit is expressible; `undefined` ≠ 0), `firstOpenStep`, `RxTab.onUnresolvedChange`, the portal seam, `gate-flow.tsx` (renders NO clinical control — steps are `gates.map`, guarded by a source test that it names no specialty), tokens CSS, and 35 tests. **2913 pass, tsc clean.** **THE PORTAL WAS THE BUG, and the E2E is what found it.** `createPortal(node, host)` and a bare `node` are different element TYPES to React, so every time a step deactivated and its host vanished the gate flipped back to inline and the subtree UNMOUNTED AND REMOUNTED — resetting `RxTab.overriddenIds` to the stale server prop. Step forward, step back, and the doctor is asked to re-justify a warning already in `rx_warning_overrides`, with N ticking back up: exactly the defect the portal was chosen to prevent, reintroduced by the portal itself. Changing a portal's container remounts for the same reason, so "one host per step" could not have fixed it. **The seam is now DOM ADOPTION** — the gate renders into a stable `[data-gate-slot]` wrapper in the paper and STAYS there; the flow borrows the node into the active step and restores it on cleanup. Moving a DOM node does not touch React's tree, so state survives because nothing unmounted. The restore is not optional: React removes that wrapper from its ORIGINAL parent when the paper unmounts, and a node adopted elsewhere at that moment throws. **Before that, the same pack caught REACT #185** — an infinite render loop from `ref={hostRef(id)}` returning a fresh arrow every render, so React detached (`ref ← null`) and reattached (`ref ← element`) forever; the "bail when unchanged" guard could not help because the value genuinely alternates. Pinned by a unit guard whose negative control holds the exact naive factory that shipped. **⚠️ A LESSON CORRECTED: all 8 tests failed at the same line, which A2 says is "almost never the product, it is the environment". Here it WAS the product.** The sound form is narrower — a uniform failure means ONE COMMON CAUSE, usually the environment but identically produced by a mount-time crash. Checking the built image for the component and its CSS is what ruled the environment out before any code was read. **One deliberate behaviour change, stated rather than absorbed:** `rounds-stage`'s last test asserted the rail NAVIGATES and opens no dialog; B2 makes it open Screen 3, which IS a dialog. Rewritten to pin the invariant that survives and matters more — exactly ONE control in the document can start a signature, and the flow adds none: it adopts the existing bar, so the count stays 1 open, shut or reopened. **Both CI guards watched to FAIL:** removing the chromium `testIgnore` entry reddens `rounds-gates — its specs are ignored by chromium`; a foreign recreate between a pack's recreate and its run reddens `rounds-stage — the recreate before it is ITS recreate`. **Proven locally on real flag-ON builds before pushing:** `rounds-gates` 8/8 and `rounds-stage` 10/10 against a freshly built `:rounds` image on the isolated QA stack. **Left to B3/B4:** the signed branch and deck-advance; axe across the flow, screenshots, the fixture matrix, PDF/Word parity, and a flag-ON a11y run. |
| **B3** | Screen 4 — signed + deck-advance | ✅ **DONE, MERGED** | strip fully checked; lock banner; safety trail shows **only what applied**; addendum footer; deck advances to next in-review | PR **#476** squashed to **`3f9d3d87`** · **merge-commit CI on `main@3f9d3d87`: `CI` run `30607287556` · `e2e` run `30607287558` · `secrets-scan` run `30607287569`, all six checks success.** ⚠️ **The e2e run was read STEP BY STEP**, not for a green tick: `rounds-signed` is step 24, `success`, **`11 passed (46.6s)`** — eleven named tests, zero skipped. Not a formality here: this is the pack where a broken seeder skipped all 11 and the run still exited 0. **2924 → 2949 units, tsc clean.** ⚠️ **THIS ROW WAS WRITTEN FOUR ITEMS LATE.** B3 merged, B4's two PRs merged on top of it, and the ledger still read `⬜ TODO` with evidence `—` the whole time — because the session that merged it was killed mid-relay and the next one inherited a ledger that disagreed with the tree. The CI existed and was green on the day; **the citation is the artefact, not the run**, and rule 2a is unsatisfied until it is written down. **THE SAFETY TRAIL IS AN HONESTY PROBLEM, NOT A LAYOUT ONE:** "only what applied" cannot be inferred from *"the visit is signed, so its gates must have been cleared"* — that reasoning puts a green tick on a step nothing recorded. Each card is backed by a COLUMN: the Rx card by real `RxWarningOverride` rows (validated reason, signer, timestamp, correlated against the visit's persisted warnings), the E/M card by `emPendingChange.acknowledgedAt`, stamped by the winning READY→SIGNED transition. **ATTESTATION IS PARKED, AND THE PARK IS THE FINDING:** nothing persists it — no field in the sign body schema, no column, no audit action. Its only signal is a `useState(false)` that dies with the page and is never transmitted; `signGates` already marks it `serverEnforced:false`. A tick would re-assert on every reload a fact nothing recorded, and would **contradict Screen 3**, which tells the doctor the server does not check it. Two cards, not three-with-one-greyed — **a greyed card is still a claim.** *Un-park trigger: an `attestedAt` in the sign body plus a column* — a schema and route change, its own item, not a reskin's. **THE DECK ADVANCE READS THE QUEUE HEAD, NOT `nextVisitId`:** a signed visit has LEFT the queue, so both peek neighbours are null by construction — deliberately, since claiming a place in a list it has left would put a signed note back in the review count. A Continue wired to `nextVisitId` would render on **0%** of signed visits and read as a wiring bug. Empty queue ⇒ **nothing renders** — not a disabled button and not "all done for today", because the queue is a 200-row window and a still-to-review visit outside it looks identical. **Two defects found on the way, each shipped as its own commit:** (1) the strip drew *"still ready"* and *"signed"* on the same track — `nodeStates` asked the status column alone and `stageOf('READY')` is 5, so a `READY`+`signedAt` row drew node 5 as CURRENT, with NOW REVIEWING, beside a ✓ Signed node; the board rendered it correctly and the strip did not. (2) **A broken seeder skipped 11 tests and the run exited 0** — A2 defect 0's shape in a new place. ⚠️ *The first guard asked the wrong question:* it probed the psql **channel** and passed while the pack skipped all 11 anyway. The channel was fine; the **INSERT** was rejected. **"Can I reach the database" and "did this seed succeed" are different questions.** Proven by re-breaking the seeder exactly as it broke: exit 1 with the seed named, where before it was exit 0 and eleven green ticks. ⚠️ **Wider exposure, recorded and NOT fixed here: 43 specs use the same `test.skip(!seeded, …)` pattern** and can each go silently green on a broken fixture. Its own item. **⚠️ TWO SPEC DEVIATIONS ON THE LOCK BANNER, neither amended when it was made.** SPEC `:161–162` asks for a **green** banner carrying an **attestation line**; the product rendered neither. The attestation omission is RIGHT and is the park above — the tests actively assert it (`not.toMatch(/attest/i)`). **The colour was not:** the banner was styled from `--rounds-signed` grey, the token for a signed CARD, while SPEC `:4–6` says a component that disagrees with the spec is the bug. Found by B4's verification after B3 had closed, so it landed as its own commit rather than by reopening this row: PR **#479** squashed to **`7a496c6a`** · **merge-commit CI on `main@7a496c6a`: `CI` run `30620743944` · `e2e` run `30620743900` · `secrets-scan` run `30620743923`, all six checks success**, with `rounds-a11y` (step 26) and `rounds-signed` (step 24) both EXECUTED. The banner is now `--rounds-ready`, and its title takes a **new** `--rounds-ready-text` (#6ee7a8) — `--rounds-ready` itself is #187a4e and lands near 2.3:1 on the stage, so using it as text would have traded a spec deviation for an AA failure. **That is the FOURTH instance of one lesson** in this palette (`--rounds-em`/`-em-fill`, `--rounds-accent`/`-accent-text`, `--rounds-signed`/`-signed-text`, now this): *if a token names a STATE or a FILL, assume it needs a text variant BEFORE it is used as one.* Pinned by `gate-signed-banner-green.test.ts`, mutation-proven three ways — the grey restored, the fill green used as text, and the **selector renamed**, that last caught by the extractor's own positive control, without which a rename would silently make every absence assertion in the file vacuous. ⚠️ **A screenshot would not have caught this and did not:** Gate B's 21 captures include the signed screen at both widths and were uploaded for a human to look at, not diffed. *A capture is evidence for a reader, never a check.* |
| **B4** | Gate B verification | ✅ **DONE, MERGED** | axe zero serious/critical on stage + all gates + signed · chromium E2E incl. sign-block · **fixture matrix both specialty classes** (imaging: no E/M gate, no strip blocker, anywhere) · **PDF/Word parity re-proven at 1440** · screenshots · merge on green | Two PRs. **#477** squashed to **`b12a8fde`** · merge-commit CI `CI` run `30611249714` · `e2e` run `30611249741` · `secrets-scan` run `30611249722`, all six success — and the e2e read step by step: **all ten pack steps EXECUTED**, `rounds-a11y` at step 26, none `skipped`. **#478** squashed to **`51e9440c`** · **merge-commit CI on `main@51e9440c`: `CI` run `30617805287` · `e2e` run `30617805479` · `secrets-scan` run `30617805187`, all seven checks success** — read step by step, **all eleven pack steps EXECUTED**, none `skipped`. **2949 → 2957 units, tsc clean. Flag stays OFF.** **#477 — AXE, FOR THE FIRST TIME ON A ROUNDS SURFACE.** `a11y.yml` builds with plain `npm run build` and three `NEXT_PUBLIC_*` vars, none of them the skin flag, so the board, the stage, the flow and the signed screen had never been measured — including the `<main>` landmark change B1 made *because* `AppFrame` already owns one. Three real contrast defects: `.qm-rounds-strip-now` (~2.7:1 — **A2 defect 4's own element**, failing on colour this time rather than a pulsing opacity), `.qm-rounds-queue-open` (same token), `.qm-rounds-gateflow-step-label[data-state=done]` (~3.7:1). Also: two assertions that **passed against a build with the feature deleted** (every imaging fixture hard-nulls `emPendingChange`, the only source of `emArtifact`), and the board's imaging split, which had **zero** E2E coverage — the seam that once made every ultrasound visit persist an office E/M level. **#478 — SIX DEFECTS, AND THEY ARE ALL ONE DEFECT.** Every remaining Gate B clause was being closed by a check that reported success **without being able to report anything else** — the project's named recurring failure, four more times. (1) **The screenshots could never survive the run that produced them.** They were written into `test-results/`, and playwright's runner `fs.rm`s every project's `outputDir` in global setup — FOUR further `playwright test` invocations run after the a11y pack, so the first deleted them; and the only step uploading that directory was `if: failure()`. **On a GREEN run — the only kind rule 2a lets the ledger cite — zero screenshots left the runner.** The always-uploaded HTML report cannot substitute: `page.screenshot({path})` registers no `testInfo` attachment. Now `rounds-shots/`, outside every `outputDir`, uploaded `if: always()` with `if-no-files-found: error` so an empty upload cannot read as success. **PROVEN ON THE MERGE-COMMIT RUN, which is the only place it counts: artifact `rounds-shots`, 2 329 922 bytes, on `main@51e9440c`'s GREEN e2e run `30617805479`** — step 27, `success`. Before the fix that artifact list held `playwright-report` and nothing else, on every green run this project has ever had. (2) **Gate 3 was never measured, by axe or by a camera.** The walk stopped at Gate 2 and navigated away — and not by choice: on the default fixture the E/M step BLOCKS and `rounds-gate-next` is disabled, so it *could not advance*. Gate 3 carries the only form control the flow authors itself, a bare `<input type="checkbox">`. Reached now via `emPending:false`, the same door `rounds-gates.spec.ts` uses. (3) **Ownership was decided on truncated evidence, by a rule blind to the element it most needed to see.** `targets` was `.slice(0, 8)` — a DISPLAY truncation that was also the SOLE input to the ownership decision, so a Rounds-owned node past the 8th was reclassified as inherited and vanished from the gate AND from the inherited log (which filters the already-truncated array). And ownership was a regex over axe's selector string — axe names an element by `#id` or `tag[attr]` when unique and **never climbs to an ancestor class**, so `qm-rounds-*` is absent for precisely the elements the skin renders itself. Now decided IN THE DOM: **the nearest ancestor-or-self carrying ANY class decides.** Not `closest('[data-testid^="rounds-"]')` — the paper renders INSIDE `rounds-stage`, so that would claim every inherited violation on the screen and quietly convert this into a gate over other people's code. (4) **Nothing proved the harness could fail.** A clean run and a run whose filter classifies everything as inherited emit the identical `violations: []`. A positive control now plants a serious violation and requires it caught — **twice**: once on a classed Rounds element, once on a **classless** one inside a Rounds container, which is the attestation checkbox's exact shape. `aria-hidden-focus` is adjudicated by PROBE rather than by prose, because a hand adjudication is only true of the day it was made and Gate 3 was not among the states it covered. ⚠️ **The first probe was wrong and is worth recording:** it flagged 18 elements in the override-modal state — the dialog primitive marking the background while it traps focus, i.e. the CORRECT pattern. Narrowed to non-modal states, and the skipped case **replaced** by asserting the trap itself with a non-vacuity guard on how many modal states were seen — skipping a check and asserting nothing in its place is how a state ends up measured by nothing at all. (5) **The imaging E/M guard on the safety trail had no fixture behind it.** `emNotApplicable ? null : …` (`page.tsx:868`) could be deleted with the whole suite green: every imaging seed hard-nulls `emPendingChange`, so guarded and unguarded both evaluate to null, and the one imaging Screen 4 test scoped its prose check to `rounds-signed-lock` — while the trail is a **sibling** of that section. `POST /sign` is not specialty-conditioned, so the state is reachable; five imaging visits acquired office E/M state in prod and sat two days. It would have printed *"Documentation level change confirmed"* on a signed ultrasound report. **PROVEN, NOT ARGUED:** on a separately-tagged `:rounds-mutant` with the guard removed, **only the new companion reddens** (`toHaveCount(0)` receiving 1) while the pre-existing imaging test still **PASSES** — which IS the finding. Source restored byte-identical, mutant image destroyed. Plus the in-paper E/M surface (six controls) asserted ABSENT on imaging and PRESENT on primary care, flag-ON: that stack was covered only by `review-document.spec.ts`, on an image without the skin flag, and the flow **adopts** those nodes out of the paper, so the flag-ON composition is not the flag-OFF one. (6) **Parity was "re-proven" on builds where the skin does not exist.** The evidence offered was the `review-doc` and `visit-doc` packs — both built WITHOUT `NEXT_PUBLIC_SKIN_ROUNDS`, i.e. the same proof that existed before Rounds was written. And **no Rounds pack had ever SIGNED**: `rounds-signed` seeds `signed: true` into the database, so `POST /sign`, the export path and the artifacts had never been exercised with the skin on, at any width. Now at **1440**, on the flag-ON image: sign through the flow, download both formats, assert every section the doctor read on the paper is in the bytes they receive — markers derived from the **fixture** (`IMAGING_NOTE_SOURCE`), never a second hand-written copy that could drift into agreeing with itself. Mutation-proven both ways. **A comment was deleted for being FALSE:** `rounds-stage.spec.ts` claimed its blocker-count assertion would catch an image missing `NEXT_PUBLIC_ULTRASOUND_SPECIALTY`. It would not — B2's ruling makes a quiet E/M gate contribute `unresolved: 0`, so the count reads 1 either way. *A false claim about what a test would catch is worse than no claim: it is the reason the next reader stops looking.* **⚠️ ADJUDICATION, RECORDED BECAUSE IT CHANGES A WRITTEN CLAUSE:** SPEC `:191` scopes axe **by surface** ("on stage + all gates + signed"); the pack asserts zero serious/critical **by element ownership**, reporting inherited ones with selectors. The narrowing is right — a reskin has no business silently rewriting the components it composes, and those violations are present flag-OFF too — but it is *not* what the spec says, and a future reader citing "Gate B axe green" will read the sentence, not the filter. **The inherited inventory, so the follow-up starts from a list rather than a rediscovery:** `.qm-lin-rx-row` (nested-interactive), `.qm-warn-override-btn`, `.qm-lin-rx-rail-group-n`, `.cell > .l`, `.qm-ux-doc-disclosure > span`, `.qm-lin-rx-pane-count`, `#override-reason-help`. **⚠️ KNOWN LIMIT, NAMED RATHER THAN CLOSED:** the `:rounds` image omits `NEXT_PUBLIC_VISIT_DOC_PAGE` and `NEXT_PUBLIC_DOC_PREVIEW`, **both of which production sets true**. Changing the image's flag set would alter what every Rounds pack renders and is not this item's to do. **C2 owns "exports match preview 1:1"; this is its inheritance.** Final: stage **12** · gates **10** · signed **12** · a11y **2** · **21 screenshots** including both attestation widths, on a freshly built flag-ON image with all six flags confirmed **INLINED** by grepping the shipped chunks (0 surviving runtime reads against a positive control of 54). |
| **C1** | Auth / settings / templates / error-empty-loading | ✅ **DONE, MERGED — C1-a · C1-b · C1-c · C1-c2 · C1-d · C1-e · C1-f · C1-g** | all to tokens; copy register: plain verbs, sentence case, actions keep their names end-to-end | **C1-a MERGED:** PR **#482** squashed to **`d9418398`** · **merge-commit CI on `main@d9418398`: `CI` run `30645213292` · `e2e` run `30645213287` · `secrets-scan` run `30645213323`, all six checks success** · e2e read step by step, **10 `Run E2E` pack steps EXECUTED, 0 skipped**, plus the screenshots upload (`rounds-shots`, 2 095 120 bytes). **This closes B4's named carry-forward.** The `:rounds` image now builds production's feature-flag set. **The delta was computed, not guessed:** prod's `args:` block carries 13 entries, the image carried 6, and two of the seven missing are the URLs, which differ per environment by design. The four feature flags added: `SETTINGS_SIMPLE_ROW`, `VISIT_DOC_PAGE`, `DOC_PREVIEW`, `TEMPLATE_NATIVE_DOCX`. **THREE CHECKS, BECAUSE "0 SURVIVING RUNTIME READS" ANSWERS A NARROWER QUESTION THAN IT LOOKS LIKE.** (1) all ten flags INLINED — 0 surviving reads against a positive control of 54 chunks, and no `were not consumed` warning; (2) ⚠️ **inlined as `true`, not merely inlined** — and the chunk grep *structurally cannot* answer that, because minification constant-folds `"true"==="true"` away. Probed behaviourally instead: a visit page renders `visit-document-loading`, a node that exists **only** inside `VisitDocumentSurface`, which mounts only when `docPage` is true; (3) all five Rounds packs green locally AND on the merge commit. **⚠️ THE PLAN PREDICTED "budget one red cycle" AND IT DID NOT HAPPEN** — recorded because a prediction that did not hold is worth as much as one that did: the composition change was real (check 2) and nothing depended on its absence. **⚠️ A WRONG REASON WAS COMMITTED AND CORRECTED IN THE SAME PR.** The first commit's code comment said `SETTINGS_SIMPLE_ROW` "decides which of TWO settings layouts exists at all". It does not — `isSkinBeta()` (`settings/page.tsx:226`) does. `isSettingsSimpleRow()` is read at exactly ONE place, `:214`, and only decides whether `NativeTemplateManager` mounts, **inverted**: `templateNativeDocxEnabled() && !isSettingsSimpleRow()`. **The real reason is a PAIRING and it is sharper:** prod sets both true so the slot is `null` — the deliberate "no door in" in AGENTS.md, and why prod holds zero twin certifications while the twin flag is ON. An image carrying `TEMPLATE_NATIVE_DOCX` **without** `SETTINGS_SIMPLE_ROW` would MOUNT a surface production folds away. **Both, or neither.** Verified behaviourally, not by re-reading the ternary: `Native template` absent from `/settings`, 37 `qm-c3-set*` nodes present. *A false comment is worse than none — it is the reason the next reader stops looking.* **NOT DONE, DELIBERATELY:** `NEXT_PUBLIC_TEMPLATE_NATIVE_PDF` is not added. Prod does not pass it as a build arg either — it supplies it at RUNTIME (`docker-compose.yml:646`) with no `ARG` in the Dockerfile, and the QA stack supplies it in **neither** place. Adding `ARG`+`ENV …=false` alone would inline `false` into client bundles while the server keeps reading `true` — **creating** the inconsistency the hardening exists to prevent. Both halves belong in one change, during a prod rebuild. *Consequence to carry: any QA proof touching the pdf-native export path is measuring a configuration prod does not have.* **C1-b GROUNDWORK, generated rather than assumed:** the bridge needs **22** distinct `--color-linear-*` names across **43** surface files, every one of them declared in `globals.css`. ⚠️ *A hand-written glob found only 21* — it missed `--color-linear-surface-3` in `settings/security/mfa/mfa-enrollment-panel.tsx` because bash does not expand `**` recursively, so **the guard must derive the list by traversal, never from a maintained array.** Four new tokens are needed and each now has a usage citation rather than an assertion: `--rounds-em-text` (amber as `color:` — `login-form:290`, `note-format-manager:924`), `--rounds-processing-text` (info as `color:` at `template-review-editor:617,:657,:911` **and** as a fill bar at `:679`), `--rounds-danger` (danger as `background:` — `delete-account-dialog:302`); `coral` needs no new token, it is used only as `color:` and maps to the existing text-safe `--rounds-critical-on-dark`. **C1-b MERGED:** PR **#484** squashed to **`7d181ae8`** · **merge-commit CI on `main@7d181ae8`: `CI` run `30657051204` · `e2e` run `30657051329` · `secrets-scan` run `30657052783`, all six checks success** · 10 `Run E2E` pack steps executed, 0 skipped. **The host bridge.** C1's surfaces have no classes — **434 inline `style={{}}` objects across 43 files** reading `var(--color-linear-*)`. Custom properties inherit and resolve at computed-value time, so redeclaring the 22 old names on a scoped `.qm-rounds-host` retints all of them without touching a line of TSX: **60% come to Rounds tokens for free**, only ~33 carry a literal needing a fork. **ZERO RUNTIME CHANGE, and that is a test rather than a sentence** — no element carries the class yet, and the test says it expects to be DELETED by C1-c rather than becoming a rule that blocks the work it exists to enable. **Two new tokens** (`--rounds-em-text` #E8B168, `--rounds-processing-text` #7AB0F5). ⚠️ **Two the plan asked for are NOT needed:** `--color-linear-danger` is a `background:` and maps to the existing `--rounds-critical`; `--color-linear-coral` is only ever `color:` and maps to the already text-safe `--rounds-critical-on-dark`. ⚠️ **THE GUARD CAUGHT FOUR THINGS ON ITS FIRST RUN AND TWO WERE MINE.** `sage` and `danger` were genuinely mis-mapped — each serves BOTH roles (sage 4 foregrounds / 7 fills; danger 1 / 1), and one bridge line cannot satisfy both. The mapping follows the majority and the minority sites are tracked as **DEBT, NOT EXEMPTION**: each entry names its sites and its owning split, and the guard asserts the entry still matches real source AND still describes a genuine failure, so it cannot rot into a stale exemption. ⚠️ **MY FIRST GUARD DRAFT WAS OVER-STRICT, and that is the lesson worth keeping.** It took `min()` across all four Rounds surfaces — i.e. assumed every text token might land on the lightest — and immediately flagged `--rounds-text-3`, which is shipped across the board, stage, gates and signed screen and is GREEN UNDER AXE. Measured: text-3 is 4.68/4.59 where it is actually used and 3.76 on a surface it is not. **The guard was wrong about where the token lives.** A static check cannot know the real foreground/background PAIRING — that is precisely what axe measures on the rendered DOM, and `rounds-a11y.spec.ts` already does it. This guard exists for the one thing axe cannot do: catch a bad mapping BEFORE any surface adopts the bridge, when there is nothing rendered to measure. *Second time in two items that a probe of mine was over-strict; both times the cure was to narrow it AND keep asserting something in the narrowed case.* ⚠️ **TWO NUMBERS WERE CARRIED FROM THE WIDER BACKDROP SET INTO THE NARROWED ONE AND WERE WRONG IN A COMMITTED COMMENT:** `--rounds-em` as "4.40 on the darkest surface" — it is 4.40 on the **lightest** (surface-3) and **5.48** on the darkest; and `--rounds-accent` as 2.58 — it is **3.22** on C1's backdrops. Both corrected against measurement. *A remembered number from a different question is not evidence.* **`--rounds-em` is the row worth remembering:** it PASSES on three of four surfaces (5.48 / 5.37 / 4.89) and fails on surface-3 at **4.40** — a tenth under the bar. **A near miss reads exactly like a pass.** **SIX MUTATIONS WATCHED TO FAIL**, including the `--rounds-surface-0` trap (an undeclared right-hand token is neither a build error nor a console error — the property becomes unset and falls to its initial value, `background-color: transparent`, showing the stage through the surface) and a broken traversal, which now reddens two tests rather than letting the suite pass by covering nothing. **The surface list is derived BY TRAVERSAL** — a bash glob undercounted the names 21 against 22, missing `settings/security/mfa/` because bash does not expand `**` without `globstar`. **DEVIATION FROM THE PLAN, STATED:** the 17 control-primitive classes are NOT here. A class with no consumer cannot be proven by rule 7 — nothing renders and nothing can be made to fail — and it would be rewritten by the first split that needs it. ⚠️ **CORRECTED 2026-08-01 — THE NEXT SENTENCE OF THIS ROW WAS FALSE WHEN IT WAS WRITTEN, AND STAYED FALSE FOR THREE MERGES.** It said *"The naming CONTRACT is in `docs/design-tokens.md`"*. It was not. C1-b's 87 lines into that file were the contrast-pair rule and the host-bridge section; **the seventeen class names appeared nowhere but the plan** (`C1-PLAN.md:225`). Settled as a RECORD error rather than a regression, which is a different repair: `git log --follow --full-history -- docs/design-tokens.md` returns five commits ever, `git log -S'## Controls'` returns **`46d7ee6c` and only `46d7ee6c`** — and the pickaxe reports every change to an occurrence count, so a write-then-delete would surface two commits, not one. The section was written by **C1-d** (`design-tokens.md:234`, `@@ -231,6 +231,76 @@`, +70/−0). ⚠️ **AND COMMIT `7d181ae8`'S OWN MESSAGE CARRIES THE IDENTICAL FALSE CLAUSE**, where it cannot be edited — so the row and the commit corroborated each other while both were wrong, which is the shape rule 2c exists to prevent arriving from a second direction. *The deviation was declared correctly; the forwarding address was fabricated, and anyone building against the promised contract would have found nothing and invented their own.* **What is true:** each class lands with its consumer and its test — `-btn` plus the three `-skel-*` at C1-c with their callers, seven more (`-input`, `-label`, `-error`, `-check`, `-link`, `-panel`, `-btn-secondary`) plus the unplanned `-btn-primary` at C1-d with 1–15 callers each, and `gate-c1d-auth.test.ts:347,379` now enforces the pairing in **both** directions. **`.qm-rounds-host` is the one deliberate exception** — C1-b shipped it consumerless *because it is the bridge*, and it acquired its first caller only at C1-c. Of the plan's 17, **9 shipped**; `-field`, `-textarea`, `-select`, `-help`, `-btn-danger`, `-alert`, `-pill` and a `[disabled]` variant were never needed and do not exist (0 occurrences in `rounds-tokens.css` and 0 under `apps/transcribe-md/src`, positive-controlled against `qm-rounds-panel` at 1/14 and `qm-rounds-host` at 28). **2962 → 2971 units, tsc clean**, CSS re-parsed with postcss (106 rules, 22 bridge declarations) against a negative control so a syntax error could not reach CI. **C1-c MERGED:** PR **#486** squashed to **`ff623d87`** · **merge-commit CI on `main@ff623d87`: `CI` run `30666709780` · `e2e` run `30666710011` · `secrets-scan` run `30666709661`, all six checks success** · 10 `Run E2E` pack steps executed, 0 skipped. **Error, empty and loading brought to tokens** — the boundary behind all five `error.tsx` shims, both 404s, the visit loading state, a `/board` loading state that did not exist, and the skeletons underneath. ⚠️ **THE RECOVERY SWAP WOULD HAVE SHIPPED A 404 LOOP.** Every recovery affordance sent the doctor to `/dashboard`; under Rounds home is `/board`. But `app/board/page.tsx:76` runs `if (!isSkinRounds()) notFound()` **before** `auth()`, so with the flag off `/board` DOES NOT EXIST — and the flag is off in production until item F. A hard swap takes a doctor who just hit an error to a second 404, with the back button as the only way out. Forked in `lib/recovery-href.ts`, deliberately NOT under `lib/rounds/` because item F deletes that namespace and these components outlive it (same reasoning as `lib/sign-gates.ts`). The label lives beside the href so they cannot drift. ⚠️ **ONE OF MY OWN GUARDS WAS VACUOUS AND ONLY RULE 7 FOUND IT.** The label/href pairing test asserted `label.toLowerCase()).toContain('board')` for the flag-ON case — and **`'dashboard'` CONTAINS `'board'`**. A label reverted to "Back to dashboard" on BOTH branches passed it cleanly; the flag-ON half asserted nothing. Reading the test could never have shown this. Mutating the label and watching the assertion **fail to notice** is what showed it. Now compared by exact value, and it carries the substring trap as its own assertion so nobody reintroduces it while simplifying. *This is the sharpest instance yet of rule 7: the check that could not fail was mine, in the very PR whose subject is checks that cannot fail.* Four mutation classes proven on that guard — the hard swap, a truthiness check (unset routes to `/board`, and unset is the production state everywhere until F), the label reverting, and a surface hardcoding the href again. ⚠️ **THE PLAN'S "REAL DELIVERABLE" FOR THIS SPLIT CANNOT WORK AS SPECIFIED, and it was measured rather than reasoned.** C1-PLAN calls a dev-only `/dev/states` route the centrepiece, because Gate C cannot otherwise reach the error boundary or a `loading.tsx` that paints for <100ms. It would have been **a door onto nothing**: the QA stack runs `NODE_ENV=production` (read from the running container), `/dev/rx-warnings` — the exact pattern the plan says to model on — returns **404 on QA** against a `/login` control at 200, and **zero** E2E specs reference any `/dev/` route. A route gated on `NODE_ENV==='production'` is unreachable by every pack including the sweep it exists to serve. The route was WRITTEN, tested against that finding, and REMOVED from this PR. **Scope corrected too:** both 404s ARE reachable by navigation (proven — a bad URL returns 404 and renders the Rounds branch), so the door is needed for **2 of 4** state families, not 4. It becomes **C1-c2**, alone, because it needs the whole flag chain (Dockerfile `ARG` — an undeclared build-arg is discarded silently — plus the e2e.yml build-arg and a `gate-flag-coverage` row) and C1-a proved that chain deserves an unambiguous red. *It also needs a `preview` prop on `ErrorFallback`: the beacon POSTs scope/message/stack/digest/url to `/api/client-errors` on mount with no suppression, so a preview would emit synthetic error reports that look real to ops — and the guard must assert the beacon STILL fires when preview is falsy, or the suppression silently disables real reporting.* **The root 404 is FORKED, not bridged:** it layers an `AnimatedGrid`, a `GradientText` sweep and a SAGE radial, and the host bridge retints custom properties — it cannot touch a component that paints its own colours, so bridging alone leaves a green gradient on an indigo stage. The Rounds branch drops the decoration and lets the stage do it, which also removes a continuously animating background from a page Gate C must axe (A2 defect 4 was an animation that made text unreadable at the sampling instant). **The visit loading state is a different SHAPE, not a colour** — it promised `max-w-4xl` while the route resolves to an 820px paper, and a skeleton that contradicts what arrives moves the eye to where the content is not. **`/board` had no `loading.tsx` at all**; no flag fork there, deliberately, because `/board` fails closed and a fork would be dead code reading as a supported state. **C1-b's `danger` deferred-fork debt is PAID, and C1-b's own guard demanded it** — refusing to let a stale exemption survive. **C1-b's zero-runtime-change test is DELETED**, exactly as its own failure message instructed, replaced with the opposite assertion: adoption is real AND every adopter carries an owned `qm-rounds-*` class, because that class is the currency axe's ownership rule spends. **The bridge guard's surface list is now widened BY TRAVERSAL** to Next's convention files — `visits/[id]/not-found.tsx` and `visits/[id]/loading.tsx` were both C1-c surfaces and NEITHER was in the hand-written list, the same failure as the `globstar` miss arriving a second time from another direction. **The first control primitive lands WITH its consumer** (`qm-rounds-btn`, one caller), as C1-b said they should. **2971 → 2978 units, tsc clean, 0 lint errors**, CSS re-parsed with postcss (114 rules), all five Rounds packs green on a freshly built flag-ON image (board 6 · stage 12 · gates 10 · signed 12 · a11y 2 + 21 shots). **Behavioural proof, not a chunk grep:** on the flag-ON build a bad URL returns 404, renders the Rounds branch carrying `qm-rounds-host`, recovers to **`/board`** labelled "Back to the board", shows **no** AnimatedGrid, and its button computes `rgb(91,91,214)` = `--rounds-accent`. **C1-c2 MERGED:** PR **#488** squashed to **`829cdd01`** · **merge-commit CI on `main@829cdd01`: `CI` run `30671785766` · `e2e` run `30671785810` · `secrets-scan` run `30671785815`, all six checks success** · 10 `Run E2E` pack steps executed, 0 skipped. **The Gate C door, built the way that works.** C1-c removed this route after measuring that the plan's version could not. ⚠️ **`NODE_ENV === 'production'` IS THE WRONG GATE FOR ANYTHING A TEST MUST REACH, and it is the pattern this codebase already uses.** The QA stack RUNS a production build, so a NODE_ENV-gated preview route 404s exactly where Gate C's sweep needs it. Measured on the running container: `NODE_ENV=production`, `/dev/rx-warnings` **404 on QA** against a `/login` control at **200**, and **zero** E2E specs reference any `/dev/` route. Copying the existing pattern would have shipped a door onto nothing that looked like progress. **A build flag inverts it, and BOTH directions are proven behaviourally on real builds:** with `NEXT_PUBLIC_DEV_STATES` passed, `/dev/states` → **200**; with the SAME code and the flag absent → **404**, `/login` still 200. Both on containers reporting `NODE_ENV=production`. ⚠️ **The control that makes it evidence:** `/dev/rx-warnings` stayed **404 in the same probe**, so the difference is demonstrably the GATE and not the environment. Probe image destroyed. **Declared in the Dockerfile** — an undeclared build-arg is discarded silently, which is how the first flag-ON build shipped the old skin — **passed only on the `:rounds` CI image**, and **never in production's compose**, which the guard asserts against the compose file rather than trusting the Dockerfile default (a default is only as good as everyone's memory of it). ⚠️ **THE SUPPRESSION THAT COULD HAVE BEEN WORSE THAN THE BUG.** `ErrorFallback` POSTs `scope`/`message`/`stack`/`digest`/`url` to `/api/client-errors` on mount, unconditionally — so a preview rendering it files **fabricated bug reports**, indistinguishable from real ones and arriving from a URL that looks like a real page. It now takes a `preview` prop. But a suppression switch that silently disabled REAL reporting would be far worse than the bug it fixes, so the guard does not assert the beacon is *skippable* — it asserts it **STILL FIRES** when `preview` is falsy, that the early return is CONDITIONAL, and that the default is `false`. Both failure modes mutated and watched to redden: an unconditional `return;`, and `preview = true` as the default. **Scope narrowed from the plan BY CHECKING:** the route serves **2 of 4** state families, not 4 — both 404s are already reachable by navigation (proven in C1-c: a bad URL returns 404 and renders the Rounds branch). It is needed for the error boundary, which nothing navigates to, and the loading states, which paint for <100ms so a walk catches them essentially never. **Six mutations watched to fail:** the NODE_ENV gate restored · the Dockerfile ARG dropped · the `:rounds` image no longer passing it · **production starting to pass it** (the inverse failure — synthetic outages on a real host) · the beacon suppression made unconditional · `preview` defaulting true. All five touched files restored byte-identical. The stale-error fixture is built from `isStaleDeploymentError`'s own contract and asserted against it, so a change to that predicate cannot leave the page labelling a branch it no longer renders. **2978 → 2988 units, tsc clean, 0 lint errors**, all five Rounds packs green on the flag-ON image (board 6 · stage 12 · gates 10 · signed 12 · a11y 2). **C1-d MERGED:** PR **#490** squashed to **`46d7ee6c`** · **merge-commit CI on `main@46d7ee6c`: `CI` run `30683343153` · `e2e` run `30683343169` · `secrets-scan` run `30683343136`, all six checks success** (finished 04:13:44Z / 04:44:06Z / 04:08:46Z). **The six auth routes to tokens** — `/login`, `/signup`, `/waitlist`, `/forgot-password`, `/reset-password`, `/check-email` — plus the `rounds-c1` pack that proves them. ⚠️ **FOLLOWING THE PLAN WOULD HAVE SHIPPED THREE AA FAILURES.** The plan's axis for this split is "BRIDGE the ~60 colour-only objects, FULL for the ~40 that carry shape". Derived by traversal the real figures are **5 of 110 objects colour-only — 2 of them in code that renders** — and 105 carrying geometry: **the axis partitions nothing.** Following it lands `#0d1611` on accent at **3.43:1** (`.qm-lin-btn-primary`), `#08090a` at **3.71:1** (waitlist submit), and `#0c1410` at **3.48:1** — **2.71:1** on the gradient's far stop (`.qm-c3-auth-mark`). That is the submit button of four of the six routes. **A bridge retints a custom property; it cannot touch a literal**, and the literal sits on the most important control on the page. ⚠️ **AND GATE C STRUCTURALLY COULD NOT HAVE CAUGHT ANY OF IT.** Ownership climbs to the nearest ancestor-or-self carrying ANY class, so `<button class="qm-lin-btn-primary">` answers for itself, resolves NOT owned, and its violation files as "inherited" — reported, never blocking. The brand mark is worse: both spans are `aria-hidden`, so axe never evaluates them at all. `--rounds-on-accent` (#fff — 5.37:1 / 6.90:1) is the fix, and **`gate-c1d-auth` computes the ratios in a unit** precisely because the E2E gate cannot. *The same rule from the other direction:* the auth shell classes every node it renders, so a violation inside the form climbs to `.qm-c3-auth-form`, matches nothing, and is reported rather than gated — **`violations: []` over an unmeasured form.** Hence `qm-rounds-authform` on the container and `qm-rounds-*` on each control, and the pack's third positive control **plants a BRIDGED node (own class, not a Rounds one) and asserts it is NOT gated** — the blind spot is written down rather than assumed away. **C2 inherits that.** ⚠️ **THE GATE THEN FOUND A DEFECT NOBODY HAD TOUCHED: A SURFACE THAT CHANGES WHAT IS UNDER THE TEXT IS A CONTRAST CHANGE** — seventh instance of one lesson, with a new face. `.qm-rounds-panel` grounds to surface-2, a step lighter than the card it sits in, and that alone took a forgot-password paragraph from 4.91:1 to **4.18:1** with no text changing. `--rounds-text-3` is safe on the stage and on surface-1 and **not** on surface-2. The panel now re-bridges the faintest tiers upward for its own subtree — the host-bridge mechanism one level down. **Also:** the axe harness is now **SHARED, not copied** (`helpers/rounds-axe.ts`) — the whole of `runAxe` had to move, because the adjudicator `ownedByDom` is declared inside the `page.evaluate` callback and *a serialised callback cannot close over a module import*; the regex the plan named as "the adjudicator" is reporting-only, and **lifting it alone ships the log and leaves the gate behind**. **`gate-shot-durability` no longer pins one spec by path** — it reddened the moment the sink moved, correctly, and now derives helper + every `rounds-*` pack by traversal, asserts **exactly one** upload step (it was `.find()`, so a second would never have been checked) and asserts every pack runs BEFORE it — an ordering `if-no-files-found: error` structurally cannot see, because earlier packs have already filled the directory. **`NEXT_PUBLIC_SKIN_BETA` is now pinned** — built into the `:rounds` image since Gate A and asserted nowhere, while choosing which branch of `auth-shell.tsx` renders, so dropping it fails the pack while the product is correct. **Two copy defects, both correctness rather than taste:** /signup advertised "Free for 14 days. No credit card." above a required invite field, with no trial anywhere in the schema or the actions; `VerifyToast` told the doctor to click "resend" — a control no page carries, on the wrong page. **`14-auth-signup-onboarding` had two assertions that could not fail** — the refusal check DOM-resolved to a static paragraph present *before* submit, and the credential replay used a negated `toHaveURL`, which resolves against the current URL and returns before a leak could land; both repaired, and **the repair proven by making the gate accept the code and watching the test fail**. **`waitlist_entries` had no reaper** — an unauthenticated write unreachable from `users`, so the cleanup cascade could never see it. **Proof:** ⚠️ **THE UNIT FIGURE IN PR #490'S BODY IS WRONG AND IS CORRECTED HERE FROM THE CI ARTEFACT.** It claimed *"3009 → 3010 units"*, i.e. +1. **The merge-commit CI run says `Tests 3013 passed \| 4 skipped (3017)`, `Test Files 239 passed \| 2 skipped (241)`** (run `30683343153`, job `91324447779` — the same `npm run test:unit -w transcribe-md` this ledger's other rows quote, reproduced locally to the digit). Against the previous merge commit's own run — `ad0f9202` and `829cdd01` both at **2988** (runs `30675196690`, `30671785766`) — **C1-d's real delta is 2988 → 3013, +25.** The stated base of 3009 corresponds to no commit on `main`; the nearest measured points are 2988 before and 3013 after. *Recorded rather than quietly rewritten, because the ledger's delta chain is arithmetic that later rows build on: C1-c's `2971 → 2978` and C1-c2's `2978 → 2988` both reconcile against CI, so this is one broken link and not a drifting series — but a session that computed its next base from 3010 would have been three items adrift with nothing to notice it.* **Everything else in the proof reproduces:** tsc clean, 0 lint errors on the diff, CSS re-parsed with postcss (133 rules) against a negative control rejecting 3/3 malformed inputs. **24 mutations watched to redden**, sources restored byte-identical. **One mutation deliberately does NOT redden, and is recorded:** `gate-project-env` adjudicates "the last recreate before the run", not strict adjacency, so a pack sharing an image with its predecessor is fine — a guard forbidding that would be the over-strict-probe defect a third time. All six Rounds packs green on a freshly built flag-ON image (board 6 · stage 12 · gates 10 · signed 12 · a11y 2 · **c1 3**, 41 shots); the touched required-gate specs re-run green on a flag-OFF build built the way CI builds it. **Behavioural, not a chunk grep:** all six routes carry `qm-rounds-host qm-rounds-auth` and `qm-rounds-authform`, `--color-linear-text` resolves to `#e7ebf1` inside the host, the card radius computes 18px, labels render JetBrains Mono, the brand mark computes `rgb(255,255,255)` on the indigo gradient, and **the primary CTA computes white on `rgb(91,91,214)` — 5.37:1** on all five. Control: `/dev/rx-warnings` stayed **404** beside `/dev/states` at **200** on a container reporting `NODE_ENV=production`. **One state is NOT photographed and is named rather than bought:** login's needs-verification banner needs `RESEND_API_KEY` set, which would breach the QA stack's vendor severance and break `captureResetToken()` by construction. ⚠️ **C1-d'S CLOSE-OUT WAS ITSELF DELAYED FIVE HOURS BY A BLIND WAITER** — its merge-commit CI had been green since 04:44Z and was read at 08:52Z. Not a CI fault and not a work fault; see rule 7's *a wait is a check* corollary. **C1-e MERGED:** PR **#492** squashed to **`ee0bf3f2`** · **merge-commit CI on `main@ee0bf3f2`: `CI` run `30699466057` · `e2e` run `30699466058` · `secrets-scan` run `30699466050`, all six checks success** · e2e read step by step: **11 `Run E2E` pack steps EXECUTED, 0 skipped** (the one `skipped` step is the traces/videos upload, which is conditional on failure). **Settings to tokens** — the C3 rail and its seven panels, both modals, the three MFA panels, and the loading state nobody had classed. ⚠️ **THE DEFECT THIS ITEM EXISTS FOR: A BRIDGE DOES NOT CROSS A PORTAL.** Both settings modals render `<Dialog.Portal>` with no `container`, so Radix mounts them on `<body>`. `data-skin` is on `<html>` so `[data-skin='rounds']` still matches — but the bridge is `[data-skin='rounds'] .qm-rounds-host`, deliberately scoped, and **a portalled node is not a descendant of the page root**. NINE distinct `--color-linear-*` names in each dialog kept old-skin values: a near-black #0d0e10 dialog opening on a #161b24 Rounds page. `gate-rounds-bridge`'s adopter check could not see it — it asks whether the FILE contains `qm-rounds-host`, and the file does, **on the trigger rather than on the portalled content**. The host now goes on `Dialog.Content` itself. ⚠️ **And the fix carries a trap that would have made it worse.** `.qm-lin-btn-primary` hardcodes `color: #0d1611` — 4.62:1 on the old danger fill, **3.62:1** on the bridged `--rounds-critical`. Bringing the FILL into the portal by any route that did not also bring C1-d's label fork would have pushed a passing button under AA: **a contrast regression created by the act of fixing a colour.** The E2E asserts the computed label and fill TOGETHER, so shipping half of it is not expressible. ⚠️ **THE HOST MUST BE ON, OR ABOVE, THE ELEMENT THAT PAINTS THE GROUND.** `/settings` is the first Rounds surface inside `AppFrame`. `.qm-lin-app` paints an OPAQUE `background: var(--color-linear-bg)` at `min-height:100vh` and is an ANCESTOR of the host, so the host's own redeclaration cannot reach it and the stage gradient on `body` sits underneath, covered. Every earlier adopter escaped **by accident**: `/board` does not use `AppFrame`, and 404/loading/error render outside it. Fixed for this subtree only — the tempting fix, `qm-rounds-host` on `.qm-lin-app`, would bridge EVERY authenticated page, none designed for Rounds or axe-walked, which is the partial flip rule 4 forbids. **The chrome gap is NAMED as C2's**, so what C2 inherits is the decision rather than the discovery. ⚠️ **TWO CONTRAST DEFECTS THE UNITS STRUCTURALLY CANNOT SEE, both found on the rendered DOM.** (1) *A fill token used as text* — `globals.css` sets `color: var(--color-linear-danger)` on the danger heading and active danger tab; the bridge maps that to `--rounds-critical` #c93a2e **correctly**, because its majority use is a border/fill, and as text it is **3.39:1** against 7.70:1 for the on-dark variant. `gate-rounds-bridge`'s foreground scan walks `.tsx` **ONLY**, so a `color:` written in `globals.css` was never in its universe — not missed, never in scope. Eighth instance of the palette's standing lesson, from a direction no guard watches. (2) *A correction cannot reach what does not speak its vocabulary* — `.qm-rounds-panel` lifts the faintest tiers by REDECLARING `--color-linear-*`, which protects everything reading a bridged name; the dialog labels carry `color` **INLINE** via a module const, so neither the class nor a `.qm-rounds-panel .qm-rounds-label` override touched them. Only an ancestor redeclaration reaches them. **A primitive tells you what a surface INTENDS; only the cascade tells you what it DOES.** ⚠️ **THE GATE CAUGHT THE AUTHOR OF THE GATE.** `.qm-rounds-btn-danger` was declared up front for an obviously destructive button; the only candidate keeps an inline `background` it needs with the flag OFF, inline beats a class, so the primitive's fill could never apply and the rest duplicated C1-d's fork. `gate-c1d-auth`'s orphan assertion failed — `expected [ 'qm-rounds-btn-danger' ] to deeply equal []`. **The class is deleted, not given a manufactured caller.** *(The first diagnosis of that failure was also wrong — the recorded "guard trips on its own comment" trap was assumed; it was simpler, the class was still in a `:disabled` selector group. Checking beat guessing.)* **THREE GUARDS, each mutation-proven.** `gate-controls-contract` — the debt named the same morning: both directions, with the boundary between control primitive and Rounds-native screen class **DERIVED** and asserted from BOTH sides so neither a collapse nor an over-broad read passes; 12 tests, 9 mutations, plus a **no-mutation positive control first** — without which a harness that reds on everything and a guard that catches everything are the same output. ⚠️ *It found the comment trap live in the tree*: `mfa-management-panel.tsx` names a Phase-B class in a JSX comment, which unstripped would have had the guard demand a contract row for a class never near a settings page — **a guard fabricating its own finding.** `gate-c1e-settings` — the contrast arithmetic for the new forks. `gate-css-parses` — because a comment edit closed a block mid-comment and **broke the image build ~10 minutes in** as `Unknown word WHY` behind a turbopack stack trace naming neither file nor edit; **four prior items each performed that postcss check BY HAND and recorded it as evidence**, which is the definition of something that should be a test. It reddens on the exact defect in **13ms**, with file and line. ⚠️ **A FAILURE MESSAGE THAT CANNOT BE DIAGNOSED IS A DEFECT IN THE HARNESS.** `rounds-axe.ts` collected axe's `targets` and discarded its `data` — the `fgColor`/`bgColor`/`contrastRatio` axe computes for every contrast node. So a colour failure named four selectors and **no colours**, and three rebuild cycles went into hypotheses about which rule decided the pixel. Once the pair printed, the answer was that **none of them did**: `#5f6772 on #13171f = 3.13`, values not in this palette — `--rounds-text-2` and `--rounds-surface-1` **COMPOSITED MID-FADE**, because Radix opens with `fade-in-0`/`zoom-in-95` and the sweep was measuring during the animation. **A2 defect 4, one surface over.** The helper now carries the pair, the message prints it, and the wait is on `getAnimations().finished` — the settle condition is the animation finishing, not a duration someone guessed. **Recorded, not fixed:** `qm-rounds-devstates` is applied and declared nowhere — it is not a styling class, it is an axe-OWNERSHIP marker, and so are nine Phase-B classes. **A `qm-rounds-*` class has two jobs and may legitimately do only the second.** The new guard pins it as the single such exclusion so a second cannot appear quietly. `gate-rounds-bridge.test.ts:332` still decides adoption on raw file text. **Proof:** 3013 → **3057 units**, tsc clean, CSS re-parsed with postcss (141 rules) against a negative control rejecting 3/3 malformed inputs. All six Rounds packs green on a freshly built flag-ON image, run **sequentially** with per-test counts and exit codes: **board 6 · stage 12 · gates 10 · signed 12 · a11y 2 · c1 5 — 47 tests, 0 failed, 48 screenshots.** Control: `/dev/rx-warnings` **404** beside `/dev/states` **200** on a container reporting `NODE_ENV=production`. ⚠️ **AN INTERMITTENT AUTH FAILURE DURING THIS WORK WAS NOT A PRODUCT DEFECT AND IS NOT A FLAKE TO INHERIT.** Two of my own Playwright invocations overlapped against one QA container, racing signup and login. Four hypotheses were wrong before the process was checked — user accumulation (9 users, cleanup works), animation timing on auth, a cold container (5/5 in 42.3s), and before those two fixes aimed at a mid-fade artefact. Three sequential `rounds-c1` runs — two warm, one deliberately cold — are 5/5. **Recorded because "the pack flakes" would send the next session hunting something that does not exist.** ⚠️ **AND ONE DEBT C1-e DID NOT PAY, NAMED HERE RATHER THAN LEFT TO BE FOUND:** the settings host now covers `NoteFormatManager`, and the C1-e pack **never opens that section** (`grep -c "note-format"` in the pack = 0). C1-b predicted exactly this and deferred it to "C1-e / C1-f". **The host was extended over a panel that was not measured** — four AA failures at 3.43:1 sit under it, invisible because the sweep does not walk there. **C1-f owns it.** **C1-f MERGED:** PR **#494** squashed to **`5ac874a9`** · **merge-commit CI on `main@5ac874a9`: `CI` run `30711793811` · `e2e` run `30711793881` · `secrets-scan` run `30711793799`, all success** · e2e read step by step: **11 `Run E2E` pack steps EXECUTED, 0 skipped** (the two skipped steps are the failure-conditional log and trace uploads), plus the Rounds screenshot upload. **Templates to tokens** — the note-format panel and its six views, and the advanced editor as a bridge-only surface. ⚠️ **THE DEFECT THIS ITEM EXISTS FOR: NOBODY EDITED THE THING THAT BROKE.** C1-e extended the host over this panel, so every `--color-linear-*` here has resolved to a Rounds token since that merge with no edit to any templates file. **A bridge retints a CUSTOM PROPERTY and can never reach a LITERAL.** `#0d1611` typed over a sage fill was 6.72:1 and became **3.43:1** the moment the bridge mapped that fill to `--rounds-accent` — on the primary button of four live views, with nothing in any diff saying so. Eight more literals were sage or amber chrome, drawing GREEN borders around INDIGO content. Nine are tokens now, declared in `globals.css` with the values they replace: a rename, not a restyle. **Proven on a real flag-OFF render — 10/10 exact, `data-skin = null`, against a negative control that returns empty** (an undeclared property yields `""`, so "it resolved" means something). ⚠️ **THE SECOND DEFECT IS OWNERSHIP, AND IT IS WHY THE FIRST WAS INVISIBLE.** `ownedByDom` stops at the FIRST ancestor-or-self carrying any class. Every node in `note-format-manager` and `template-review-editor` is classless, so the walk ran past them and halted on `.qm-c3-set-content` — not a Rounds name — and every violation underneath filed as *inherited*: reported, never blocking. **`violations: []` over an unmeasured panel**, the C1-d auth-form finding in a new place. `.qm-tpl-actionbar` and `.qm-ux-proc` are SECOND shields, and what the action bar shields is the primary CTA — the exact node carrying the failure. The new classes are ownership anchors first and styling second; two set no colour at all. Anchoring the editor makes ~900 classless nodes measurable in one step. ⚠️ **THE THIRD IS A GROUND CHANGE WITH NO COLOUR EDIT BEHIND IT** — C1-d's lesson, eighth instance. `.qm-c3-set-panel` grounds the panel on surface-1 where `--rounds-text-3` is 4.68:1; the rows, cards and alert repaint a step lighter where the SAME token is **4.18:1**. Each class that repaints its ground now re-bridges the faintest tiers upward for its own subtree (5.97:1). ⚠️ **THE PLAN'S E2E PATH FOR THIS ITEM CANNOT WORK, AND IT WAS MEASURED.** `C1-PLAN.md:315` says drive the machine through `parseToReview()`, which waits for "Save & activate" — the REVIEW EDITOR. This image builds `UX_SIMPLIFY=true`, and `note-format-manager.tsx:195` routes a completed parse to `confirm`, never to `review`; the helper would also `fill()` a panel still carrying `hidden`, because the C3 rail keeps all seven mounted. Following it yields a pack that hangs its full timeout and reports the PRODUCT as broken. `doc-preview.spec.ts` is the only spec that drives this machine on a UX_SIMPLIFY build and is the model used instead. **Two of the six views cannot be walked to at all** — `parsing` paints only while four server actions are in flight, `rejected` needs a container env this image does not carry — so both render through the `/dev/states` door C1-c2 built, from the REAL components and the REAL stage builder. ⚠️ **THREE OF THE DEFECTS FOUND WERE IN MY OWN CHECKS, and only mutation testing found them.** (1) the literal scan **fabricated its own finding** — it filtered comments per LINE, so the prose explaining the fork reported the hex it exists to prevent; third instance in this repo. (2) the preview-derivation check matched `advance(initialStages(…))` in the COMMENT saying it must be derived, not in the code. (3) the tier-lift check was an EXISTENTIAL over the stylesheet, so deleting the lift from three of four subtrees left one block matching and the guard green. *An existential over a set is not a claim about the members of that set.* ⚠️ **AND `gate-controls-contract` READ `SURFACE_ROWS[0]` AND `PREFIX_ROWS[0]`.** With one row of each kind the index was invisible; C1-f's second prefix row would have shipped **UNCHECKED** — free to expand to nothing or to the bare namespace. It now iterates every row, and two `toBe(1)` counts became identity assertions, which is what they meant. **Proof:** 3057 → **3077 units** (+20), 244 test files, read from the merge-commit CI artefact (run `30711793811`) and reproduced locally to the digit; tsc clean; new files lint clean. **17 mutations watched to redden** after a **no-mutation positive control**, sources restored byte-identical. All six Rounds packs green on a freshly built flag-ON image, run sequentially: **board 6 · stage 12 · gates 10 · signed 12 · a11y 2 · c1 10 — 52 tests, 0 failed, 54 screenshots.** Control: `/dev/rx-warnings` **404** beside `/dev/states` **200** on a container reporting `NODE_ENV=production`. Flag-OFF, on a SEPARATELY TAGGED build made the way CI builds it: 15 note-format + settings specs green. **The C1-e debt is paid and the numbers reconcile:** the pack referenced `note-format` **0** times when C1-e recorded the debt and **10** now; of six `btnPrimary` call sites exactly **four are live** — `:952` and `:963` sit in the legacy `TemplateRow` branch that `SETTINGS_SIMPLE_ROW=true` makes dead — so C1-e's "four" was right for the shipped configuration and a raw grep of six is the figure needing the qualifier. ⚠️ **A STEP NAME BROKE THE REQUIRED E2E GATE AND THE PR WENT GREEN ANYWAY.** Renaming a workflow step to stop it claiming it ran only C1-d's tests introduced `C1-d/e/f: auth` — a colon-space in an unquoted YAML scalar starts a mapping, and `e2e.yml` stopped parsing at 404:44. GitHub then listed the run by **filename** rather than its `name`, failed it before any job started with no log to fetch, and **never created the `Playwright E2E` check-run at all**. The PR showed **six checks, all green**: "is anything pending?" → no; "did they pass?" → yes. **The required gate had left the set being asked about, and nothing in the answer said so.** This is rule 2a's corollary one step on — a `cancelled` run at least looks odd; a run that never registers a check leaves an all-green PR with a hole in it. What caught it was **enumerating the workflow RUNS for the branch instead of reading the check list**. `gate-workflows-parse` closes it: 13ms, names file and line, and it **fails loudly if the YAML parser itself is missing** rather than skipping — a guard that silently stops running is the defect it exists to catch. Negative control reproduces the exact broken string and asserts the repaired one parses. ⚠️ **A CLAIM IN COMMIT `7a36c543`'S MESSAGE IS OVERSTATED, AND IS CORRECTED HERE BECAUSE A MESSAGE CANNOT BE EDITED.** It says a flag-OFF `/board` serves 200 "rather than the 404 the gate at `board/page.tsx:76` implies". **On `:latest` — the image prod and the QA default both run — `/board` correctly returns 404** (verified twice, unauthenticated). The 200 is real but narrower: it reproduces 3/3 on a locally built image carrying every `NEXT_PUBLIC_*` at its Dockerfile default plus `SKIN_BETA=false`, where the response is a **content-less streaming shell** ("Board · QuillMD / Skip to main content", 30144 bytes) — the status was committed before the gate threw. **Which flag causes the difference is NOT established**, and no test asserts the HTTP status either way. **C1-c's recovery fork is unaffected**: `recoveryHref()` returns `/dashboard` with the flag off, so no recovery path sends a doctor to `/board` regardless. **Deliberately NOT done:** `native-template-manager.tsx` stays PARKED with its literals. The abandoned WIP named at the end of this row had tokenised them and its reasoning is sound, but the component renders `null` on every image that ships (`templateNativeDocxEnabled() && !isSettingsSimpleRow()`, both true), so nothing renders it and **rule 7 cannot prove it** — the same reasoning C1-b used to defer the control primitives. `gate-c1f-templates` holds the exemption to being REAL: the file must still contain a literal AND still be gated that way, or the exemption reds.  ⚠️ **AND C1-f SHIPPED A NUMBER A CHECK COULD NOT SEE PAST — CORRECTED IN `25c96966` (PR #495), merge-commit CI on `main@25c96966`: `CI` run `30713488742` · `e2e` run `30713488745` · `secrets-scan` run `30713488736`, all success · 11 `Run E2E` pack steps executed, 0 skipped; 3077 → 3078 units from the artefact.** C1-f forked two real-text sites and wrote `sites: 2` into the deferred-fork list. **The tree held 3** — and the `sites: 4` it started from was produced by the same blind matcher, so the true figure before any fork was **5**. Every number in that entry's history was the matcher describing itself. The third was `template-review-editor.tsx`'s ☒/☐ state glyph, written as a TERNARY, which the matcher required to start with `var(` and so had never seen — nor the `var(--a, #fallback)` form, which flag-safety guidance RECOMMENDS, so the blind spot was set to GROW. **The regex is the small half:** the staleness assertion RECOMPUTED the count with the same regex, so it confirmed the number the matcher would produce rather than the number in the file, and every other foreground assertion asks that same matcher. All three are forked now, `DEFERRED_FORKS` is **empty**, emptiness is asserted DIRECTLY rather than iterated over, and `matcher shapes` pins the matcher with fixtures it did not produce (PLAIN · TERNARY · FALLBACK · COLOR-MIX · skin-fork inline and via a `const`, plus negative controls — `backgroundColor` ends in `color`). 5 mutations reddened; the decisive one is that reverting the ternary fork now reds the AA check, which it could not before. ⚠️ **FOUND BY READING AN ABANDONED LOCAL WIP BRANCH** (`feat/rounds-c1f-templates`, commit `f0f33778`) from an earlier session that had attempted C1-f and never pushed. Its diagnosis was right and would have died with the branch. **Before starting an item, run `git branch -vv`** — it costs nothing and this one held a correct finding about work that had already merged. Its E2E was one narrower test and its parked-file tokenisation was declined for the reason above; harvested, then retired. **C1-g MERGED:** PR **#497** squashed to **`676a8269`** · **merge-commit CI on `main@676a8269`: `CI` run `30718847535` · `e2e` run `30718847541` · `secrets-scan` run `30718847540`, all success** · 11 `Run E2E` pack steps executed, 0 skipped. **3078 → 3086 units** from the artefact (245 files), tsc clean, 0 lint errors. **The surface tells the truth about where things live.** ⚠️ **`/settings/note-format` DID NOT EXIST AND AN EMAIL POINTED AT IT.** `board-chrome.tsx:133` (the Rounds nav) and `lib/email.ts:371` (the certified-template email's manage URL) both linked there; both 404'd. **Fixed at the ROUTE, not at the links** — an email already delivered cannot be rewritten, so editing `email.ts` fixes future sends and leaves every message in a doctor's inbox pointing at a 404. ⚠️ **AND `template-certified-email.test.ts:44-45` WAS ALREADY "PINNING" IT** — by asserting the STRING appears in the payload. **A string assertion about a URL says nothing about whether the URL resolves**, so the guard and the defect coexisted. `gate-c1g-routes` checks the claim instead: every `/settings/*` path any source links to must resolve to a real segment, **derived by traversal** — a maintained list of links is exactly what would have missed these two. The directory helped it hide: `src/app/settings/note-format/` has existed all along holding this feature's COMPONENTS, so `ls` shows a folder while Next, which routes on `page.tsx`, serves nothing. ⚠️ **IT HAD TO WORK ON BOTH SETTINGS BRANCHES, WHICH ARE DIFFERENT SHAPES.** Production renders the C3 rail, whose seven panels stay mounted with `hidden`, so arriving must PRESELECT or the doctor lands on Profile with no sign the link meant anything; the required chromium gate builds `SKIN_BETA=false` (`e2e.yml:97`) and renders the legacy long-scroll stack, where the section simply exists and preselect is meaningless. Rendering the page component with a prop satisfies both **without duplicating ~790 lines and without a redirect** — the URL the doctor clicked is the URL they stay on. The prop is VALIDATED against the real section list: an unknown id would leave every panel `hidden` and render the rail above an empty column, throwing nothing. **The 2FA card described shipped work as unbuilt, in BOTH branches**, months after MFA shipped at `/settings/security/mfa` — whose only entrances were a typed URL and `admin/layout.tsx:84`'s redirect. Copy corrected and **both** branches given a door; the guard asserts the count is **2, not ≥1**, because fixing one branch fixes the surface nobody is looking at. Billing's "Stripe portal in the next Settings wave" rewritten to what is true during the pilot, **button still disabled** — the copy changed, not the capability, and the guard asserts both. **Proof on BOTH branches, each on its own freshly built image:** C3 (`SKIN_BETA=true`, the shape production renders) — route 200, the note-format panel visible AND asserted to be the only open panel by id; all six Rounds packs green: **board 6 · stage 12 · gates 10 · signed 12 · a11y 2 · c1 11 — 53 tests, 55 screenshots**. Legacy (`SKIN_BETA=false`) — route 200 and 8 specs green, with `/dev/states` **404** in the same probe so the build is demonstrably flag-OFF rather than the difference being environmental. **5 mutations reddened**, sources restored byte-identical — including **deleting the new segment**, which reds the linked-route assertion: the guard would have caught the original defect. ⚠️ **A SOURCE GREP THAT FINDS ZERO BECAUSE THE TEXT WRAPS READS EXACTLY LIKE "ALREADY FIXED".** Re-verifying the plan, my first pass reported two of C1-g's four bullets as closed. They were not: `grep "lands in the next batch of Settings"` returns NOTHING when the string breaks across a JSX line, and both lies were live at `:338` and `:756`. Only a whitespace-flattened search showed it. One bullet WAS genuinely already closed — /signup's trial claim, by C1-d — so the answer was three open and one closed, and the grep had it backwards. ⚠️ **RAISED FOR C2/D, NOT ABSORBED, and the plan's citations for it are WRONG.** No nav component links `/board` and `AppFrame` has no Rounds branch, so a doctor who reaches Templates from the board has no way back — verified true. But `C1-PLAN.md:328` cites all five under `src/components/`; **every one of them lives under `src/components/ui/`** (`top-nav`, `top-nav-c3`, `mobile-nav-c3`, `sidebar-c3`, `icon-rail`, `app-frame`), and a session grepping the cited paths gets zero hits and concludes the components are gone. The finding is real; the addresses are stale. **C1 is now COMPLETE.** |
| **C2** | Default-paper typography + Gate C | ✅ **DONE, MERGED — C2-a · C2-b** | **exports match preview 1:1** (this is the report-template design deliverable) · axe on every restyled screen **incl. waitlist** · full suite + typecheck · E2E green · merge on green | Two PRs. **#499** merged as **`c9937125`** · **merge-commit CI on `c9937125`: all six success** — `test` `91434518967` · `unit tests` `91434518954` · `Playwright E2E` `91434518893` · `npm audit` `91434518976` · `dev-dependency advisories` `91434518972` · `TruffleHog` `91434519042`. **#500** merged as **`6f96be5b`** · **merge-commit CI on `6f96be5b`: all six success** — `Playwright E2E` `91439647580` (run `30726711307`) · `test` `91439647558` · `unit tests` `91439647522` · `npm audit` `91439647541` · `dev-dependency advisories` `91439647567` · `TruffleHog` `91439647514`. `c9937125` is an ancestor of `6f96be5b`, which is an ancestor of `main`, so the later run covers both (rule 2a's corollary). **The e2e was read STEP BY STEP, not concluded from the tick: all 46 steps EXECUTED** — rounds-board 18 · rounds-stage 20 · rounds-gates 22 · rounds-signed 24 · rounds-a11y 26 · rounds-c1 28 · doc-preview 36, every one `success`; the only two `skipped` steps are the on-failure-only log/trace uploads. **#499 — GATE C MADE ABLE TO FAIL.** Five restyled states had been built and never swept (C1-c's axe was deferred to a pack that sweeps only auth); `/settings/loading` had **no door at all**. Nine states swept now, with `gate-c2-gatec` asserting the two sides against each other so an unswept state is a red unit, not a silent hole. And the sweep itself was measuring nothing on `/board`: `ownedByDom` stops at the first ancestor carrying ANY class, and the board's chrome is entirely inline-styled and classless, so every node climbed to `<body>` and filed as *inherited* — **the `board` state had been green on the lane rows alone since Gate A**. Found: the error boundary at 4.17:1, and the day meter painting **fill tokens as text** (`--rounds-ready` 3.39:1, `--rounds-processing` 3.80:1) — which fell between two guards and under a third, so the new guard is **derived, not listed** (a token is a fill iff the stylesheet declares a `-text`/`-on-dark` sibling), catching six sites including the retry button's 2.72:1 label, latent because no fixture had ever produced a FAILED lane. **#500 — THE PREVIEW *IS* THE WORD FILE, AND IT WAS A DIFFERENT PAGE.** `pdf-generator.ts` drew US Letter; `docx-generator.ts` declared no page properties at all, so Word used the library's default **A4** — measured 595.3×841.9pt vs 612×792pt. The doctor read an A4 page on screen and downloaded a Letter one. **And the parity test that existed could never have seen it**: it compares section-heading STRINGS, and stripping XML tags discards `w:pgSz`/`w:pgMar`/`w:rFonts`/`w:sz` — text extraction structurally cannot see geometry or type. It reads the bytes now and names US Letter EXPLICITLY, because two artifacts agreeing on the wrong page would satisfy an equality alone. Also: the converter could not render the type the document names (stock gotenberg → NotoSerif substitution; `meddoc-pro-gotenberg:fonts` → Charter/InterTight, with `fc-cache && fc-list \| grep -qi charter` failing the BUILD rather than shipping a silent substitution), and `deploy-prod.sh` gained step 5b because **a service a deploy never names is left behind**. 3095 → 3110 units, tsc clean, 7 mutations watched to redden. **THE TWO OWED PROOFS ARE DISCHARGED, and by CI on the merge commit rather than by a sentence in a PR body** (rule 7): *(i) QA end-to-end preview on the fonts image* — step 35 brings up `gotenberg` from `docker-compose.qa.yml`, which **builds** `meddoc-pro-gotenberg:fonts` (qa.yml:28-38), and step 36 `doc-preview` passed; *(ii) explicit flag-OFF export proof* — that same `:doc-preview` image is built with FOUR build-args (`DOC_PREVIEW`/`SETTINGS_SIMPLE_ROW`/`UX_SIMPLIFY`/`SKIN_BETA`) and **`NEXT_PUBLIC_SKIN_ROUNDS` is not among them**, so it defaults false: the export path was proven through the fonts converter on a Rounds-OFF build. The flag-independence scan (`gate-c2b-export-parity`, negative-controlled) rides the flag-OFF unit suite. **Flag stays OFF — the flip is item F.** ⚠️ Recorded 2026-08-02 by item F's session: **this row sat `⬜ TODO` with no evidence while both PRs were merged on `main`**, which is exactly what rule 5 exists to prevent and what A1's row already warned about — the evidence existed the whole time and nobody had written it down. |
| **F-pre** | **Reboot proof — BOTH encrypted stores** | ✅ **DONE** | one real host reboot, then `bash scripts/verify-post-reboot.sh` = 0. It asserts the whole chain: **both** units started AT BOOT (not by hand) · both mappings open · both mounts live on their dm devices · Postgres **and** MinIO healthy on those devices · both fail-closed guards intact · prod 200 · co-tenants up | Added 2026-07-29, widened the same day when Postgres got the same guard (PR #456). Both unlocks are `Before=docker.service` and **both stores now fail closed**, so a unit that loses its race with docker takes the stack down rather than reverting to plaintext — the right trade, but only if the ordering works, and a hand-start cannot prove ordering. **The script already narrows the job**: `pgdata-encrypted` started **8s after the 2026-07-27 boot**, so its ordering IS proven by a real reboot; only `miniodata-encrypted` (hand-started, +189687s) is unproven. **Chosen boundary: after A2 merges, before B1 opens.** Handle the two known side effects as part of the proof, not as surprises — the QA stack does NOT self-restart, and a stale `@reboot` cron dirties the tree. Script: `scripts/verify-post-reboot.sh`, PR **#457** merged as **`ff2078e2`**. Runbook **§5.7.4** (added 2026-07-29 — this pointed at §5.7.1–5.7.2, neither of which ever mentioned the proof; a production safety mechanism documented only in a project ledger is documented for the wrong reader). **⚠️ THE REBOOT CANNOT BE TRIGGERED FROM AN AGENT SESSION — Claude Code runs ON this host (`crimson-mink-43222`; its own PID is visible in the host PID namespace), so a reboot kills the session that would verify it.** It therefore records itself: `quillmd-postreboot-proof.service` (enabled, `After=docker.service`, 90s settle) runs the script on **every** boot and writes `/var/log/quillmd-postreboot-proof.<UTC>.log` + a `.latest.log` symlink, exit code **not** swallowed so a bad proof shows in `systemctl --failed`. That also covers the UNPLANNED hypervisor resets this host is known for — the ones nobody is watching. **To close F-pre: reboot the host from outside a session, then read `.latest.log` and expect `exit=0`.** Static evidence already gathered short of a boot: `systemctl show docker.service -p After` **contains both units** (the ordering edge is materialised, not just declared), both units `systemd-analyze verify` clean, and the two are byte-identical apart from `Description` — and pgdata's shape **is** boot-proven (started 8s after the 2026-07-27 boot). **ARMED 2026-07-29T14:3xZ — everything that can be done before the boot is done; only the boot is left.** Baseline run recorded: **exit 1, and on exactly one line** — `miniodata-encrypted.service started 189687s after boot (grace 120s)`. Every other assertion is already green (both mappings + mounts on their dm devices, both standing mount-checks 0, all 10 prod containers up, `quillmd.com` 200, all three co-tenants up, tree clean). Prep done this session: both LUKS units confirmed **`--key-file`**, so the unlock is unattended and a reboot **cannot** hang on a passphrase prompt; prod + all co-tenant containers are `unless-stopped` (they self-restart) while 5 of 6 QA containers are `no` (the documented side effect); `docker` and `nginx` both `enabled`; the proof unit's stale `failed` state — left by this morning's deliberate hand-run — **reset**, so `systemctl --failed` is empty and the post-boot signal is unambiguous; and **the stale `@reboot` cron is retired** (see below). **The property that makes this recoverable: section 1 compares `ActiveEnterTimestamp` against boot time, so it stays valid whenever it is run.** A hand re-run hours later still proves boot ordering. So if the boot unit's 90s settle turns out to be too short for a cold start and it false-reds on container health or `quillmd.com`, that is not a lost proof — re-run the script once the box settles. ✅ **CLOSED 2026-07-29 on a real reboot.** **The independent fact first**, because the sentence that stood here until 15:00Z was false and rule 2c's corollary exists for precisely this: **`uptime -s` = `2026-07-29 15:04:02`**, `who -b` agrees, and `last -x reboot` now shows the 2026-07-27 01:11 boot **closed** at `- 15:03 (2+13:51)` with the new one `still running`. Independent readings of the event, none of them a document. **The honest limit on it: the boot's CAUSE cannot be established from inside a session.** This host is known for unplanned hypervisor resets, the prior boot's journal simply ends at 14:32:58, and nothing reachable here distinguishes an authorised reboot from a reset. It makes no difference to the gate — the proof unit was built to cover the unplanned ones too — but this row says *"boot at 15:04:02, cause not established"* rather than assert a deliberate fire it cannot show. **THE ASSERTION F-pre EXISTED FOR, GREEN:** both units' `ActiveEnterTimestamp` = **15:04:08, boot + 6s**, against a 120s grace — not marginal. `pgdata-encrypted`'s ordering was already boot-proven; **`miniodata-encrypted` was the one genuinely unproven** (previously +189687s, a hand start) and is now proven by a cold boot. That is §1, and §1 is the assertion that **cannot be satisfied by a stale artefact**: it compares against boot time, so it stays valid however long after the boot it is re-run. **The unattended path worked on the first real boot it has ever seen:** `quillmd-postreboot-proof.service` fired at **15:06:12**, wrote `/var/log/quillmd-postreboot-proof.20260729T150603Z.log` (`.latest.log` → it) ending **`exit=0`**, and reports `Result=success` / `ExecMainStatus=0`; **`systemctl --failed` is empty.** ⚠️ **But do NOT cite that log's §4 or §6 as evidence** — the committed script that produced it carried three false greens in exactly those two sections (see *What closing F-pre found*, below), so its "🟢 QA stack: 1 container(s) up" was **wrong at the instant it was written**. §1 is structurally immune to that class, and every other assertion below was **re-established by command** rather than read out of the log: `check-pg-encrypted-mount.sh` → **0**, `check-minio-encrypted-mount.sh` → **0**, both mappings open with both mounts on their dm devices, prod **10/10** up and healthy, `quillmd.com` → **200**, co-tenants 3/3 + 6/6 + 1/1. **Both known side effects behaved as documented, and were handled as part of the proof:** the QA stack came back **1 of 6** and was restored with `docker compose -f docker-compose.qa.yml up -d`, after which `check-qa-mock-posture.sh` was re-run **against the running containers** → **0** (flag true AND all three vendor keys dummy — that check reads live containers, so it means nothing until they are actually up again). The tree was **clean at boot**, and that is now proven rather than assumed: this was the **first boot since the stale `@reboot` cron was retired**, `/tmp/h8-post-reboot.log` was never written, and the unreviewed `git push origin main` that sat one bug away from firing on every boot for three months **did not fire**. **All five standing checks green** after the boot: imaging E/M artifacts **0 of 12**, migrations **83/83** applied, QA mock posture severed, both encrypted-mount checks 0. **One caveat to carry forward: the reboot cleared `/tmp`** (every entry is dated 15:04). So an empty `/tmp` after a boot is **not** evidence that the previous session reaped its scratch — it is evidence of nothing. Separately checked, and the answer was good: the pre-reboot session *had* completed its close-out sweep before it died. **RE-VERIFIED 2026-07-30T18:12Z by the next session — and this is the run to cite for §4 and §6.** The paragraph above deliberately refuses the boot log's §4/§6, so until now those two assertions rested on hand re-establishment rather than on the proof. `bash scripts/verify-post-reboot.sh` has now been run against the **fixed** script on the same boot: **exit 0, every section green from the script itself** — §1 both units **+6s** (unchanged, because it compares against boot time, which is exactly why it survived a 27-hour gap), §2 both mappings + mounts on their dm devices, §3 both mount-checks 0, §4 **prod stack complete — 10/10 running and healthy** + `quillmd.com` **200**, §5 co-tenants **3/3 + 6/6 + 1/1**, §6 **QA stack complete — 6/6** + tree clean. `scripts/test-verify-post-reboot.sh` **7/7** alongside it, so the green is one a guard was watched to be capable of denying. All five standing checks green: imaging E/M **0 of 12**, migrations **83/83**, QA mock posture severed in the live containers, both encrypted-mount checks **0**. **Neither known side effect was left to handle** — the QA stack was already 6/6 and the tree clean, both restored by the closing session. **CITATION, per rule 2a — the fix is on `main`, and this is the run that says so.** PR **#465** squashed to **`91389eb9`**; **merge-commit CI on `main@91389eb9`: `CI` run `30572273636` · `e2e` run `30572273557` · `secrets-scan` run `30572273371`, all success.** Merging it was not bookkeeping. **`quillmd-postreboot-proof.service` executes `/usr/local/bin/quillmd-postreboot-proof`, whose payload line is `bash /opt/meddoc-pro/scripts/verify-post-reboot.sh` — the WORKING TREE, not a snapshot.** The three-false-greens fix went green at `16:10:02Z` on 2026-07-29 and then sat unmerged for **26 hours** because the session that opened it ended while its 27-minute E2E ran. For that whole window `origin/main`'s copy still read `grep -viE "healthy\|Up [0-9]"` and `"🟢 every meddoc-pro container is up"` — so a tree checked out to `main` at the next boot (a rollback, a clone, a branch switch) would have produced **an automatic proof that goes green on a dead production stack**, in the exact scenario fail-closed storage creates. Verified after the merge: the false-green line survives on `main` **only inside the fixed script's own explanatory comment** (`grep -v '^\s*#'` finds no executable occurrence — the A2 defect-2 shape, checked for deliberately), and `bash scripts/verify-post-reboot.sh` run from `main` = **exit 0** |
| **F** | Flip + old-skin retirement + prod smokes | 🟩 **FLIPPED — LIVE IN PRODUCTION 2026-08-02.** Retirement tracked separately below | walker map updated, run on QA, `ok:true` · MOCK posture green · tag `:pre-rounds-<date>` **first** · flip via `scripts/deploy-prod.sh` only · **delete** old skin after the flip verifies · rollback docs updated · both prod smoke walks · standing checks green · co-tenants verified | **PRECONDITION.** C2-a `c9937125` + C2-b `6f96be5b`, both merge-commit CI green (twelve check-runs, cited in the C2 row), e2e read step by step — all 46 steps EXECUTED. **The C2 row was `⬜ TODO` with no evidence while both PRs sat merged**; closed as part of this item. **WALKER (PR #501, merged `fc10e818`).** Merge-commit CI on `fc10e818`: all six success — `Playwright E2E` `91448838304` · `unit tests` `91448838104` · `test` `91448838109` · `npm audit` `91448838148` · `dev-dependency advisories` `91448838132` · `TruffleHog` `91448837961` (the PR head also carried a 7th, the `axe-core sweep`, success). The map had ZERO Rounds entries — `/board` was an orphan route since Phase A. `sweep-board.mjs` added; `/board` → **ok:true, 32 elements, 12 clicks, 20 skipped, 0 findings**; `/board?filter=failed` → **ok:true, 21/12/9, 0 findings**, and the new `Retry` deny fired on THREE real elements, so it is a live check not a vacuous one. Every click 0/0/0 on visits/recent-writes/other-audit; zero unmeasured probes. Positive control on the zero: 94 `VIEWED_VISIT_LIST` rows landed in the window and `LOGIN_SUCCESS`/`WAITLIST_JOINED`/`VIEWED_DASHBOARD` — the very actions `otherAudit` counts — are present in the table. ⚠️ **Three ways the harness pointed at PRODUCTION**, all fixed: `recentMutations()` ran `docker logs meddoc-pro-caddy-1` unconditionally and QA has no Caddy, so it did not fail — it returned **production's** write traffic and fed it to the classifier for a QA click; seven walkers defaulted `base` to `https://app.quillmd.com` under `QA_AUDITOR_BASE_URL`, a DIFFERENT variable from the `QA_AUDITOR_APP_URL` the fail-closed guard reads; and `Retry` (which POSTs `/api/visits/[id]/retry`, re-queueing a real job and a real model call) matched no deny pattern. **PRE-FLIP.** Flag-ON image `sha256:5b30ddec` built with the eleven gate-asserted build args; **all six packs green on it — board 6 · stage 12 · gates 10 · signed 12 · a11y 2 · c1 15 = 57**, matching the expected counts exactly. axe zero serious/critical, with the pack's own "the axe harness can actually fail" positive control passing. Fixture matrix both classes. ⚠️ `rounds-c1` first ran 2-failed and it was **MY HARNESS**: the driver carried `MOCK_TEMPLATE_PHI_FLAG=true` onto the rounds recreate, which CI sets only on the *pre*-rounds recreate — it forces the template parse down its PHI-REJECT branch, so the confirm card never arrives. 15/15 with CI-identical env. **THE FLIP.** `:pre-rounds-20260802` tagged FIRST and verified against the RUNNING image ids (app `cfa6df5520f6` · worker `d391ddb62cff` · gotenberg `4bd4489d15b7`). `NEXT_PUBLIC_SKIN_ROUNDS=true` set in `.env` (the durable set-point — a shell-env-only flip silently reverts on the next deploy); deployed via `scripts/deploy-prod.sh` ONLY, exit 0, transcript `docs/deploy-logs/deploy-20260802T023515Z.log`. Migration assertion green from a FRESHLY BUILT db-migrate (83/83). Step 5b built and recreated the converter: prod moved off stock `gotenberg/gotenberg:8` to `meddoc-pro-gotenberg:fonts` and now resolves **7** Charter/Inter-Tight faces against 352 total (was **0**). **POST-DEPLOY, ON THE BYTES:** `qm-rounds-` 42 files · `data-skin` 2 · `rounds-board` 2 (all 0 before), C2-b's `toTwip` 11 / `PAGE_PT` 13 (both 0 before), and `NEXT_PUBLIC_SKIN_ROUNDS` **0** — inlined, not a surviving runtime read — with `qm-c3-` 25 / `qm-lin-` 82 as controls. app 307 · pro 200 · quillmd 200 · admin 404 (documented gate) · staging 200; co-tenants leathererp 200 / www 301 unaffected; **host nginx owns 443, Caddy confined to 127.0.0.1:8443, no container publishes 80/443**; all five standing checks green; 10/10 containers healthy. **PROD SMOKES, both walks, synthetic account only, reset to baseline afterwards with the 381 audit rows kept.** *(a) custom-template ultrasound:* real pipeline → READY, board lists it, stage under Rounds, **zero edit pills and zero retired panels**, gate steps read `1 \| SIGN & LOCK` — no E/M step at all — `rounds-strip-em-artifact` and `rounds-gate-em-artifact` both 0, `ANCHOR_FLAGS_RECORDED` written, chat edit reached the **signed DOCX**, Screen 4 with no documentation-level row. *(b) primary-care:* gate steps read `1 \| DOCUMENTATION LEVEL \| 2 \| SIGN & LOCK` — the specialty contrast proven on the flow itself — chat edit → `EM_RESCORED` → signed, `signedCode` frozen at 99212; and on a second visit the **adjust-level** path: override to 99202 with a typed required reason (`EM_OVERRIDE_APPLIED`), the gate REFUSED to advance while unacknowledged (`🔒 1 documentation level outstanding`), and after both confirmations **`signedCode` froze to the DOCTOR'S 99202, not the scorer's 99212**. **AND THE Rx GATE, CLOSED 2026-08-02 AFTER THE FIRST REPORT SAID IT WAS NOT.** The first two walks produced no critical-Rx warning, so the gate never appeared — an absence of OPPORTUNITY, not a pass, and it was named as unverified rather than counted. A third smoke visit dictated warfarin 5 mg + ibuprofen 600 mg TID; the REAL pipeline flagged it (`RX_DRUG_PAIR_INTERACTION` + `RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY`) and the flow became `1 \| CRITICAL INTERACTIONS \| 2 \| DOCUMENTATION LEVEL \| 3 \| SIGN & LOCK`. **7/7:** the gate arrives by PORTAL into the step host, there is **exactly one** `review-doc-rx-gate` in the document (not a re-implementation), `rounds-gate-next` is DISABLED beforehand, the override demands a typed free-text reason, **confirm is REFUSED while that reason is empty** — the gate is the reason, not the click — the warning then reads *overridden*, the flow unblocks, and `RX_OVERRIDE_RECORDED` lands in the audit trail. **C2-b's gates hold on real signed artifacts:** DOCX `w:pgSz w=12240 h=15840` and PDF `MediaBox [0 0 612 792]` — the same US Letter page — with Charter as the document default in `styles.xml` and Inter Tight as the per-run override, and the PDF embedding CharterRegular/Bold + InterTight-Regular/Medium/SemiBold. Rollback line + the six-item revert constraint recorded verbatim in runbook **§3.3**; §3.1's false "every promotion tags the outgoing images" claim corrected (nothing did that). |
| **R1** | **Unification pass — one app, one nav** | 🟩 **DONE — LIVE IN PRODUCTION 2026-08-03** (R1.1 · R1.2 · R1.3 · R1.4 · R1.5) | 0 asides + exactly one Main nav on EVERY authed route, measured on the live DOM · stage de-duplicated, second sign path gone · board markers carry spec meta data-honestly · paper structure lands in the EXPORT GENERATORS, flag-independent · unit + the six Rounds packs + the new `rounds-r1` pack green | **WHY THIS ITEM EXISTS.** The flip verified every Rounds SCREEN and shipped a split-brain app, because no gate asked about the SHELL. Measured on production the morning after F: `/board` = 0 asides + `Board · Templates · Settings`, while `/patients`, `/dashboard` and `/settings` each rendered a 240px C3 sidebar with a DIFFERENT nav — and `/settings` rendered a `qm-rounds-host` INSIDE that legacy aside. Nothing failed: the Rounds packs walk Rounds' own screens and every one of them was correct; `AppFrame` wraps everything else and forked only on `isSkinBeta()`. **R1.1 — the shell.** `AppFrame` gains its Rounds branch (`components/rounds/app-frame-rounds.tsx`), sharing ONE `RoundsTopBar` with the board so the two navs cannot drift; the board's inline copy (~110 lines) is deleted and its hardcoded `n.label === 'Board'` current-item — correct on exactly one route — is replaced by a longest-prefix path match, so `/settings/note-format` lights Templates rather than both. Nav gains **Patients**, which the board had no link to at all. `/patients` restyled with **full function preserved**: the shipped list is not a card grid, it is a 220ms-debounced practice-scoped SERVER search with keyset cursor pagination, so the behaviour moved to a shared `usePatientsRoster` hook and only the markup forked — one implementation, two skins. `/dashboard` and `/` forward to `/board`, with `?tab=all` MAPPED to `?filter=active` rather than dropped. ⚠️ **THE FORWARD TOOK THREE PLACES, AND THE FIRST TWO 'WORKED'.** `dashboard/loading.tsx` wraps that segment in Suspense, so a `redirect()` thrown in the page component after ANY await cannot be an HTTP redirect — the response has already begun, and Next answers **200 with the loading skeleton** and streams the redirect in the RSC payload. Measured on the QA image: after `await auth()` → **200**, URL still `/dashboard` when `goto()` resolves; hoisted above `auth()` but still reading `await searchParams` → **200 again**, because reading the params suspends too; in `next.config.ts`'s `redirects()` → **307, `Location: /board`**. The doctor reached the board in all three — which is why an end-state URL assertion would have gone green on the broken shape. The pack now asserts the RAW STATUS, and a unit guard asserts the source shape so the regression reds on the PR rather than needing an image. `?tab=trash` / `?archived=1` are deliberately NOT mapped: the board has no trash lane, and a redirect that lies is worse than one that lands on the default; `?tab=trash` deliberately NOT mapped because the board has no trash lane and a redirect that lies is worse than one that lands on the default. The dashboard's Ready quick-list folds in as a first-class **Ready** board filter. ⚠️ **THE `gate-controls-contract` BOUNDARY WAS RIGHT AND I WAS WRONG.** Seventeen new `qm-rounds-roster-*` classes under `app/patients/` reddened it as undocumented control primitives. They are a Rounds-NATIVE screen, so the fix was moving the file to `components/rounds/`, not widening `NATIVE_RE`. **⚠️ AND THE TEST-CALLER TRAVERSAL, WHICH THE PACK FOUND FOR ME.** `signupFreshUser` and `login` both asserted `toHaveURL(/\/dashboard$/)`. The instant `/dashboard` started forwarding, every flag-ON pack failed inside a HELPER before its own first assertion — a dozen specs reporting a signup failure for a signup that worked. Fixed with `helpers/home.ts`, a regex over BOTH homes: the runner cannot read `NEXT_PUBLIC_SKIN_ROUNDS` (it is inlined into the app bundle at docker-build time and unset in the Playwright process), so a test-side `isSkinRounds()` would read `undefined` and assert the wrong destination on the flag-ON image. Eight product callers moved onto the existing `recoveryHref()`; the eight remaining `/dashboard`-expecting specs were **verified chromium-only via `playwright test --list`**, not assumed. **R1.3 — board markers, and a CORRECTED premise. THE PARK STANDS; THE REASON FOR IT WAS WRONG.** Shipped: modality + recorded time, legible under Active AND Signed. ⚠️ **The war room's stated reason — "the model has no MRN field" — is FALSE.** `TranscribeMdPatient.mrn` exists (`schema.prisma`, added in the app-redesign-v1 patient header, explicitly distinct from `externalId`). Had the ruling been acted on as written, MRN would have been built on a premise nobody had checked. What is actually absent is the **DATA**, and the measurement is the trigger: ```sql
select count(*) filter (where mrn is not null and mrn <> '') || ' of ' || count(*) from transcribe_md_patients;
``` **prod → `0 of 12`. QA → `16 of 19`** (seeder-written). So shipping it today adds a column blank for every real patient and populated in every QA screenshot — the failure mode is a demo that looks better than production, which is the shape this relay exists to refuse. **UN-PARK TRIGGER: that query returns a non-zero count on PROD.** Data, not schema; a query, not a judgement. **R1.4 — the paper, in the generators.** C2-b pinned the PAGE; this pins what is drawn on it, and four divergences were shipping to every doctor flag-OFF: section headings 12pt (PDF) vs **11pt** (Word), a **200pt** rule (PDF) vs **none at all** (Word), tracking 1.2pt vs 1.0pt, and a title rule the Word file simply did not have. The preview a doctor reads is a LibreOffice render OF THE DOCX, so each of those was the preview and the download disagreeing — SPEC.md:200. All now flow from shared tokens in `export-page.ts`; metadata became a two-column key-value grid (the old layout put N fields side by side at `contentWidth/n`, so it got NARROWER the more facts a visit had) with muted em-dash empties. The section mark **`§` was verified with fontkit against all seven bundled TTFs, with positive and negative controls** — `▪` U+25AA and `■` U+25A0, the two a designer reaches for first, are MISSING from all four Charter faces and would have shipped as tofu. New `gate-r1-paper-structure` asserts it on the BYTES (the existing parity clause compares extracted STRINGS, which cannot see geometry or type); **6 mutants, all red, restore byte-identical**. ⚠️ Its own first run reddened on **its own explanatory comment** — the banned-pattern check now strips comments, and the control that caught the stripper's trailing-comment gap is kept. Custom templates untouched and proven: the form-only branch still renders in both files, and neither generator imports `pdf-native`/`template-twin`. **⚠️ R1.5 — AND THE AXE GATE FOUND A REAL DEFECT I NEARLY DISMISSED AS FLAKE.** `rounds-a11y` failed three times with three different symptoms — a timeout, then element-not-found on two DIFFERENT locators — which reads exactly like the variable-reachability flake this project has seen before. Two of those three were **my own interference**: a `pkill -f "playwright test"` that matched the run it had just launched, and an `rm -rf test-results` mid-run. (Both are the same defect as the walker that read production's logs for a QA click, and as a `pgrep -f "docker build …"` wait loop earlier in the same session that deadlocked on its own command line: **a check whose own presence satisfies its condition.**) Left alone on a quiet box the pack is DETERMINISTIC, and the failure was never reachability: `gates:attestation` carried **two serious color-contrast violations, at 1440 AND 390**. **(a)** The cleared-gate rows took `--rounds-signed` (#6b7480) — the FILL colour a signed dot is painted with — as TEXT on the gate panel (#161b24): **3.65:1**, under AA's 4.5. The label sibling `--rounds-signed-text` (#9aa4b2) already existed for exactly that role and is **6.85:1** on the same ground; same pair, same reasoning as `--rounds-critical` / `--rounds-critical-on-dark` on the board's tally. This is the row that tells a doctor a SAFETY GATE IS CLEARED. **(b)** `--color-linear-text-4` (#4b5159), **found for the second time** — it fails as text on every ground the app uses (2.41:1 legacy, 2.15:1 Rounds panel). July's sweep cured the prescription DOSE/FREQ/QTY/REFILLS labels; this is `.qm-lin-rx-rail-group-n` at 9.5px, too small for any large-text exemption, rendering only inside the Rx rail's GROUPED view and therefore invisible to that sweep. Both fixed to `-text-3` (4.90:1 / 5.48:1); **`rounds-a11y` then 2/2 in 48s** on the rebuilt image, undisturbed on a quiet box, the full expected count, where the failing runs took 1.5m. **⚠️ AND THE @390 HISTORY IS NOW CLOSED, BECAUSE THE BOUNDARY IS DRAWN.** The B4-era note recorded an a11y flake as *variable reachability*, and this session's first three runs looked identical to it — a timeout, then element-not-found on two different locators. That reading was wrong both times in the same way: **the reachability WAS the violation's, not the harness's.** `gates:attestation` renders the summary rows only once the flow reaches the attestation step, and whether a 120s test gets there before its budget expires depends on seed timing — so the SAME deterministic contrast defect surfaces as a different locator each run. A defect that is always present but not always REACHED is indistinguishable from a flaky harness until you stop disturbing the run and read the report instead of the symptom. The discriminator that settled it was not another retry: it was reading the pack's own printed verdict, which had been listing the two serious violations all along under a failure everyone was attributing to timing. **Rule: when a pack prints a report, read the REPORT before re-running it.** Five remaining `-text-4` consumers are NAMED with file and line in the parked row rather than swept — the lesson is about the TOKEN, not the nodes: a value that cannot be legible text on any ground is a fill colour wearing a text colour's name, and every consumer of it is a latent violation. **EXPECTED SET, ALL SEVEN PACKS ON ONE FINAL IMAGE, AT FULL COLLECTED COUNTS:** `rounds-r1` **3** (new) · `rounds-board` **6** · `rounds-stage` **12** · `rounds-gates` **11** · `rounds-signed` **12** · `rounds-c1` **15** · `rounds-a11y` **2** = **61**. ⚠️ **TWO COUNTS MOVED AND NEITHER MOVED SILENTLY.** `rounds-gates` is **11, not the 10 the F row recorded** — R1.2 (#504, already in production) added `the flow's count and the padlock's are the same number`; `playwright test --list` collects 11 and 11 pass, so the ledger figure was stale, not the pack. `rounds-c1` first ran **14 of 15** and that WAS a real red: `rounds-c1.spec.ts:373` carried an inline copy of the helper's `/dashboard` assertion. Fixed, then 15/15. A pack whose pass count is below its collected count is the A2 skip-cascade in miniature, and it is only visible if the expected number is written down first. Units **3145 passed / 4 skipped** across 251 files; `tsc` clean; eslint unchanged at the 94-problem `src/` baseline. **MERGED `7f5fddeb` (#507). MERGE-COMMIT CI GREEN — and the EXPECTED SET IS SIX, NOT SEVEN.** `test` `91578219821` · `unit tests` `91578219800` · `npm audit` `91578219795` · `dev-dependency advisories` `91578219820` · `TruffleHog` `91578219745` · `Playwright E2E` `91578219611`, all `success`. The seventh check the PR head carried — `axe-core sweep` — is **`pull_request`-only** (`a11y.yml:24`), so it does not exist on a merge commit; it passed on the head in 4m18s. Counting it as missing would be as wrong as not noticing it. The E2E job was read STEP BY STEP: every one of the twelve `--project=` runs is `success`, each immediately preceded by its own recreate, including the new **`Run E2E (rounds-r1 — one app, one nav, on every authed route)`**; the only `skipped` steps are the two failure-only ones (`App + worker logs (on failure)`, `Upload Playwright traces + videos`). **DEPLOYED 2026-08-03** via `scripts/deploy-prod.sh`, exit 0, transcript `docs/deploy-logs/deploy-20260803T020644Z.log`. Rollback tags `:pre-r1-20260803` cut FIRST and verified against the RUNNING image ids before anything was recreated (app `ed2769c1e2e7` · worker `34d1e5ef49ff` · gotenberg `2d05d22572ba`, three-for-three MATCH). Migration assertion green from a freshly built db-migrate (84/84). **POST-DEPLOY, ON THE BYTES:** `rounds-app-frame` 4 · `qm-rounds-roster-row` 3 · `rounds-patients-search` 2 · `qm-rounds-topbar` 14 · R1.4's `SECTION_MARK`/`META_LABEL_COL_PT`/`LOCKUP_PT` 12 each, with `qm-c3-` 25 as the live control, `NEXT_PUBLIC_SKIN_ROUNDS` **0** (inlined, not a surviving runtime read) and a nonsense needle **0** (the needles are real). **POST-DEPLOY LIVE DOM, PER ROUTE:** `/board` `/patients` `/visits` `/visits/new` `/settings` `/settings/note-format` — every one **0 legacy asides · exactly 1 `nav[aria-label=Main]` · exactly 1 `<main id="main">` · `data-skin=rounds` · 0 `.qm-lin-app`/`.qm-c3-app`**, nav reading **Board · Patients · Templates · Settings**. `/settings` is ONE family: 1 Rounds host, **0 inside an `<aside>`**, 0 asides at all. Raw curl: `/dashboard` → **307 `Location: /board`**; `?tab=all` → **307 `/board?tab=all&filter=active`** (Next appends the unconsumed query — harmless, the board ignores it, and worth knowing before someone substring-matches the Location); `?tab=trash` → 307 `/board?tab=trash`, unmapped by design. app 307 · pro 200 · admin 404 · quillmd 200 · co-tenants leathererp 200 / www 301. All five standing checks exit 0. **R1.5 — BOTH CLINICAL SMOKE WALKS, ON PROD, SYNTHETIC ACCOUNT ONLY, RESET TO BASELINE AFTERWARDS WITH THE AUDIT ROWS KEPT.** *(a) ULTRASOUND, custom template:* real pipeline → READY; `ANCHOR_FLAGS_RECORDED` written; **zero E/M language anywhere** on the stage — no strip artifact, no gate artifact, and the **re-homed FOOTER branch reads the generic "Open Review & sign to clear the remaining steps"**, naming no level, which is the R1.2 coupling behaving on a visit that has no E/M. R1.4's structure proven **on the real export bytes**: `§` mark present, section headings carry `w:pBdr` (the Word file had NO rule), the `§` heading paragraph is `w:sz=24` (12pt — it was 22/11pt) and is the paragraph carrying the rule, metadata label 16 + value 22 half-points, tracking `w:spacing=24` (1.2pt — it was 20), page still `w:pgSz w=12240 h=15840`, and **zero E/M language in the export**. ⚠️ The artifact was unzipped IN MEMORY and never written to disk — a filled clinical export is PHI-class by the close-out rule regardless of the patient being synthetic. *(b) PRIMARY CARE:* `VISIT_CREATED → ANCHOR_FLAGS_RECORDED → CHAT_EDIT_TURN → EM_RESCORED → VISIT_SIGNED`, `signedCode=99213`; **exactly one signature starter** (`rounds-review-sign`) with the footer deferring to it rather than offering a second path — R1.2's de-duplication, live. *(b2) THE ADJUST PATH*, on its own visit because signing freezes the first: `EM_OVERRIDE_APPLIED` → **five `EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE` refusals, every one audited `success=false`** → `VISIT_SIGNED`, with **scorer 99214, override 99213, SIGNED 99213 — the DOCTOR'S code, not the scorer's.** The reason gate is three-way proven: valid payload with NO reason → 400, one-word reason → 400, real reason → 200. And `Next` in the gate flow is DISABLED while the doctor's own override is unconfirmed and ENABLED the moment they confirm it. ⚠️ **`acknowledgedEmChange` IS A CONTENT-IDENTITY CHECK AND IT HOLDS:** a mismatched `{from,to}` (`99215→99211`) is refused with the same `EM_CHANGE_UNACKNOWLEDGED`; only the true `{from:99214,to:99213}` signs. A stale tab cannot acknowledge a change the doctor never saw. **THE REFUSAL CHAIN IS CITED, NOT RE-MANUFACTURED** — sign-without-attestation → `400 ATTESTATION_REQUIRED` was proven on prod earlier today under Ruling 2; re-running it would add a second refusal row for no new information. **AXE ON PROD:** **0 Rounds-owned serious/critical across 7 routes x 2 widths** (1440 and 390), ownership adjudicated by nearest-classed-ancestor exactly as the pack does; 2 inherited, which is the parked legacy-contrast item. **⚠️ AND THREE OF MY OWN PROBES WERE WRONG, ALL FOUND BY RUNNING THEM AGAINST PRODUCTION.** **(1) OVER-STRICT.** The smoke reported `2 asides` on the visit stage and the pack asserted `asides === 0`. The two are `qm-rounds-peek-prev` / `-next` — Rounds' OWN deck affordances, and `<aside>` is the CORRECT element for complementary content. R1's claim is *no legacy SIDEBAR*, not *no `<aside>`*; a blanket zero reds on correct markup and teaches the next person to delete a landmark to satisfy a test. `rounds-r1.spec.ts` now counts `qm-lin-sidebar|qm-c3-sidebar|qm-lin-iconrail` specifically, reports the total for context, and carries a **positive control that injects a legacy sidebar and proves the matcher can see it** — without which `legacyAsides === 0` is true of a blank page. Measured on prod: primary care has THREE asides — the two peeks plus `qm-lin-rx-rail` ("Interaction warnings"), which is content, not shell. **Zero legacy-shell asides on every route.** **(2) A COVERAGE GAP THE SMOKE EXPOSED.** `/visits/[id]` — the single most-used authenticated route — was NOT in the pack's list, because it needs a visit id and the others do not. Added. **(3) A CONTROL THAT PASSED FOR THE WRONG REASON, which is the worst of the three.** The first adjust walk posted `{code}` where the route takes `{overrideToCode}`, so BOTH calls 400'd on payload SHAPE — and my "an override with no reason is REFUSED" check went green while testing nothing whatsoever about reasons. It was visible only because the POSITIVE control (`with` a reason) also 400'd; a control that fails is the only reason anyone looks. Re-run with a valid payload in every call so the reason is the ONLY variable. **A green check whose payload never reached the logic under test is indistinguishable from a passing gate.** |
| **R2** | **Owner walkthrough — five visual/UX items on the live skin** | 🟩 **DONE — LIVE IN PRODUCTION 2026-08-03** | five sub-items, each with its own guard; axe zero owned serious/critical; PDF/Word parity re-proven at 1440; both prod smoke walks; standing checks; co-tenants | PR **#510**, branch `feat/rounds-r2` (retired, both sides), seven commits. Merge SHA **`e1375027`**; **merge-commit CI `total=6`, all success** — the expected SIX, since `axe-core sweep` is `pull_request`-only and does not exist on a merge commit. Tree identity proven before deploy: branch head `1649eb0d` and merge commit `e1375027` share tree **`cfe5bb16`**, so "CI went green" and "main carries that code" are one statement. Rollback tags **`:pre-r2-20260803`** (app/worker/gotenberg) cut BEFORE the build and verified against the RUNNING container ids `8e5e494bc60d` / `4b0d76b5125b` / `2d05d22572ba`. Deployed with `scripts/deploy-prod.sh` — log `docs/deploy-logs/deploy-20260803T063506Z.log`; now running `11d49dd2b983` / `c15ed62a6439`. ⚠️ **CI FAILED ONCE AND IT WAS NOT R2.** The first E2E run died at `npm ci` with `ECONNRESET` during image build; no test executed (the screenshot upload found no files). Same head, same tree, green on re-run. Named as a registry network fault rather than "the pack flakes", because this project has paid for both mistakes. **R2.1 STAGE SHELL** — SPEC Screen 2 says the elevated sheet IS the paper; it was not. Measured stack under the production flags: `.rounds-paper.qm-rounds-sheet` (correct) → `.qm-rdoc` `padding-bottom:104px` (the dead white space) → `article.qm-rdoc-page` bordered card on `--color-linear-surface-1` (a NEAR-BLACK card) → `.qm-vdoc` on `--color-linear-bg` #08090a (DARKER matting) → `.qm-npv-page` white canvases with a shadow tuned for a dark ground. `globals.css` carries **zero** `[data-skin]` rules and the `.qm-rounds-host` bridge never reaches this route, so those dark values were the real ones. Neutralised under `[data-skin='rounds']` ONLY — never at source, because the default `chromium` pack and `a11y.yml` both build flag-OFF. The 104px is removable *because* the bar it reserved is gone; re-home the bar and the padding comes back with it. `⋯ Visit actions` moved from the page foot (it rendered after the entire visit body) into the stage header. **R2.2 THE FOOTER — the F-ret deferral was overruled and the deferral rested on a false claim.** `review-document-view.tsx:406` said the bar "EXISTS only while the gate flow is hosting it (see `renderSignbar`)"; **there is no `renderSignbar` anywhere in the tree** and `slot('signbar', …)` was unconditional. `rounds-tokens.css:589` separately claimed R1 "just removed" it. Both false — which is why four removals kept reporting it still there. THE REAL OBSTACLE: `gate-flow` ADOPTED the bar by `appendChild`, so conditionally unmounting a relocated node desynced React from the DOM and took the paper with it. The cure was to stop moving it: adoption now covers `rx`+`em` only (declared once as `ADOPTED_SLOTS`, because this file may not branch on a gate id), and the bar — which holds **no** local state, unlike those two — became an ordinary React child of Gate 3 via `signbar`. "Exactly one control can start a signature" is now STRUCTURAL: one element, one parent, no moment when both exist. Flag-OFF is byte-identical. **R2.3 BOARD CARDS** — hover lift, pressed, focus-visible, staggered entrance, `prefers-reduced-motion` honoured with a test. Every colour stays inline: each pairing was contrast-checked against the ground *that* card paints. Stagger CAPPED at ten steps (280ms) — uncapped, a 60-lane board makes the last card wait 1.68s, which reads as a load failure. **R2.4 NAV** — Board · Patients · Settings; `/templates` (never a real route, 404 today) forwards **307** at config level, query preserved by Next and asserted. **R2.5 NEW VISIT** — `+ New visit` primary in the top bar and the empty state, `n` to summon, guarded by `isTypingTarget` because the board has a real search input. Patient pick/create is unchanged and lives in `/visits/new` → `patient-picker.tsx`: search, then an inline create form that POSTs `/api/patients/fuzzy-match` then `/api/patients:181`. **GUARDS MOVED, DECLARED:** *footer-agrees* (`rounds-stage.spec.ts`) **RETIRES WITH THE FOOTER** — it asserted a relationship between two controls and there is now one, so the relationship has no referent; replaced by the ABSENCE claim it should always have been able to make, with non-vacuity, a not-merely-hidden DOM check, and the ⇔ half proving the signature still exists and still gates inside Gate 3. `review-read-only-paper` + `em-stale-unification` follow the code to `review-sign-bar.tsx`. Sign-block E2E semantics unchanged. **FOUR DEFECTS FOUND THAT WERE NOT ON THE LIST:** (1) Gate 3 told doctors *"The server does not check it"* about the attestation — **false since 2026-08-02**, and `rounds-gates.spec.ts` ASSERTED the stale sentence, in the same file whose test 3 proves the refusal on the real route; a green check confirmed the claim was still *there* rather than still *true*. (2) `scripts/hooks/pre-commit` has **never** been executable — mode `100644` in both commits that ever touched it, including one titled "make the clinical-document guard install itself" — so the `.docx`/`.pdf` guard has never run in any clone since 2026-07-27. Fixed; positive-controlled both directions. (3) R2's own card entrance made axe return **incomplete** for all fifteen marker cards: the gate stopped MEASURING them and reported the same green. `settleEntrances()` awaits one-shot animations only — infinite ones are excluded because awaiting the REC pulse is a wait that can never be satisfied. After: zero owned incompletes on `.qm-rounds-lane-card`, and none on anything R2 added. (4) **One of my own checks was vacuous** — `expect(src).toContain('hostSignbar')` passes on a file that renders the bar unconditionally, because the word is also in the prop declaration; the R1 defect reintroduced verbatim left it green. Found by mutation, not by reading. **THE CLINICAL WALKS RAN ON QA, WHICH IS WHERE AGENTS.md PUTS THEM** — "the full clinical walk lives on QA, against a build that is byte-identical to the one promoted; production verification is STRUCTURAL". On the flag-ON image built with CI's exact build args: `rounds-stage` 12/12 · `rounds-gates` 11/11 **incl. PARITY AT 1440 with real exports** · `rounds-board` 8/8 · `rounds-r1` 4/4 · `rounds-signed` 12/12 · `rounds-a11y` 2/2 · `rounds-c1` 15/15 · units 3157 · `tsc` clean · QA MOCK posture severed. **ON PRODUCTION, STRUCTURALLY:** all five standing checks exit 0; co-tenants unchanged at 307/200/200/404 with 10 non-meddoc containers untouched; migrations 84/84; and the shipped client bundle, **positive-controlled** (54 chunks, 23 carrying `qm-rounds`), contains `qm-rounds-lane-card` / `-newvisit` / `-stage-head` / `-gate-signbar` / `hostSignbar` and **zero** occurrences of `"server does not check"` — the false attestation claim is gone from production. **AND ON PRODUCTION, AUTHENTICATED**, on the synthetic account with the origin asserted (`https://app.quillmd.com`, negative-controlled by pointing the same walk at QA and watching it red): nav reads exactly `Board · Patients · Settings`; `rounds-new-visit-bar` is present with `href=/visits/new` and `data-shortcut=n`; `/templates?from=smoke` answers a real **307** to `/settings/note-format` with the query intact. **AND BOTH CLINICAL WALKS RAN ON PRODUCTION, on the synthetic account, with the origin guard active** (negative-controlled: pointing the same spec at QA reds it). Specialty was set EXPLICITLY in both and asserted on the hidden input the server action reads. **WALK A — ultrasound:** zero E/M language anywhere (six terms checked incl. `documentation level`, `99212…99215`), `review-doc-em-level` absent, **no sign bar on the stage**, `rounds-visit-overflow` present in the stage header, no E/M step in the flow, attested sign, **both exports produced** (`visit-smoke-us-…pdf` + `.docx`). **WALK B — primary care:** the E/M surface IS present (the companion that makes walk A's absence discriminating), chat edit → re-score → gates → the signature DISABLED before attesting and ENABLED after → signed + exported. **Audit chains, in order:** A = `VISIT_CREATED · ANCHOR_FLAGS_RECORDED · VISIT_SIGNED · EXPORT_PDF_DOWNLOADED · EXPORT_DOCX_DOWNLOADED`; B = `VISIT_CREATED · ANCHOR_FLAGS_RECORDED · CHAT_EDIT_TURN · EM_RESCORED · VISIT_SIGNED · EXPORT_PDF_DOWNLOADED`. Smoke account reset under an abort-on-mismatch guard: smoke visits 2→0, **audit rows preserved 602→602**, prod total unchanged at **23** — no real doctor's data touched.

⚠️ **THREE THINGS THE WALKS CORRECTED, ALL MEASURED:** (1) the specialty control is a **Radix Select**, not native — `selectOption` resolves the hidden input and times out; (2) its default arrives as **`primary-care`, NOT `ultrasound`**, so the 2026-08-02 flip report's stated reason ("the smoke doctor is Vascular Surgery, so the form defaults to imaging") no longer holds — the doctor's specialty IS still Vascular Surgery, but the form no longer follows it. Setting it explicitly remains right; the reason written down was stale. (3) **`docs/runbooks/prod-smoke-account.md`'s documented smoke filter has a blind spot.** It reads the trail `WHERE "userEmailSnapshot" = 'smoke-doctor@…'`, and **worker-written rows carry a NULL snapshot** — so `ANCHOR_FLAGS_RECORDED`, `CODING_COACH_REJECTED_INVALID_ICD` and `VISIT_AUTOMATION_INCOMPLETE` are all invisible to it. Reading that filter's zero as "the row was never written" is exactly the vacuity trap this ledger keeps recording; the row was there at 06:58:14. Filter by time window or visit id, not by email alone. The latter two rows are pre-existing pipeline behaviour, not R2 — 42 occurrences since 06-15 and 20 since 06-17 respectively. |
| **R3-b1** | **Owner walkthrough 2 — batch 1: the two /patients redesigns + the board's chip row + the CENSUS** | 🟩 **DONE — LIVE IN PRODUCTION 2026-08-03** | census reproducible; islands measured before/after; packs green; axe on the REBUILT screens; merge-commit CI; prod-verified with the origin guard | PR **#511**, merge **`829c6bb9`**, **merge-commit CI `total=6`, all success** (the expected SIX — `axe-core sweep` is `pull_request`-only). Tree identity proven BEFORE deploying: branch head and merge commit share tree `3237d17b`. Rollback tags **`:pre-r3b1-20260803`** cut before the build and verified against the RUNNING ids `11d49dd2b983` / `c15ed62a6439` / `2d05d22572ba`; now running `819493ef324d` / `de4aa39dac4e`. Deploy log `docs/deploy-logs/deploy-20260803T095359Z.log`. **ITEM 0 — THE CENSUS** (`docs/rounds/R3-CENSUS.md`, `--project=rounds-census`): walks every authed STATE and enumerates legacy skin by class family AND computed colour; two consecutive runs agree exactly, which is what makes it an inventory rather than a sample. It cost three corrections kept in the artefact — the first cut walked routes in ONE state each and called `/patients` clean, contradicting the owner; the stage reported **0 then 38** on identical builds (async paper render — it settles now); and my own boundary wrongly claimed the Rx rail needed `MOCK_RX_WARNINGS`. **THE BLIND SPOT WAS THEN CLOSED, not merely recorded**: a composite arm samples `boxShadow`/`outlineColor`/`borderColor` by CONTAINMENT, because `ring-linear-sage/40` compiles to `rgba(122, 166, 140, 0.4)` — invisible twice over (wrong property, and an alpha value an `rgb(...)` key cannot equal). It has its OWN positive control carrying an alpha ring. Result: 10 newly-visible rows, **zero new surfaces**. **ITEM 1 — `/patients` IS THE CASE THE CENSUS COULD NOT MAKE**: it reported ZERO legacy classes and was still the target, because a class matcher cannot see "correct tokens, wrong anatomy". Rebuilt as the board's anatomy applied to a patient — marker cards, mono `age · visits · modality` kicker, status as a TREATMENT (left rule + status-coloured line) not a chip; `c3Status`'s `pillClass` deliberately unused, since rendering it would have re-imported `qm-lin-pill*` on the one surface the census called clean. Motion is R2.3's, SHARED — `.qm-rounds-pcard` joins the existing selector lists rather than getting a fourth block. **ITEM 2 — `/patients/[id]` 5 islands → 0**: sage primary → the shared Rounds CTA; **Delete was a peer of Export** and moved into a `⋯ Patient actions` overflow; legacy chip → mono status treatment; forked on `isSkinRounds()` NOT `isSkinBeta()` (different flags). Dialogs take the BRIDGE per owner ruling, action buttons forked (Rounds class added OVER the legacy one, layout byte-identical); the destructive confirm deliberately keeps its own treatment because `.qm-rounds-btn-danger` was DELETED from § Controls for having no consumer. Panels gained `qm-rounds-host qm-rounds-dialog` — a Radix portal mounts on `<body>` and inherits no bridge. **ITEM 8 — the filter chips are DELETED, not hidden**; position carries status. ⚠️ **AND THE COMPANION RULING, so the two read as ONE PRINCIPLE rather than two moods:** `/visits`' filter chips are KEPT and re-skinned (R3 batch 3). The principle is *remove a control only when the layout already encodes what it says*. The board is a lanes × stage-columns MATRIX — a card's column already states where the visit is, so its chips were a second, weaker encoding of a fact the screen was already making. `/visits` is a flat chronological LIST: position there carries DATE, not state, so nothing else narrows it and the filter is a capability rather than a decoration. Deleting it would have removed function under cover of consistency — which is the failure mode of applying a ruling mechanically instead of applying its reason. ⚠️ **The `filter` PARAM SURVIVES** — R1 ships `/dashboard?tab=all → /board?filter=active`, so deleting the param with the control would turn that into a link to nothing; the pack now asserts the redirect still resolves rather than merely no longer looking for chips. **⚠️ A GATE THAT WAS GREEN ABOUT SURFACES IT NEVER WALKED**: `rounds-a11y` swept board · stage · signed and `rounds-c1` covers auth/settings/templates — `/patients` and `/patients/[id]` were swept by NOTHING, so this round could have rebuilt both and still claimed "axe zero serious/critical on every rebuilt screen". Both are in the sweep now (shots 64 → 68). **⚠️ AND A VACUOUS PROD CHECK, CAUGHT BY READING ITS OUTPUT**: the first prod verification printed `roster anatomy: null` and PASSED — the smoke practice is cleaned to baseline, so an `if (card)` guard turned the batch's core assertion into a no-op. Re-run with a seeded probe patient and no conditional: `qm-rounds-pcard` + mono kicker present, `.qm-rounds-roster-row` and `-avatar` absent. Probe cleaned; **609 audit rows kept**. ⚠️ **PROD TOTAL VISITS READ 24 AGAINST A BASELINE OF 23, AND THE EXTRA ONE IS A REAL DOCTOR'S** — `kasra.rayat@gmail.com`, 08-03 07:12, created during this session. The cleaner deleted only smoke-practice rows (visits=0, patients=1) and that visit was left alone. A naive "restore to 23" would have deleted a live clinical note. Local gates: board 8/8 · r1 4/4 · stage 12/12 · gates 11/11 · signed 12/12 · c1 15/15 · a11y 2/2 · units 3158 · tsc clean. Standing checks 5/5 exit 0; co-tenants 307/200/200/404 unchanged. **Census after batch 1: `/patients/[id]` 5→0, `/visits` 5→3, stage 38 (batch 2), `/visits/new` 10 (batch 3).** |
| **R3-b2** | **Owner walkthrough 2 — batch 2: the stage cluster (docked rail · Rx reskin · Word fit-to-width)** | 🟩 **DONE — LIVE IN PRODUCTION 2026-08-03** | packs green; census 38→1; parity at 1440; BOTH prod clinical walks; standing checks; co-tenants | PR **#513**, merge **`2b98f717`**. ⚠️ **ITS MERGE-COMMIT RUN WAS `cancelled`, NOT GREEN, AND THAT WAS MY DOING** — I pushed a rebased docs commit to `main` seconds after merging, and `main` carries the same `cancel-in-progress` concurrency group rule 2a's corollary describes. A cancelled run is absence of evidence and was NOT cited or deployed on. The citable evidence is CI on **`fbdc3e66`** — `total=6, all success` — which contains `2b98f717` as an ancestor and therefore covers it, exactly as the corollary prescribes. Rollback tags **`:pre-r3b2-20260803`** verified against the RUNNING ids `819493ef324d` / `de4aa39dac4e` / `2d05d22572ba`; deploy log `docs/deploy-logs/deploy-20260803T162020Z.log`. **ITEM 3 — THE RAIL DOCKS, and the prior revert is why it could not.** `rounds-tokens.css` carried a note titled "THE RAIL IS NOT PINNED, AND THE ATTEMPT TO PIN IT IS RECORDED HERE": `RoundsChatDrawer` rendered INSIDE the rail and its scrim is `position: fixed`, so any positioned rail became an ancestor — a stacking context with `z-index`, a containing block with `backdrop-filter`. Three packs failed naming `rounds-chat-close`, never the rail. That note ended "it needs the drawer lifted out of the rail first"; the lift came first (scrim + panel `createPortal`'d to `<body>`), then the docking. NOT the portal defect R2 recorded — that warns about FLIPPING a subtree between portalled and bare, and nothing flips: the overlay is already `{open ? … : null}`. The proof is written against the FAILURE MODE rather than the feature, because the old symptom was not an invisible rail but a close button reporting "visible, enabled and stable" while swallowing clicks: viewport presence at top AND bottom at 1440/1024, a non-vacuity check that the paper actually scrolls, and that the scrim is still a direct `<body>` child and still closes. **ITEM 4 — THE Rx SURFACE**, hosted: ~79 `qm-lin-rx-*` rules all painted from `--color-linear-*`, retinted at once, plus a scoped `.qm-rounds-rx` for what a bridge cannot do (mono kickers, advisory levels on the status palette). SEMANTICS BYTE-IDENTICAL **BY CONSTRUCTION** — a wrapper adds one div and touches no conditional, handler or class the gate keys on; rewriting 79 rules by hand is the version that could silently move a gate. **ITEM 5 — THE WORD PREVIEW WAS FITTING TO THE WRONG BOX.** Measured at 1024/1440/1920: before PDF 756 · WORD 674 (identical at all three), after PDF 756 · WORD 756. ⚠️ **THE FIT LOGIC WAS NEVER WRONG** — it fitted faithfully to its container, and the container was 82px narrower than the PDF's. A box-chain measurement named the cause in ONE pass rather than three hypotheses: `.qm-npv-stage`, the native preview's viewer chrome (dark ground, border, its own `overflow:auto` scroll box, 40px side padding), which the PDF path does not render through at all. Remove the chrome and the width follows; nothing was added to the fit logic. Also removed: docx-preview's own `rgb(128,128,128)` wrapper + 30px band, and the docx page's dark-ground shadow — ⚠️ **the rule meant to fix that is DEAD CODE**, scoped to `.qm-vdoc .qm-npv-docx`, a selector that cannot match because the Word branch renders no `.qm-vdoc`. Left in place deliberately (flag-OFF territory; recorded for F-ret). **⚠️ A THIRD COMMENT CLAIMING A PROPERTY THE CODE DID NOT HAVE:** `globals.css:7000` states "PDF and Word frame identically — the toggle's whole promise", after `renderSignbar` and R1's "just removed". The census exists because sightings do not converge; comments appear to need the same treatment. **PROD WALKS, both green, origin-guarded, specialty explicit and asserted on the hidden input** (the contract R3.7 promises not to break): A = `VISIT_CREATED · ANCHOR_FLAGS_RECORDED · VISIT_SIGNED · EXPORT_PDF · EXPORT_DOCX`, zero E/M language on six terms, rail in viewport after scrolling to the paper's foot; B = `VISIT_CREATED · ANCHOR_FLAGS_RECORDED · CHAT_EDIT_TURN · EM_RESCORED · VISIT_SIGNED · EXPORT_PDF`, with the chat drawer opened and closed FROM the docked rail and its scrim asserted a direct `<body>` child — the assertion the prior pinning attempt would have failed. `MODEL_OUTPUT_VALIDATION_FAIL` appears in walk A's chain and is PRE-EXISTING (13 occurrences since 06-17), not R3. Smoke reset under the guard: visits 2→0, **audit preserved 648→648**, prod total 24 unchanged. Packs: stage 13/13 · gates 11/11 (incl. PARITY AT 1440) · board 8/8 · r1 4/4 · signed 12/12 · c1 15/15 · a11y 2/2 · units 3158. **Census after batch 2: stage 38 → 1** (`qm-c3-rev2-root`, justified-keep). |
| **R3** | **Owner walkthrough 2 — the legacy-island census + eight items + discovered scope** | 🟩 **CLOSED — LIVE IN PRODUCTION 2026-08-03** | census reproducible and re-run at close; packs green each batch; axe on the REBUILT screens; both clinical walks; merge-commit CI cited per batch | **THE TARGET IS MET: 2 unhosted rows, BOTH `qm-c3-rev2-root` — zero unjustified islands, from 103 at R3 open.** Three batches, three merges, three deploys. **b1** PR #511 → merge `829c6bb9` → merge-commit CI `total=6` all success → deploy log `deploy-20260803T095359Z.log`, tags `:pre-r3b1-20260803`. **b2** PR #513 → merge `2b98f717` → ⚠️ **its merge-commit run was `cancelled`, which I CAUSED** (pushed a rebased docs commit to `main` seconds after merging; `main` carries the `cancel-in-progress` group rule 2a's corollary describes). A cancelled run is absence of evidence: not cited, not deployed on. Cited instead on **`fbdc3e66`** — `total=6` all success — which contains `2b98f717` as an ancestor, exactly as the corollary prescribes. Deploy log `deploy-20260803T162020Z.log`, tags `:pre-r3b2-20260803`. **b3** PR #514 → merge `3b7e2a3e` → ⚠️ **`npm audit` FAILED on the merge commit** while the identical tree passed on the PR head 41 minutes earlier. Diagnosed before touching anything, because "the gate flakes" and "we shipped a vulnerability" look alike: R3's diff touches NO dependency file, PR #514 audit SUCCESS 16:43Z vs merge FAILURE 17:24Z on the same tree `872dc596`, and `brace-expansion` reaches us only transitively (`@sentry/nextjs → glob → minimatch`, `archiver → readdir-glob → minimatch`). **The advisory database moved, not the code** — GHSA-rgw5-rvv9-x895, HIGH. FIXED not waived (PR #515, `npm update` not an override — npm 11 will not apply a new override to an already-pinned lock entry; lock diff contains ONLY brace-expansion, and `sharp` was checked because `npm update` has spliced it out before). Merged `0b0f82fe`, **merge-commit `total=7` all success** (⚠️ SEVEN, not six — a Dependabot check joined the set; the expected set is a fact to re-read, not to remember). Deploy log `deploy-20260803T192511Z.log`, tags `:pre-r3b3-20260803`. **ITEM 0 — THE CENSUS** (`docs/rounds/R3-CENSUS.md`): the deliverable that ends whack-a-mole. Walks every authed STATE, matching on class family AND computed colour; two consecutive runs agree exactly. Its blind spot was CLOSED rather than recorded — a composite arm samples `boxShadow`/`outlineColor`/`borderColor` by CONTAINMENT, because `ring-linear-sage/40` compiles to `rgba(122,166,140,.4)`, invisible twice over; it has its own positive control carrying an alpha ring. **ITEMS 1–8 + discovered scope:** `/patients` rebuilt as marker cards (it reported ZERO legacy classes and was still the target — a matcher cannot see "correct tokens, wrong anatomy"); `/patients/[id]` 5→0 with Delete moved into an overflow; the rail DOCKED after lifting the chat drawer to a `<body>` portal (the prior pinning attempt was reverted for exactly that trap); the Rx surface hosted with semantics byte-identical BY CONSTRUCTION; the Word preview **fitting to the wrong box** — measured PDF 756 vs WORD 674 at every width, cured by removing `.qm-npv-stage`'s viewer chrome, with the fit logic untouched because it was never wrong; the board's filter chips DELETED; `/visits/new` and the pipeline states hosted; `/visits` brought over as discovered scope. **⚠️ TWO RULINGS THAT READ AS ONE PRINCIPLE:** the board's chips went and `/visits`' stayed — *remove a control only when the layout already encodes what it says*. A matrix states position; a flat chronological list does not. **⚠️ AND THREE COMMENTS ASSERTING PROPERTIES THE CODE DID NOT HAVE** — `renderSignbar` (an identifier existing nowhere), "R1 just removed" (it had not), "PDF and Word frame identically" (756 vs 674). Two blocked previous attempts at the very items they described. Assigned to F-ret as a scoped sweep. **PROD WALKS:** b2 ran BOTH clinical walks (ultrasound: zero E/M on six terms, exports intact, rail in viewport after scrolling to the paper's foot; primary care: chat edit → re-score → gates → attested sign, with the drawer opened and closed FROM the docked rail and its scrim asserted a direct `<body>` child — the assertion the prior attempt would have failed). b3 touched no stage file (verified by diff), so those walks stand and only the CREATION leg re-ran: posted field names asserted and the specialty hidden input proven to carry the SLUG — the contract R3.7 was written as a wrapper to protect. Smoke reset under the guard each time; **audit rows preserved 648→648 and 665→665**; prod total 24 unchanged. **⚠️ TWO OF MY OWN CHECKS WERE VACUOUS AND BOTH WERE CAUGHT BY READING THEIR OUTPUT:** a prod verification printed `roster anatomy: null` and PASSED (the smoke practice is cleaned to baseline, so an `if (card)` guard made the batch's core assertion a no-op), and the axe gate was green about `/patients` and `/patients/[id]` — the two screens b1 REBUILT — because it never walked them. Both fixed; shots 64→68. |
| **R4** | **Owner walkthrough 3 — two BEHAVIOUR defects the census cannot see** | 🟩 **DONE — LIVE IN PRODUCTION 2026-08-03** | root cause named for each; both guards red-proven; creation leg walked on prod; merge-commit CI cited | PR **#516**, merge **`0868cdb0`**, **merge-commit CI `total=6` all success**. Tree identity proven before deploying. Rollback tags **`:pre-r4-20260803`** cut BEFORE the build and verified against RUNNING ids `7cb56d8e82a0` / `7ed393c06373` / `2d05d22572ba`. Deploy log `deploy-20260803T231932Z.log`. **DEFECT 1 — THE LEGACY Rx PANEL. ROOT CAUSE: `RxTab` HAS THREE MOUNT SITES AND R3.4 HOSTED ONE.** `visit-ready-view.tsx:721` (the `tabs` array's `rx` entry, rendered by `<ReviewTabsV2>` — the fall-through when neither the stage nor the signed branch claims the render; **this is the owner's cream panel**), `:1027` (the stage's `rxGateNode` — the one R3.4 hosted and verified, correctly and incompletely) and `:1451` (the SIGNED review path). A per-caller wrapper is a list kept complete by hand, and it was already incomplete the day it shipped; the host now lives ON `RxTab` so every present and future mount inherits it, and R3.4's wrapper was REMOVED so there is exactly one place it is applied. **⚠️ WHY NO AUTOMATED ENVIRONMENT COULD SEE IT, measured rather than assumed:** the imaging fixture writes `rxDrafts: null` (an ultrasound usually orders no medication — sound reasoning), and QA runs `MOCK_AI`, whose pipeline writes none either — **every visit in the QA database had `rxDrafts IS NULL`**. The owner's case is the intersection those two exclude: an ULTRASOUND whose PLAN orders anticoagulation. The panel was unrenderable in test, so a route walk reported it clean because it was never on screen. **THE GUARD RENDERS THE STATE RATHER THAN WALKING TO IT** — `imagingWithRx` seeds the owner's fixture (unnamed anticoagulant, `action: 'unclear'`, agent-not-specified advisory) and `rounds-stage` asserts the surface is hosted AND that both advisory classes survive **UN-SOFTENED**: they are correct clinical behaviour, and a reskin that "cleaned them up" would be a clinical regression wearing new paint. Red-proven: with the host removed the guard fails with its own message; restored, green. **DEFECT 2 — `+ NEW VISIT` ON `/patients/[id]` CREATED A PATIENT. A REGRESSION I SHIPPED IN R3.2**, which replaced that page's header link — carrying `?patientId=…` — with the shared `RoundsNewVisitCta`, a component that hardcoded a bare `/visits/new`. On the one page where the patient is already known, the button dropped them into create-a-patient. ⚠️ **The empty-state link on the SAME page still carried the param**, which is why only one of the two misbehaved and why "the patient page has a working New visit link" was both true and useless — a statement that survives a spot-check. The CTA takes an optional `patientId` now; every entry point was swept (four `/patients/[id]` links carry it; board ×2, roster and `/visits` ×2 correctly omit it — no patient in scope) and the E2E asserts BOTH directions, because a component appending a stale id everywhere would satisfy the positive assertion and be a worse bug. **PROD WALK** proved the defect's actual HARM is gone, not just its href: the visit landed under the originating patient, confirmed at the data layer — `select count(v.id) … group by p.id` returns ONE patient with ONE visit, where the defect would have produced two rows. **⚠️ TWO CI FAILURES, NEITHER FROM R4's CODE, both diagnosed before acting:** (1) `npm audit` HIGH — **`fast-uri` host confusion GHSA-7p8r-x3mc-p8w7**, reaching us six levels down (`@meddoc/db → @prisma/client → prisma → @prisma/dev → @prisma/streams-local → ajv → fast-uri`). Second HIGH advisory in two days after `brace-expansion`; both published upstream between one green run and the next, both FIXED rather than waived, both verified with the sharp-splice check. (2) Playwright E2E — three Turbopack errors, all the SAME `bricolage_grotesque` Google-font fetch failing in CI's build sandbox; R4 touches no font/layout/config file and the identical build succeeded locally minutes earlier. Re-run passed. **The escalation is written into the commit rather than left implicit: if it recurs the fix is to VENDOR the font, not to retry harder** — a retry is defensible once, on evidence. Smoke reset under the guard: visits 1→0, **audit preserved 673→673**. ⚠️ Prod total read 25 against 24; per **rule 7c** it was investigated, not restored — the extra row is `kasra.rayat@gmail.com`'s, created 20:55, real clinical work, left alone. Packs: stage 14/14 · gates 11/11 · r1 5/5 · board 8/8 · signed 12/12 · c1 15/15 · a11y 2/2 · census 1/1 · units 3158. |
| **F-ret** | Old-skin retirement — **delete, not hide** | ⬜ TODO | the SKIN_ROUNDS fork collapsed to its ON arm; files only the OFF arm reached deleted; its own green CI | Deliberately SEPARATED from the flip above, which is verified and live. ⚠️ **THE OFF ARM IS NOT ALL OLD-SKIN CODE, and this is the trap to read before touching it.** `visit-ready-view.tsx:1099-1105` is the live ON branch of **`NEXT_PUBLIC_REVIEW_DOC_VIEW`** and `:1193-1197` is **`NEXT_PUBLIC_UX_SIMPLIFY`**'s — both `true` in production. The three big legacy blocks (`auth-shell.tsx:139-405`, `settings/page.tsx:575-950`) are gated by **`NEXT_PUBLIC_SKIN_BETA`**, a different flag again. Deleting "the else branch" would retire three flags at once. Also: `qm-rounds-*` is COMPOSED ON TOP of `qm-c3-*`/`qm-lin-*` in globals.css (`rounds-tokens.css` selects them directly at :1310, :1349, :1504, :1538), so removing old-skin CSS breaks the Rounds branch. **⚠️ AND THE STOPPER, MEASURED RATHER THAN FEARED — 2026-08-02.** The bridge itself is safe: it is scoped `[data-skin='rounds'] .qm-rounds-host`, so it cannot reach markup that carries no Rounds class. But **9 of the 170 `[data-skin='rounds']` selector lines in `rounds-tokens.css` do NOT require a `qm-rounds-*` descendant** — `:root[data-skin='rounds']` / `[data-skin='rounds']` (:17-18), **`[data-skin='rounds'] body` (:159-160), which paints the stage gradient**, `[data-skin='rounds'] :focus-visible` (:200), and `[data-skin='rounds'] *` (:211-213). So an unconditional `data-skin` on `<html>` **repaints the page ground and the focus ring on every legacy surface**. Two REQUIRED checks build flag-OFF and would inherit exactly that: the default `chromium` pack pins `NEXT_PUBLIC_SKIN_BETA: "false"` and no other flag (`e2e.yml:90-98`), 24 of 38 specs; and **`a11y.yml` builds with only three `NEXT_PUBLIC_*` vars, none of them the skin flag** (`:156-162`), then runs an axe CONTRAST sweep over those legacy routes. Changing the ground under a contrast gate whose surfaces nobody has re-measured is the one thing rule 7 says not to do. **F-ret is therefore its own item, not a follow-up commit: the default pack and the a11y workflow have to be migrated to the Rounds contract FIRST.** Nothing is at risk in production meanwhile — the dead branches are compiled but unreachable, and the skin is fully on. Stopped and recorded rather than shipped, per the stop-condition. **⚠️ CENSUS UPDATE — R1, 2026-08-02.** R1 REMOVED work from this item rather than adding to it: the board's ~110-line inline top bar is gone (one shared `RoundsTopBar`), `AppFrame` now has a real Rounds branch so `/patients`, `/dashboard` and `/settings` no longer reach `SidebarC3`/`TopNavC3`/`IconRail` at runtime at all, and `/dashboard`'s legacy body is unreachable under the flag (the route forwards before rendering). Those components are still COMPILED — they are the flag-OFF arm, which is exactly what F-ret retires — so the count of consumers to delete is unchanged; what changed is that none of them is reachable in production any more, which makes the deletion a smaller risk than it was. **⚠️ CENSUS CONFIRMED ON PRODUCTION 2026-08-03, not inferred:** with R1 live, `/board` `/patients` `/visits` `/visits/new` `/settings` `/settings/note-format` and `/visits/[id]` all render **0 legacy-shell asides and 0 `.qm-lin-app`/`.qm-c3-app`** — so `SidebarC3`, `TopNavC3`, `MobileNavC3` and `IconRail` have **zero reachable consumers in production**. They remain COMPILED as the flag-OFF arm, which is precisely what F-ret retires, so the deletion list is unchanged; what changed is that nothing a doctor can reach depends on them any more, which makes the deletion a smaller risk than when this row was written. `/dashboard`'s legacy body is likewise unreachable — `next.config.ts` `redirects()` forwards before the route renders. **AND THE FOOTER RE-HOME, which F-ret must not undo:** the paper's embedded signature footer was removed from the stage in R1.2 and `review-document-view`'s `blocked` now takes a `signGateBlockers` prop from the gate overlay. That coupling is what makes the ONE sign path work; deleting the old-skin arm around it without carrying the prop forward re-opens the second sign path this pass closed. **⚠️ CENSUS UPDATE — R2, 2026-08-03. THE FOOTER LINE IS RESOLVED; THE HARNESS
MIGRATION IS NOT.** R2 removed work from this item again, and this time it removed
the part F-ret was deferring.

*Resolved by R2:* the legacy sign bar no longer renders on the stage at all.
`review-document-view` takes `hostSignbar`, false under Rounds, and the signature
is an ordinary React child of Gate 3 (`review-sign-bar.tsx`). **The two artifacts
that said this was already true were wrong** — `review-document-view.tsx:406`
cited a `renderSignbar` that exists nowhere in the tree, and
`rounds-tokens.css:589` claimed R1 "just removed" the bar. Both are corrected.
The footer-agrees guard retired with the footer, declared in the R2 row above.
`gate-flow`'s DOM adoption now covers `rx` and `em` only, declared once as
`ADOPTED_SLOTS`, so F-ret no longer has to reason about a three-way adoption when
it collapses the fork.

*Also resolved:* the `.qm-rdoc` / `.qm-rdoc-page` / `.qm-vdoc` legacy geometry is
neutralised under `[data-skin='rounds']` rather than deleted — deliberately, and
F-ret must NOT read that as work already done. Those rules are still the flag-OFF
surface's real chrome and still ship; what changed is that Rounds overrides them.

*Unchanged, and still the stopper:* the 9 non-`qm-rounds-*`-scoped
`[data-skin='rounds']` rules, and the two flag-OFF REQUIRED checks that would
inherit them — the default `chromium` pack and `a11y.yml`. **The harness
migration is the whole remaining blocker.**

*New for F-ret to carry:* `hostSignbar` defaults to `true` so every flag-OFF
caller keeps its footer untouched. When the fork collapses, that default is the
thing to delete — and the prop must not simply be removed, or the legacy footer
returns to the stage. Same shape as the `signGateBlockers` coupling R1 warned
about here: **deleting the old-skin arm around a prop without carrying the prop
forward re-opens the second sign path this pass closed.**

**⚠️ ASSIGNED TO F-RET BY OWNER RULING, 2026-08-03 — THE FALSE-COMMENT SWEEP.**
R3 found **three** comments asserting a property the code did not have, each
costing real diagnosis time because they were believed:

| comment | file | reality |
|---|---|---|
| *"EXISTS only while the gate flow is hosting it (see `renderSignbar`)"* | `review-document-view.tsx:406` | `renderSignbar` existed NOWHERE in the tree; the bar rendered unconditionally |
| *"the legacy `.qm-c3-rev2-signbar` that R1 just removed"* | `rounds-tokens.css:589` | R1 had not removed it |
| *"PDF and Word frame identically — the toggle's whole promise"* | `globals.css:7000` | measured 756px vs 674px, at every width |

The census exists because a list of sightings never converges into an inventory.
These are the same defect one layer up: **a comment is an assertion nobody
re-runs.** Two of the three were load-bearing enough to have blocked a previous
attempt at the very item they described.

**SCOPE, deliberately bounded — not a repo-wide audit:** during the old-skin
deletion pass, comments asserting BEHAVIOUR or a PROPERTY on Rounds-touched
surfaces and in `globals.css` get verified-or-corrected. That includes
named-function claims (a comment naming an identifier that must exist), and it
runs alongside the dead selectors at `globals.css:7096-7104` already recorded
here — `.qm-vdoc .qm-npv-docx` cannot match, because the Word branch renders no
`.qm-vdoc`.

**The stopper is UNCHANGED** — the 9 non-`qm-rounds-*`-scoped `[data-skin='rounds']` rules and the two flag-OFF REQUIRED checks are exactly as measured. Tests that would need updating with it: `gate-c1c-recovery` (3 flag-OFF cases), `gate-c1d-auth:205`, `gate-c1e-settings:296/305/402`, `gate-c1f-templates:157`, `gate-c1g-routes:136`, the new `rounds-r1` pack (its `HOME_URL_RE` collapses to `/board` once the fork goes, and its legacy-aside matcher becomes vacuous — DELETE the assertion rather than let it pass over nothing), `helpers/home.ts` itself, and `config/rounds-redirects.ts` (whose flag-off arm returns `[]` and would become dead), and `gate-devstates.test.ts:85`, which uses `NEXT_PUBLIC_SKIN_ROUNDS` as its POSITIVE CONTROL for slicing prod compose's `args:` block — remove the arg and that control breaks and its absence assertion goes vacuous. |

---

## Parked, with reasons

| Thing | Why | Un-park when |
|---|---|---|
| **Vitals chips** on the paper (Screen 2) | The spec reserves the slot and says **build it only when structured vitals exist — parked, never faked.** L3 has a `measurements` slot but no vitals shape. | Structured vitals land in the extractor |
| **Failure-stage precision** on the Board | `transcribe_visits` records the terminal status only, so a FAILED lane's stub stops at the last *known* stage and at stage 1 with no history. Claiming further progress would be fiction. | A status-history column exists |
| ~~**The attestation card** on Screen 4 (B3)~~ **UN-PARKED AND CLOSED 2026-08-02 — Ruling 2.** | The un-park condition was met by building it. `POST /sign` now takes `attestation: { acknowledged: true }` and **refuses without it** — `400 ATTESTATION_REQUIRED`, with `SIGN_BLOCKED_NO_ATTESTATION` in the audit trail; `signGates` marks it `serverEnforced: true`. ⚠️ **The park was RIGHT and the reason got worse before it got better:** a second sign control shipped that did not count the tick, so for a window a signature could pass the gate with no refusal and no audit row — a UI-only gate is one alternate path away from not existing. ⚠️ **And the refusal WORKED while its audit row silently did not:** `SIGN_BLOCKED_NO_ATTESTATION` was added to the TS union but not to the Postgres enum, and `logAudit` is `void`-ed, so the insert was rejected and discarded. The gate held; the record did not. Found only by asking PRODUCTION for the row. Fixed by migration `20260802220000` plus `gate-audit-action-parity`, which compares the two lists by source so the next one is caught before it ships. | **CLOSED** — proven on prod today: refusal 400 + `ATTESTATION_REQUIRED`, attested sign 200. |
| **43 specs that can go green on a broken fixture** | B3 found `test.skip(!seeded, …)` letting eleven never-run tests exit 0 — A2 defect 0 in a new place. `requireSeed()` cures it, and is applied in the four Rounds packs. **43 other specs still carry the raw pattern.** Recorded rather than swept because fixing them is not a reskin's work and a half-applied cure is worse than a named one. | Its own item — ideally a lint rule, since the failure mode is silence |
| **The axe gate's inherited violations** | B4 scopes the gate by element OWNERSHIP; the components Rounds composes carry pre-existing serious/critical violations, present flag-OFF too. A reskin rewriting them would be changing the shipped product under cover of a skin. Inventory is in the B4 row. **⚠️ R1 ADDENDUM — `--color-linear-text-4` (#4b5159) IS THE RECURRING ONE, AND IT HAS NOW BEEN FOUND TWICE.** It fails as text on every ground the app uses: **2.41:1** on the legacy canvas (#0d0e10) and **2.15:1** on the Rounds gate panel (#161b24). The 2026-07-28 pass cured the prescription DOSE/FREQ/QTY/REFILLS labels; R1's axe run caught a second node, `.qm-lin-rx-rail-group-n` at 9.5px — small enough that no large-text exemption applies — which renders only inside the Rx rail's GROUPED view and so was invisible to the first sweep. Both fixed to `--color-linear-text-3` (4.90:1 / 5.48:1). **FIVE `color:` consumers of `-text-4` remain and are NOT this item's to change**, named here so the next sweep starts from a list rather than a grep: `.qm-lin-rx-pane-count` (globals.css:1823), `.qm-lin-coding-time-rule` (:4071), `.qm-lin-em-criterion-group-summary` (:4111), `.qm-lin-em-criterion-group-foot` (:4122), `.qm-lin-coding-cta-foot` (:4400). The sixth use, `:4654`, is a `background` and is fine. The lesson is about the TOKEN, not the nodes: a value that cannot be legible text anywhere is a fill colour with a text colour's name, and every consumer of it is a latent violation. | Its own item, against the flag-OFF product |
| **Host disk, and it is NOT this project's to fix** | Free space fell **74G → 71G → 65G** across three sessions (78% used; 80% is the preflight yellow line, 90% blocks). Measured by owner rather than assumed: **`voiceassistmain` holds 106.9 GB across 73 images**, 10 of them built within hours — it rebuilds a ~1.5 GB agent image continuously and keeps every tag. meddoc holds **17.7 GB**, of which nearly all is load-bearing (running `:latest` images, `db-migrate` for `deploy-prod.sh`, and 11 `pre-*` rollback tags). A blanket `docker image prune -a` would delete those rollback tags; trimming only meddoc's own would free 1–2 GB, which is noise against 107 GB. **At the current rate this crosses 90% and stops the relay for a reason the relay cannot fix.** | Needs the **co-tenant owner**, or a host retention policy on `voiceassistmain-agent:git-*`. Not a Rounds item — recorded here because it will present as a mystery to whoever hits it |
| **`NEXT_PUBLIC_TEMPLATE_NATIVE_PDF` has no `ARG` and no QA presence** | Prod supplies it at RUNTIME only (`docker-compose.yml:646`, `environment:`); the Dockerfile declares no `ARG`; the QA stack supplies it in neither place. It WORKS today only because both readers are server-side (`settings/page.tsx:49`, `lib/pdf-native/export.ts:10`) — 0 surviving reads in prod's client chunks, positive-controlled. ⚠️ **CORRECTED 2026-08-01 — THE OLD "HALF-FIXING IS WORSE" SENTENCE WAS WRONG, AND THE TRUTH IS WORSE THAN IT SAID.** It read: *an `ARG`+`ENV …=false` alone inlines `false` into client bundles while the server keeps reading `true`.* The server would **not** keep reading `true`. Next 16 spreads `nextPublicEnv` into the define map **before** any `isClient`/`isNodeServer` branching (`next/dist/build/define-env.js:61`; the map is built by `next/dist/lib/static-env.js`, which keeps every key where `value != null`), so the constant is folded into the **server** bundle too and PDF-native fill would go **silently and uniformly OFF in production** — not a client/server split, a uniform disable. | ⚠️ **DO NOT ADD `ARG NEXT_PUBLIC_TEMPLATE_NATIVE_PDF` TO THE DOCKERFILE — that is the destructive half, and it is not the compose `args:` row.** A compose `args:` entry with no matching `ARG` is discarded silently (this repo's own recorded trap); the `ARG`+`ENV` pair is what puts the key in the **builder's** env, and mere presence is the whole trigger — the ARG's own default suffices, whether or not compose passes anything. This flag is the only **`NEXT_PUBLIC_*`** one in the stack that can be flipped without a rebuild (`docker-compose.yml:646`, *"ROLLBACK: unset it + force-recreate"*), and it works **because** it has no `ARG`. (Scoped deliberately: `SIGNUP_INVITE_CODES` `:667` and `EMAIL_AUTO_CONFIRM_DOMAINS` `:656` are also runtime gates, but they carry no `NEXT_PUBLIC_` prefix and so were never at risk.) **The harm is not theoretical — the neighbour already has it.** `NEXT_PUBLIC_SHOW_PIPELINE_TAB` is read by a server component (`visits/[id]/page.tsx:680`) and *three* comments promised the same no-rebuild flip; it has **0 surviving server reads across 579 prod chunks**, folded to the literal **`showPipelineTab:!1`** (positive control: `process.env` matches 90 of the 579). All eleven ARG-declared `NEXT_PUBLIC_*` flags read 0; this one reads 2. Those three comments are corrected (`docker-compose.yml` `args:`+`environment:`, `Dockerfile:61`) — **the lie was the comment, not the line.** *The reasoning error worth keeping:* they verified "not inlined into the CLIENT bundle" (true) and generalised it to "read at runtime" (false). **"Not in the client bundle" does not mean "read at runtime."** **What to do instead — none of it needs a rebuild.** The real risk is only the misleading `NEXT_PUBLIC_` prefix inviting a future client read, and a guard closes that permanently at no cost: (1) a source test beside `gate-flag-coverage` asserting `@/config/template-native-pdf` is never imported from a `'use client'` module and that the `process.env` read lives in exactly one file — prove it red by adding the import to `note-format-manager.tsx`; (2) add `NEXT_PUBLIC_TEMPLATE_NATIVE_PDF: "true"` to the **base** `docker-compose.qa.yml` `environment:` block. *(Correction to this row's own text: "no QA presence" is imprecise — `docker-compose.qa.ux.yml:35,40` does supply it, with a comment documenting the mechanism correctly. But that file is a scenario override that swaps in the `:ux-simplify` image and is not the stack in use, so no QA configuration actually running supplies it.)*; (3) record the no-rebuild flip in `DEPLOYMENT_RUNBOOK.md` §3.1/§3.2 — **it exists today only as a compose comment, which is why it was nearly traded away**, and §3.2 already shows the cost of a rebuild-only flag rollback. **If a prod rebuild ever does happen, the strongest fix is to RENAME it** — drop the `NEXT_PUBLIC_` prefix entirely. Both readers are server-side, nothing breaks, and the trap becomes structurally impossible rather than merely guarded. Six existing sites across four files (`config/template-native-pdf.ts:17,20`, `.env:91`, `docker-compose.yml:646`, `docker-compose.qa.ux.yml:35,40`) plus a stale name-mention at `actions/certify-pdf-template.ts:13` |

---

## What F-ret STEP 1 measured — the migration is a multi-session item, and it found a product defect

**Measured 2026-08-03/04. Nothing was migrated, nothing was deleted, nothing
shipped.** This section exists so the next session starts from a number instead
of from the assumption the brief carried.

### The number

The brief's first sub-item reads *"Migrate the two flag-OFF required checks to
the Rounds contract first (default `chromium` pack rebuilt against the flag-ON
production-shaped image)."* That is one sentence and it is not one session.

Running the default `chromium` pack against the **flag-ON** QA stack:

> **21 failed · 20 passed · 18 skipped, of 59 tests.**

The pack is 24 specs of the app's non-Rounds behaviour. Migrating it is not
re-pointing a config value — **it is 21 individual triages**, each of which is
one of three different things, and they cannot be told apart in bulk:

1. **Selector drift** — the spec asserts a legacy affordance that the Rounds
   shell renders differently or not at all. Fix the selector.
2. **Retire-with-a-note** — the spec asserts something the Rounds skin
   deliberately does not have. Delete it *and say so in this ledger*, per R2's
   footer-agrees precedent: a guard retires WITH the thing it guards, declared,
   never silently.
3. **A real defect.** At least one already is — see below.

Sampling one to prove the class: `12-auth-login` dies at
`TimeoutError: locator.click … waiting for getByRole('button', { name: /account menu/i })`,
which comes from `tests/e2e/helpers/auth.ts:51` — the **shared** logout helper.
One helper line accounts for a large share of the 21, which is exactly why the
count must be triaged rather than divided.

### The product defect it surfaced

Chasing that selector produced a finding that is not about tests. Measured on
the live Rounds DOM, authenticated:

```
/board     { signOutText: false, signOutControl: 0, accountish: [] }
/patients  { signOutText: false, signOutControl: 0, accountish: [] }
/settings  { signOutText: true,  signOutControl: 2,
             accountish: ['Profile','Save profile','Delete my account'] }
```

Confirmed from source rather than left as a DOM reading:

- `components/rounds/top-bar.tsx` renders the brand, three links
  (`/board`, `/patients`, `/settings`) and the user's name as a plain `<span>`.
  **No account menu. No sign-out.**
- `components/rounds/app-frame-rounds.tsx` renders `RoundsTopBar` and `<main>`
  and nothing else — so no route under the Rounds shell reaches the legacy
  chrome.
- The four `signOut(` callers in the app are
  `components/ui/top-nav.tsx:298` and `components/ui/sidebar-c3.tsx:89` (both
  **legacy shells, unreachable under the flag** — R1 confirmed this on
  production), `admin/_components/AdminOverview.client.tsx` (admin only), and
  `settings/delete-account-dialog.tsx:92` (a side effect of deleting your
  account).
- The two controls the probe found on `/settings` are
  `settings/session-panel.tsx:73` **"Sign out"** and `:118` **"Sign out all
  devices"**.

**So: signing out still works, and it lives in exactly one place —
Settings.** It is not a lockout, because Settings is in the nav. It *is* a
regression in affordance from the legacy account menu, shipped with the flip on
2026-08-02, and nobody noticed because the only thing that exercised it was a
test helper that has been failing since.

**Ruling owed:** either the Rounds top bar grows an account menu (and
`helpers/auth.ts` keeps its selector), or sign-out is Settings-only by design
(and the helper is rewritten to walk there, with the change declared here). It
is a product decision, not a test fix — which is precisely why it must not be
resolved by quietly editing the selector.

### ⚠️ RE-MEASURED 2026-08-04, AFTER THE ACCOUNT MENU SHIPPED — 19, NOT 21

And the correction matters more than the number.

I predicted that `helpers/auth.ts:51` "accounts for a large share of the 21",
because it is the SHARED logout helper and one broken selector in a shared
helper is the classic multiplier. Re-run against the deployed code:

> **19 failed · 22 passed · 18 skipped, of 59** (26 files, collected count
> unchanged).

**The account menu fixed exactly TWO.** The prediction was wrong, and it was
wrong in the direction that feels most reasonable — "shared helper, therefore
broad blast radius". The helper is used by the specs that log OUT, and most of
these never do.

⚠️ **AND THE RUN'S OWN SUMMARY READS LIKE A PASS.** The `list` reporter's tail
prints the failing test NAMES and then:

    18 skipped
    22 passed (7.8m)

No "19 failed" line anywhere in the tail. `22 + 18 = 40` against a collected
59, and the only unambiguous signal is `EXIT=1`. This is the emptiness-test
defect in a new coat: **a number that does not add up to the set it came from.**
Always reconcile the arithmetic against `--list`'s `Total:` before believing a
Playwright tail.

### ⚠️ AND THE NIGHTLY'S OWN FAILURE WAS THE SAME BUG, CONFIRMED

Three of the 19 fail on `expect(page).toHaveURL()`. The scheduled nightly was
failing on exactly that shape and it took reading the artefact to name it:
`expectAppSuccess` waited for `/\/dashboard/`, and under Rounds `/dashboard` is
a **config-level 307 to `/board`** (`config/rounds-redirects.ts:46`, verified
live: `curl -sI https://app.quillmd.com/dashboard` → `HTTP/2 307`). The skin
flipped 2026-08-02; the first nightly after it, 08-03, went red; it stayed red
for two nights.

Fixed as `/(board|dashboard)` — **both**, because that file runs against
PRODUCTION and pinning it to the new name alone would turn it into a false RED
the moment anyone rolls back to the flag-OFF image.

**Verified, not assumed** — re-dispatched after the fix landed on `main`:

> `nightly-tests` **conclusion=success** · smoke-health 8/8 · e2e **10 pass, 0
> fail** (was 8 pass / 2 fail) · the six pro.quillmd.com cells correctly skipped

Two further defects surfaced in the same run and are fixed alongside it:

- `run-all.sh:87` `cd`'d to a hardcoded `/opt/meddoc-pro/apps/transcribe-md`,
  which cannot exist on a GitHub runner — **the nightly's Playwright leg had
  never run in CI**, since PR #56. Derived from `$HERE` now.
- `Open issue on failure` was dying with `Resource not accessible by
  integration`: the default token is read-only for issues, so **a failing
  nightly had been notifying nobody**. `permissions: issues: write` added.

Three checks, three different ways of being green-adjacent: one that could not
reach what it tested, one asserting a URL the product had moved, and one alarm
that could not ring. Together they hid a two-day-old regression in a week when
somebody was watching closely.

### ⚠️ THE MEMBERSHIP COROLLARY — banked beside the arithmetic-tell

The arithmetic-tell says: *a number that does not add up to the set it came
from is the tell.* It is necessary and it is **not sufficient**.

I ran the flag-ON pack locally, got `40 passed / 19 skipped / 0 failed = 59`,
reconciled it against `--list`'s `Total: 59`, and called it green. CI then
failed — because `e2e.yml` runs a SECOND step, *"chromium; scenario 5
note-format UN-GATED via NOTE_FORMAT_E2E"* (`:271`), which EXECUTES the very
specs my run skipped. Fourteen of them failed there.

**Skipped is not covered. A reconciled sum does not prove set equality.**

So the local verification loop for a required pack must either:

1. **replicate CI's un-gating environment** — enumerate it from the workflow
   files rather than remembering it. Today that is `NOTE_FORMAT_E2E=1`
   (`e2e.yml:275`, `:604`) and `MOCK_TEMPLATE_PHI_FLAG` for the `phi-reject`
   project; or
2. **enumerate the delta explicitly** — list which CI-executed specs the local
   run did not execute, and say so in the same breath as the number.

A local green that silently covers a smaller set than CI is the same defect as
a gate pointed at a build nobody runs, one scope down.

### The triage table — F-ret.1's actual deliverable, seeded

19 failures, by error class rather than by spec, because the class is what
predicts the fix:

| Class | Count | Shape |
|---|---:|---|
| `locator.click` timeout | 8 | 1, 2, 3, 9, 12, 13, 14, 15, 19 — a control the Rounds skin moved or renamed |
| `expect(locator).toBeVisible()` | 4 | 6, 10, 11, 17 — an element the skin no longer renders in that place |
| `expect(page).toHaveURL()` | 3 | 4, 5, 8 — **almost certainly the `/dashboard` → `/board` 307**, the same root cause that reddened the nightly |
| `locator.fill` timeout | 2 | 7, 16 — an input that moved |
| `toHaveAttribute` | 1 | 18 |

Full list with spec + line in the session record; the 5 specs carrying 2+
failures are `6-patients`, `10-visit-lifecycle`, `16-account-settings`,
`27-error-resilience`, `29-sign-modal-geometry`.

**Start with the three `toHaveURL` failures.** The nightly's two app-side
failures had exactly this cause and it took one line to fix once named
(`/(board|dashboard)`), so that class is likely cheap and is likely the same
bug three times. **Do not assume it is** — the point of the triage is that each
one gets read.

### What this means for the item

**F-ret stays ⬜ TODO and is now explicitly multi-session.** Suggested split,
so the next session does not re-derive it:

- **F-ret.1** — ~~the `helpers/auth.ts` ruling~~ **RULED AND SHIPPED
  2026-08-04**: the owner's call was *account menu in the top bar*, so the
  helper is unchanged and is now a legitimate consumer of a real control
  (`components/rounds/account-menu.tsx`, pack `rounds-account`, 5/5 + a mutant
  proof). What remains of .1 is the **triage table above, worked**: 19
  failures, each marked drift / retire-with-note / defect, with the retires
  named in this ledger. Ends with a number, not a fix.
- **F-ret.2** — `a11y.yml` pointed at Rounds routes, with the route set
  enumerated **before and after** (the brief's "coverage equal-or-wider" is a
  claim that needs both lists to be checkable).
- **F-ret.3 …** — the deletion itself, unchanged, still gated on .1 and .2.

### ✅ F-ret.3 — CLOSED 2026-08-05. THE ROUNDS RELAY IS COMPLETE END-TO-END.

PR **#527** → merge commit **`2cda8f9d`** (parents `0444bed6` + `8634d9dc`).
Deployed to production 2026-08-05, log `docs/deploy-logs/deploy-20260805T110923Z.log`.

| Workflow | Run | Conclusion |
|---|---|---|
| `CI` | `30997743530` | success |
| `e2e` | `30997743548` | success |
| `secrets-scan` | `30997743533` | success |
| `a11y-ci` | — | **DID NOT RUN** — `pull_request`-only. Not borrowed from the PR head. |

`total=6, success=6, non-success=0`, re-read from the API.

**58 files, +1122/−4145, 18 files deleted.** The flag, its OFF arm, and every
decoy site are gone. Rollback for this surface is **tagged images only**
(`:pre-fret3-20260805`, ID-verified against the running containers) — and that
tag is now the ONLY place the old skin exists: `main` cannot build it and no flag
can select it. Runbook §3.1/§3.3.

**BUNDLE DIFF — the deletion's proof, measured in the RUNNING production
container, every zero against a live positive control:**

| needle | before | after |
|---|---|---|
| runtime `SKIN_ROUNDS` (app) | `=true` | **ABSENT** (12 other `NEXT_PUBLIC_*` present) |
| runtime `SKIN_ROUNDS` (worker) | `=true` | **ABSENT** (11 other present) |
| `"Go to dashboard"` | 3 chunks | **0** |
| `"Back to dashboard"` | 3 chunks | **0** |
| `"Back to the board"` / `"Go to the board"` | — | 3 / 2 |
| `qm-rounds-` | 65 | 72 |

Standing checks 5/5 ✅ clean post-deploy. Co-tenants unchanged: app `307`,
marketing `200`, admin `404`, pro `410`.

#### ⚠️ THE SMOKE IS PARTIAL, AND THE UNVERIFIED HALF IS NAMED

Steps 1–7 passed against production on the synthetic smoke account: the board is
home with its top bar and account menu; `/visits/new` draws; **zero legacy nav
components**; `data-skin="rounds"` unconditional; the 404 recovery link is
"Back to the board" → `/board` with no "Back to dashboard" anywhere; `/dashboard`
forwards rather than renders; a visit was created and the stage + paper drew.

**THE ATTESTED SIGN WAS NOT COMPLETED, and the log line claiming it was is the
lesson.** My walk printed `SMOKE 8/9 attested + signed` immediately after
clicking the sign control — before anything confirmed it. The database says
`status=READY`, `signedAt` null, and there is **no `VISIT_SIGNED` audit row**.
Step 9 caught it.

**The product is not implicated.** No `POST /sign` reached the server at all — no
sign-related log line in 20 minutes — because "Sign & Download" opens
`SignAndSendModal` and my walk never submitted it. A harness that stops one
control short, not a broken gate. The attested-sign path IS covered by the
`rounds-gates` and `visit-doc` packs, green on this merge commit.

**Evidence written at the moment of an action is not evidence.** That is relay
rule 2c, and I broke it in my own smoke while quoting it elsewhere in the same
session.

Smoke data cleaned to baseline: visits 2 → **0**, patients 2 → 0, **audit rows
PRESERVED (949)** — deleting them would be the tampering the trail exists to
prevent. Real-clinician visits unchanged at 26.

#### 19:56 — DISPOSITION: BRANCH (a), FORK OBSERVED AND RE-POINTED

Driven on the production-shaped build. The database showed a genuine fork —
`v1 INACTIVE` + `v2 ACTIVE`, original row untouched — and every DB assertion
passed unchanged. Only the card's `· v2` version badge went away, so the
assertion moved to **"Superseded"**: the word the product uses, a state a doctor
can see and act on, rather than an implementation detail leaking into the UI.
Strictly stronger than what it replaced.

#### TWO CANON COROLLARIES, BANKED

1. **Search the VARIABLE, not the accessor.** A flag census built from
   `grep -rl isSkinRounds` missed `next.config.ts:38`, which read
   `process.env.NEXT_PUBLIC_SKIN_ROUNDS` raw and never touched the helper. It
   controlled `/dashboard`'s HTTP status. A wrapper is a convention, not a
   guarantee — inventory the thing itself.
   ⚠️ **And one step further: search the DESTINATION too.** The bundle diff
   found `command-palette.tsx:206` still offering "Go to dashboard" → `/dashboard`
   on every authed page behind Cmd+K. It never touched the flag; it hardcoded
   where it went.

2. **A compliance row retires on SUCCESSOR EVIDENCE, never on a reachability
   argument.** Deleting `/dashboard`'s §164.312(b) `VIEWED_DASHBOARD` row was
   safe *because the production audit trail showed the obligation had moved* —
   `VIEWED_DASHBOARD` 2361 rows ending 2026-08-03, `VIEWED_VISIT_LIST` 301 rows
   starting 2026-08-02 and current, with a one-day overlap. "This code is
   unreachable" is a claim about source; it is not evidence the trail is
   unbroken. The rows are. Without that query this would have been a compliance
   change wearing a refactor's clothes.

#### ⚠️ OPEN ITEMS CARRIED OUT OF ROUNDS — none of these is closed

| Item | Detail |
|---|---|
| **`/board` overflows 76px at 390px** | LIVE on the doctor's home page. `board-chrome.tsx:289` carries an inline `style={{ minWidth: 190 }}` on the day meter inside a non-wrapping flex row. NOT fixed here: the remedy is a design decision and `rounds-board` asserts on that surface. Found only because the deletion pointed the one overflow check at the real skin. |
| **`16-account-settings` flake** | My own `networkidle` fix narrowed the window without closing it — 0/12 locally, then two failures in one CI run. The submit can still beat the client tree. Needs a hydration-PROVING wait, not a network condition. |
| **`docker-compose.qa.yml` hardcodes `:latest`** | The same tag production builds to, on one daemon. AGENTS.md forbids moving prod's `:latest` to stage something, and the QA compose leaves no other way — I moved it and opened a ~1h window where a prod `compose up` would have shipped an untested image (nothing ran; rollback tags verified intact). The overrides `qa.rounds.yml`/`qa.reviewdoc.yml` show the correct pattern. The base file should pin its own QA tag so the prohibition is enforceable rather than remembered. |
| **`a11y-ci` never runs on `main`** | `pull_request`-only. Recorded in `docs/foundation/RELAY.md`. |
| **`em-coding:llm-mdm` ignores `MOCK_AI_CALLS`** | Recorded in `docs/foundation/RELAY.md`. |

#### THE FINDING THAT OUTGREW THE ITEM

**Four E2E packs were certifying configurations that were not production**, each
surfacing only when the flag's deletion forced it: the default `chromium` pack
(19 failures, F-ret.1), `rx-safety` (5), `review-doc` (8), `visit-doc` (11 across
two rounds). Three had dead selectors. The fourth held the **only** check in the
entire suite that measures horizontal overflow — and had never once run it
against the shipped skin. On its first real run it caught a **live 7px overflow
on every authed page at phone width**, shipped 2026-08-04 with the account menu.

That is the argument for deleting a flag rather than parking it, stated better
than anyone would have argued it in the abstract: **a flag left on keeps a second
product alive that the test suite quietly attests to.** For three days the
suite's answer to "does the app work on a phone" was about a build nobody shipped.

⚠️ It also means "F-ret.1 migrated the packs" was true only of the packs that
BROKE. The per-pack image build args were never audited as a set until F-ret.3
did it — and that audit found `visit-doc` before CI did.

---

## 🟩 ROUNDS — COMPLETE, END TO END

Every item from the flag's first flip to its deletion is closed. The skin is not
a feature behind a flag; it is the product. **The next session opens TEAMS per
`docs/foundation/RELAY.md`, with the exit gate intact — including the owner veto
window on the 12 `MEDDOC_PRO`-only accounts, which must be confirmed lapsed
BEFORE the TEAMS migration excludes them. Four of those twelve carry the
operator's own name.**


### ✅ F-ret.1 AND F-ret.2 — CLOSED 2026-08-04

PR **#525** → merge commit **`c150b600`** (parents `214103d9` + `3d8cb23f`).

**Merge-commit evidence, by workflow name — and one of the four could not be
cited, which is stated rather than papered over:**

| Workflow | Run | Conclusion |
|---|---|---|
| `CI` | `30939703503` | success — `test`, `unit tests`, `npm audit`, `dev-dependency advisories` |
| `e2e` | `30939703687` | success — `Playwright E2E (transcribe-md)` |
| `secrets-scan` | `30939703383` | success — `TruffleHog` |
| `a11y-ci` | — | **DID NOT RUN.** `a11y.yml` triggers on `pull_request` only |

`total_count: 6, success: 6, non-success: 0`, re-read from the API rather than
remembered. `a11y-ci` was green on the PR head `3d8cb23f` (axe-core sweep,
4m24s); quoting that beside a merge SHA would be exactly the substitution the
citation rule exists to prevent, so it is not quoted as such. The gap itself is
recorded in `docs/foundation/RELAY.md` — it is not specific to this PR.

**The table: 16 drift · 2 retire · 1 new required spec · ZERO overturned.**

The two retires, with their notes in the spec files themselves rather than only
here:

| Retired | Verdict |
|---|---|
| `8-visit-detail-tabs.spec.ts` — **PARTIAL** | The tab strip is unreachable under the shipped flag set (`visit-ready-view.tsx:645/848/1203` all exit before `:1317 <ReviewTabsV2>`). It died with the C3 promotion and the read-only paper, NOT with the Rounds flip. **The list→detail navigation survives deliberately** — it is the only proof a `/visits` anchor resolves to a real visit page, and retiring the whole file would have dropped it silently. |
| `9-soap-edit.spec.ts` — **FULL, as a tombstone** | The inline SOAP editor cannot render on any shipped surface (`SoapInlineEdit.tsx:92` returns a bare div when `readonly`; both live mounts pass `chromeless`). Kept as a `describe.skip` holding the record, because deleting the file would have erased **what the required pack lost**. |

**The new spec exists because retiring `9-soap-edit` opened a hole in the same
pass that closed it.** `30-note-edit-persistence.spec.ts` promotes the *claim*
rather than the spec — `visit-document.spec.ts` needs a certified-twin fixture
and the Gotenberg sidecar, neither of which the required pack stands up. A
capability covered only by non-required packs is the two-month gate defect in
miniature.

**⚠️ WHAT THIS ITEM COST, AND THE ONE LESSON WORTH CARRYING.** Giving e2e.yml's
fixture-image build the production flag set fixed the default pack **and broke
`rx-safety`** — five of its eight tests — because `phi-reject` and `rx-safety`
run on that same image and had been silently flag-OFF. The product never
changed; the harness started looking at the shipped surface. Repaired in
`3d8cb23f`.

Three things from that repair generalise:

1. **Two failures that look alike can have different causes.** Four of the five
   died on `getByRole('tab', {name:'Rx'})`; the fifth died on
   `getByRole('button', {name:/sign & send/i})`. Reading only the first would
   have generalised the wrong cause across all five.
2. **My first repair of the fifth was wrong, and only DRIVING caught it.**
   Swapping in `openSignFlow` failed at `sign.ts:95` — "the gate flow never
   presented the attestation". The helper was right and the product was right;
   the assumption was wrong. A visit with an un-overridden critical interaction
   never reaches attestation, so the old shape (attest → submit → read the
   refusal) has **no analogue**. Under Rounds the doctor is stopped one step
   earlier and told *"1 critical interaction outstanding"* — a stronger
   property, measured on the stack, not inferred from the component.
3. **`toHaveCount(0)` passes vacuously on a misspelled testid.** The mutation
   that mattered pointed it at a testid that IS present; it went red. Without
   that, the assertion would have asserted nothing forever.

Both Rx specs had their own copy of the tab dance and both broke identically, so
the replacement lives in one place (`helpers/rxGate.ts`) — a per-caller list is
kept complete by hand, and hand-kept lists are wrong eventually (R3.4).

**F-ret.2 — the route set, both lists, because "equal-or-wider" is a claim that
needs checking rather than asserting.** Baseline `d02484f3` → `cc397d93`:

| | Routes |
|---|---|
| **Before** (14) | `/login` `/signup` `/waitlist` `/forgot-password` `/reset-password` `/check-email` `/dashboard` `/visits` `/visits/new` `/settings` … |
| **Added** (3) | `/board` · `/patients` · `/settings/note-format` |
| **Removed** | **none** |
| **After** | **17** |

⟹ equal-or-wider: **YES**, by set difference rather than by counting.

`a11y.yml`'s build step also gained the same 11 `NEXT_PUBLIC_*` flags as
`e2e.yml`, so the sweep runs against a production-shaped build. **The full flag
set, never one flag** — the `/dev/null --env-file` lesson applies identically
here: a single flag flipped in isolation produces a build that exists nowhere.

That re-point immediately found a real defect rather than a harness one: the
Word preview's `.qm-npv-docx` was a keyboard trap under
`scrollable-region-focusable` (`overflow-x: hidden` implies `overflow-y: auto`,
so the container scrolls and was not reachable by keyboard). Fixed at
`native-document-preview.tsx:270` with `role="region"` + `aria-label` +
`tabIndex={0}`; green at both viewports, 34/34.

**Note-edit persistence regained REQUIRED coverage** via
`30-note-edit-persistence.spec.ts` rather than being explained away — see above.

**F-ret.3 remains ⬜ TODO**, and three of its inputs are now measured rather
than assumed:

- **The `NEXT_PUBLIC_SKIN_ROUNDS` decoy is NOT a compose line.** `docker-compose.yml`
  names the flag exactly once, at `:560`, as a build arg. The inert runtime value
  in both containers comes from `env_file: ['.env']` → `.env:115`. The worker
  proves it: no `SKIN_ROUNDS` build arg at all, no client bundle to inline into,
  and it still carries `NEXT_PUBLIC_SKIN_ROUNDS=true` at runtime. **Three removal
  sites, not two** — deleting only the compose line would leave `.env:115`
  sourcing a variable nothing reads.
- **`globals.css:7096-7104` (`.qm-vdoc .qm-npv-docx`) is provably dead** — by
  complete enumeration, not a spot check. `.qm-vdoc` has one emitter
  (`DocumentPages`) with one mount; the `.qm-npv-docx` emitter has four mounts,
  one of which is a **mutually exclusive sibling branch** behind an early
  `return` and three of which are under `settings/note-format`. ⚠️ The near-miss
  is why this needed proving: `document-pages.tsx` DOES emit `qm-npv-page` and
  `qm-npv-note`, so grepping the subtree for `qm-npv` returns hits and would have
  argued the rules were live.
- **The "PDF and Word frame identically" comment is NO LONGER FALSE.** It was
  catalogued at `globals.css:7000` on measured evidence (756 vs 674), and
  **R3-b2 then fixed the defect** — both measure 756 after the viewer chrome was
  removed. The code was changed to match the comment. Correcting or deleting it
  now would turn an accurate statement into a false one. ⚠️ This rests on
  R3-b2's *recorded* measurement, not on one I took; re-measuring is F-ret.3's
  first step for this item. The sweep therefore stands at **4 of 5 resolved**,
  not 5.

**The stopper recorded in the F-ret row is untouched by this.** The 9
non-`qm-rounds-*`-scoped `[data-skin='rounds']` rules and the two flag-OFF
required checks are exactly as measured; this section only establishes the size
of step 1.

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

## What B2 found — a heuristic that pointed the wrong way, twice over

**A2's rule was: "a uniform failure across every test in one pack is almost
never the product. It is the environment."** B2 met a uniform failure — all 8
tests in the new pack dying at the same line — and it was **the product**: a
mount-time crash (React #185) meant the surface never rendered, so every test
failed identically.

The sound form of the rule is narrower and worth carrying forward:

> **A uniform failure means ONE COMMON CAUSE.** Usually that is the environment.
> A crash at mount produces the identical signature.

What separated them cheaply, before any code was read: **grep the BUILT IMAGE
for the component and its CSS.** Both were present, so the image was right and
the environment was not the cause. That check costs one command and is the first
thing to run against a whole-pack failure.

### And the fix for the first defect introduced the second

`createPortal(node, host)` and a bare `node` are **different element types** to
React. So a seam that portals a gate into the active step and lets it fall back
inline when the step deactivates **unmounts and remounts the subtree on every
navigation** — which reset `RxTab`'s `overriddenIds` to the stale server prop
and asked the doctor to re-justify a warning already persisted.

That is the exact defect the portal was chosen to prevent. Changing a portal's
container remounts for the same reason, so "give every step its own host" does
not fix it either.

**Moving the DOM node does.** React never learns: it keeps rendering into the
same wrapper, so nothing unmounts and all state survives. The restore on cleanup
is not optional — React removes that wrapper from its ORIGINAL parent when the
owner unmounts, and a node adopted elsewhere at that moment throws.

**The generalisation:** when the requirement is "this subtree must keep its
state while its position changes", the question to ask is not "how do I re-parent
the React element" — every answer to that remounts. It is "how do I leave the
React element exactly where it is."

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
