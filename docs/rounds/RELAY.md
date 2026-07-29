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
| **F0** | Foundation: tokens doc, `rounds-tokens.css`, flag, fonts, `data-skin`, stage mapping | ✅ **DONE** | units green + exhaustiveness guard negative-controlled | `c2f35d2a` · 18 tests |
| **F0b** | Board row model: lane kinds, run lengths, filters, ordering, day meter | ✅ **DONE** | units green, honesty rules pinned | 37 tests total, tsc clean |
| **A1** | **Board component + units** | ✅ **DONE, MERGED** | component renders all five lane kinds; positioning proved; retry integration correct; typecheck clean | PR **#453** merged · +retry fix · **24** component tests · 2719 suite green · tsc clean |
| **A2** | Board E2E + axe + screenshots + merge | 🟨 **IN PROGRESS** — reverted under rule 2a | axe **0 serious/critical** across 7 views × 2 widths × 3 animation samples · rounds-board E2E 5/5 · screenshots 1440 + 1024 · suite green — **all LOCAL, and local does not close an item** | PR **#455 open**. Was marked DONE on local evidence while CI was red: the pack was missing from the default project's `testIgnore`, so the flag-OFF run collected it and 404'd, and `--project=rounds-board` never ran in CI at all. Fixed + pinned by a negative-controlled guard (`gate-flag-coverage.test.ts`). **Closes when #455 merges green — merge SHA + CI run to be cited here.** |
| **B1** | Screen 2 — the stage | ⬜ NEXT (blocked on A2) | pipeline strip from the same mapping; NOW REVIEWING; padlocked Signed node with correct **N**; sheet is the existing paper component restyled; identity header; next-up peek; chat drawer | — |
| **B2** | Screen 3 — the gates | ⬜ TODO | full-screen sequential over EXISTING logic; only applicable gates exist; `> OVERRIDE` typed input unchanged; E/M only when `emApplies`; attestation; **sign-block E2Es pass with semantics unchanged** | — |
| **B3** | Screen 4 — signed + deck-advance | ⬜ TODO | strip fully checked; lock banner; safety trail shows **only what applied**; addendum footer; deck advances to next in-review | — |
| **B4** | Gate B verification | ⬜ TODO | axe zero serious/critical on stage + all gates + signed · chromium E2E incl. sign-block · **fixture matrix both specialty classes** (imaging: no E/M gate, no strip blocker, anywhere) · **PDF/Word parity re-proven at 1440** · screenshots · merge on green | — |
| **C1** | Auth / settings / templates / error-empty-loading | ⬜ TODO | all to tokens; copy register: plain verbs, sentence case, actions keep their names end-to-end | — |
| **C2** | Default-paper typography + Gate C | ⬜ TODO | **exports match preview 1:1** (this is the report-template design deliverable) · axe on every restyled screen **incl. waitlist** · full suite + typecheck · E2E green · merge on green | — |
| **F-pre** | **Reboot proof of the encrypted MinIO volume** | ⬜ **REQUIRED BEFORE F** | a real host reboot, then: `minio-encrypted` mapping present · `/mnt/miniodata-encrypted` mounted from it · MinIO healthy and its `/data` on the dm device · `check-minio-encrypted-mount.sh` = 0 · all co-tenants back · prod 200 | Added 2026-07-29. The unlock is `miniodata-encrypted.service`, `Before=docker.service`, and it has **never been exercised by an actual boot** — it was started by hand. Boot ordering is the one property a hand-start cannot prove, and MinIO now **fails closed**, so if the unit loses its race with docker MinIO does not start at all. Better to learn that on a chosen boundary than during F. **Chosen boundary: immediately after A2 merges, before B1 opens** — nothing uncommitted, no branch in flight, and it is the last such boundary before the work gets long. Expect the two known reboot side effects first (the QA stack does NOT self-restart; a stale `@reboot` cron dirties the tree) — bring QA back and clean the tree as part of the proof, not as a surprise. See runbook §5.7.1 |
| **F** | Flip + old-skin retirement + prod smokes | ⬜ TODO | walker map updated, run on QA, `ok:true` · MOCK posture green · tag `:pre-rounds-<date>` **first** · flip via `scripts/deploy-prod.sh` only · **delete** old skin after the flip verifies · rollback docs updated · both prod smoke walks · standing checks green · co-tenants verified | — |

---

## Parked, with reasons

| Thing | Why | Un-park when |
|---|---|---|
| **Vitals chips** on the paper (Screen 2) | The spec reserves the slot and says **build it only when structured vitals exist — parked, never faked.** L3 has a `measurements` slot but no vitals shape. | Structured vitals land in the extractor |
| **Failure-stage precision** on the Board | `transcribe_visits` records the terminal status only, so a FAILED lane's stub stops at the last *known* stage and at stage 1 with no history. Claiming further progress would be fiction. | A status-history column exists |

---

## What A2 found (read before B1 — the same traps apply)

Five defects, none visible in a screenshot. **The fifth is the one to read
first, because B1 adds another flag-ON pack and will meet it again:**

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
