# Rounds — the relay ledger

**This ledger is the contract between sessions.** `docs/rounds/SPEC.md` says what
to build; this says what is built, what is next, and what proof exists.

## Rules

1. **One item per session, taken to its gate.** Not half an item, not two.
2. **Merge on green.** An item is not done until its PR is merged.
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
| **A2** | Board E2E + axe + screenshots + merge | ✅ **DONE** | axe **0 serious/critical** across 7 views × 2 widths × 3 animation samples · rounds-board E2E 5/5 · screenshots 1440 + 1024 · 2723 suite green | `docs/rounds/screenshots/board-{1440,1024}.png` · `:rounds` QA image · CI job + flag-coverage entry, negative-controlled |
| **B1** | Screen 2 — the stage | ⬜ **NEXT** | pipeline strip from the same mapping; NOW REVIEWING; padlocked Signed node with correct **N**; sheet is the existing paper component restyled; identity header; next-up peek; chat drawer | — |
| **B2** | Screen 3 — the gates | ⬜ TODO | full-screen sequential over EXISTING logic; only applicable gates exist; `> OVERRIDE` typed input unchanged; E/M only when `emApplies`; attestation; **sign-block E2Es pass with semantics unchanged** | — |
| **B3** | Screen 4 — signed + deck-advance | ⬜ TODO | strip fully checked; lock banner; safety trail shows **only what applied**; addendum footer; deck advances to next in-review | — |
| **B4** | Gate B verification | ⬜ TODO | axe zero serious/critical on stage + all gates + signed · chromium E2E incl. sign-block · **fixture matrix both specialty classes** (imaging: no E/M gate, no strip blocker, anywhere) · **PDF/Word parity re-proven at 1440** · screenshots · merge on green | — |
| **C1** | Auth / settings / templates / error-empty-loading | ⬜ TODO | all to tokens; copy register: plain verbs, sentence case, actions keep their names end-to-end | — |
| **C2** | Default-paper typography + Gate C | ⬜ TODO | **exports match preview 1:1** (this is the report-template design deliverable) · axe on every restyled screen **incl. waitlist** · full suite + typecheck · E2E green · merge on green | — |
| **F** | Flip + old-skin retirement + prod smokes | ⬜ TODO | walker map updated, run on QA, `ok:true` · MOCK posture green · tag `:pre-rounds-<date>` **first** · flip via `scripts/deploy-prod.sh` only · **delete** old skin after the flip verifies · rollback docs updated · both prod smoke walks · standing checks green · co-tenants verified | — |

---

## Parked, with reasons

| Thing | Why | Un-park when |
|---|---|---|
| **Vitals chips** on the paper (Screen 2) | The spec reserves the slot and says **build it only when structured vitals exist — parked, never faked.** L3 has a `measurements` slot but no vitals shape. | Structured vitals land in the extractor |
| **Failure-stage precision** on the Board | `transcribe_visits` records the terminal status only, so a FAILED lane's stub stops at the last *known* stage and at stage 1 with no history. Claiming further progress would be fiction. | A status-history column exists |

---

## What A2 found (read before B1 — the same traps apply)

Four defects, none visible in a screenshot:

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
