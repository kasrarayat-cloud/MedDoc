# C1 — an execution shape, NOT a set of established facts

**Status: UNVERIFIED PLAN. Re-check every load-bearing claim before acting on it.**

This was produced by a read-only scoping pass on 2026-07-31, immediately after B4
closed. It is kept because it is far cheaper to correct a concrete plan than to
rediscover the surface area — but it is exactly the kind of artefact this project
has been burned by before.

Two rules from `AGENTS.md` apply to this file directly:

- *"A backlog that predates a rewrite is a list of guesses until it is
  re-validated."* Six of sixteen Q1 findings had been closed by later work and
  nobody had marked them.
- The Template Twin audit corrected **17 of 24 load-bearing claims** under
  challenge — a 71% correction rate — and that was the cost of illegibility, not
  of carelessness.

So: **re-run each claim's own evidence query before you act on it.** The file
cites paths and line numbers precisely so that is cheap to do.

## Corrections already made to this plan, on the day it was written

1. **`NEXT_PUBLIC_TEMPLATE_NATIVE_PDF` is NOT currently broken.** The plan says
   the missing `ARG` in the Dockerfile is *"the exact failure that shipped the
   first flag-ON build with the old skin"*, implying the shipped feature is dead.
   It is not. Both readers are **server-side** —
   `src/app/settings/page.tsx:49` (a server component) and
   `src/lib/pdf-native/export.ts:10` — so `process.env` is read at RUNTIME on the
   server, where `docker-compose.yml:646` does supply it. Verified: 0 surviving
   reads of that name in the shipped prod client chunks, against a positive
   control (53 chunks scanned).

   The trap is **latent, and worth closing anyway**: the `NEXT_PUBLIC_` prefix
   promises build-time inlining that never happens for this var, and there is no
   `ARG` in the Dockerfile at all. The first time anyone reads it from a client
   component it silently becomes `undefined` → `false`, the feature dies, and
   nothing errors. Add the `ARG`+`ENV` as hardening, but do not describe it as a
   live outage.

2. **Gate C belongs to C2, not C1.** The plan is right about this and it is worth
   repeating here: `RELAY.md`'s C1 row asks for *"all to tokens; copy register"*.
   The axe-on-every-restyled-screen clause is C2's.

---

## VERIFICATION PASS — 2026-07-31, before C1-b was written

56 load-bearing claims were re-checked against the tree at `11fa33fd`, each by
re-running its own evidence query. **31 CONFIRMED · 16 DRIFTED · 9 WRONG** — a
45% correction rate, in line with this repo's history and exactly why the file
carries the header above. **The corrections below OVERRIDE the body of this
document.** Where they disagree, these win.

### The one that would have shipped a silent visual bug

**`--rounds-surface-0` DOES NOT EXIST.** §D1's code sample names it.
`rounds-tokens.css` declares `--rounds-surface-1/2/3` (`:27-29`) and
`--rounds-stage-bg-1/2/3` (`:23-25`); there is no `-0` anywhere in `src/`.

Copying that sample verbatim does not fail loudly — it is invalid-at-computed-
value-time, so `--color-linear-bg` becomes unset and `background-color` falls to
its **initial value: transparent**. Proven in headless chromium: the plan's exact
rule computes `rgba(0,0,0,0)` and shows the stage through the surface, with **no
build error, no console error, no CSS parse error.** Written against
`--rounds-surface-1` it computes `rgb(22,27,36)` correctly.

> **Use `--rounds-surface-1`.** And C1-b's guard #2 must assert every token on the
> **right-hand side** of the bridge block is declared — as specified it only
> checks the left-hand names, so it would not have caught this.

### The mechanism itself — CONFIRMED, and stronger than claimed

- The bridge works. Proven empirically, not reasoned: reproducing the real
  cascade (`@layer theme{:root,:host{…}}` + an unlayered host rule), an inline
  `style="color: var(--color-linear-text)"` inside the host computed to the
  Rounds value, a deep descendant retinted, and a negative control **outside**
  the host kept the old-skin value.
- **`data-skin` is on `<html>` in the ROOT layout** (`src/app/layout.tsx:110`),
  and there are exactly two `layout.tsx` files of which only the root renders
  `<html>`. So **every** auth route is inside `[data-skin='rounds']` — the risk
  flagged as "the one that kills the idea if wrong" does not exist.
- **`rounds-tokens.css` contains no `@layer` and is imported AFTER `globals.css`**
  (`layout.tsx:17-18`), so the bridge lands unlayered and beats `@layer theme`
  unconditionally. There is no specificity fight to lose.

### Numbers that were inflated

| Claim | Real value |
|---|---|
| "~560 inline style objects" | **434** on the plan's own strict surface list (477 on a superset); **472 / 516** including the 40 module-level `CSSProperties` consts |
| "the 19 names C1 surfaces read" | **22** — a bridge written to 19 leaves 3 colours on old-skin values, which renders as *one component looking wrong on a correct screen* |
| "~40 objects need forking" | **~33** carry any colour literal. **60.4% (285/472) come to tokens for free** |
| "~9,600 lines of restyle without D3" | re-derive; it inherits the 22–29% inflation |

### D2 — two rulings were right for the wrong reason, and one flag was misread

- **⚠️ `settings/page.tsx`'s two-branch split is gated by `isSkinBeta()`
  (`:226`), NOT by `SETTINGS_SIMPLE_ROW`.** `isSettingsSimpleRow()` is read at
  exactly ONE place in that file — `:214`, inside `nativeSlot` — and only decides
  whether `NativeTemplateManager` mounts, **inverted**:
  `templateNativeDocxEnabled() && !isSettingsSimpleRow()`.
  A rollback setting `SETTINGS_SIMPLE_ROW=false` expecting the legacy layout gets
  the C3 rail **plus a resurrected `NativeTemplateManager`** — the opposite of the
  intent. Verified behaviourally on the flag-ON image: `Native template` absent,
  37 `qm-c3-set*` nodes present.
- **The Linear split-screen fallthrough is LIVE IN TWO CI ENVIRONMENTS,** not
  one. `e2e.yml:95-98` builds the default images with `SKIN_BETA: "false"` and
  `:219-225` runs `--project=chromium` against them, so every login in the
  default pack renders it. **Treat it as covered by the required e2e gate.**
- **`docker inspect` / `docker exec … env` is NOT evidence of what the prod image
  was BUILT with.** Every `NEXT_PUBLIC` ARG/ENV lives in the `builder` stage only;
  the `runner` stage carries none, and compose injects `.env` at runtime — where
  `NEXT_PUBLIC_SKIN_BETA` is **absent** despite being `true` in the build. Anyone
  checking that way concludes SKIN_BETA is OFF and picks the wrong branch.
- **A bundle grep cannot discriminate which branch is live** — both survive
  minification (`qm-c3-auth` and `qm-auth-grid` are both in the shipped chunks).
  Only the flag value plus a DOM read of the served route counts.

### Line numbers that would corrupt an edit

Several cited end-bounds stop short of the closing JSX, and one crosses a
function boundary. **Anchor by content, never by these numbers.**

| Cited | Real |
|---|---|
| auth-shell fallthrough `:103-366` | **`:103-369`** (`:367-368` are `</div>`, `:369` is `);`) |
| settings legacy `:538-901` | **`:538-902`** |
| TemplateRow simple `:770-908` | **`:770-905`** (`:908` is a shared comment) |
| TemplateRow legacy `:909-968` | **`:909-965`** — **`:968` is inside `EntryState`**, a component this plan lists nowhere |
| `color:'#fff'` at board.tsx `:259` | **`:260`** — `:259` is `background: 'var(--rounds-accent)'`, so an edit at `:259` changes the background instead of the white text |
| `/board` 404 gate at `page.tsx:17-18` | **`:76`** (`if (!isSkinRounds()) notFound()`), predicate `skin-rounds.ts:42-44`. `:17-18` is **prose** — the fourth instance of the comment-vs-code hazard in this file set |
| `isStaleDeploymentError` "Reload branch" at `:57` | `:57` is the **memo**. There are **FOUR** `isStale` fork sites: `:147`, `:160-162`, `:192-202`. The dev route must exercise both branches of all four |
| signup checkbox locators `14-auth:33`, `:66` | **`:32`, `:65`** — `:33`/`:66` are the next statement (the button click). The three unqualified `getByRole('checkbox')` in the suite are `signup.ts:43`, `14-auth:32`, `:65` |

### Four more, each changing what a session would do

1. **`RoundsEmptyState` does not exist as a symbol.** `grep -rn RoundsEmptyState
   src/` returns zero; the only hit in the repo is this plan. `board.tsx:219-271`
   is an unnamed early return. This is a **naming decision, not a relocation** —
   and its existing `data-testid="rounds-board-empty"` must survive extraction.
2. **`visits/[id]/loading.tsx` does not draw "the old tabbed layout".** It is 40
   lines: an **empty** 56px bar, a chip row, a title line and two content blocks.
   The rewrite is still justified (`max-w-4xl` against an 820px paper is a real
   shape contradiction) but the ledger must not record a false before-state.
3. **38 spec files import the signup helper, not ~40** — and all five Rounds
   packs *call* it, not merely import it. The prohibition stands at full strength.
4. **`signup-form.tsx:114`'s underline carries NO comment.** The only
   `link-in-text-block` comment in the repo is `waitlist-form.tsx:137`. That
   underline sits against the file's own `linkStyle` default of
   `textDecoration:'none'`, so it reads as an inconsistency a restyle would tidy
   away. **Carry the waitlist comment across to it.**
5. **The `14-auth-signup-onboarding` test is not wholly vacuous.** Only `:70-71`
   is the defect; `:72` (`toHaveURL(/\/signup$/)`) and `:81` (the credential
   replay proving the account was never created) have teeth. **Do not delete the
   test — fix the one assertion.**

---

# C1 EXECUTION SHAPE

**Verified against the tree at `34267bb6` (branch `feat/rounds-b4-shots`).** RELAY.md:117 is C1's row; :118 is C2's — Gate C (axe on every restyled screen incl. waitlist) is **C2's exit criterion, not C1's**. C1's own gate is *"all to tokens; copy register"*. C1's obligation is to leave those surfaces **axe-provable and photographable**, and to hand C2 a harness that cannot go green vacuously.

---

## 0. The three decisions that must be made before any code is written

These are not design choices; they are the mechanism choices every split depends on. Make them in C1-b and record them in the ledger.

### D1 — How a `[data-skin='rounds']` stylesheet reaches ~560 inline `style={{}}` objects

All three inventories hit this independently and each proposed the same three options. The answer is **none of them as stated** — it is a fourth, and it is the load-bearing idea in this plan:

> **A SCOPED custom-property bridge.** Not `:root[data-skin='rounds']` (rejected: repaints admin/patients/visits — a replacement, not an addition). A **host class**:
> ```css
> [data-skin='rounds'] .qm-rounds-host { --color-linear-bg: var(--rounds-surface-1); --color-linear-text: …; /* the 22 names C1 surfaces actually read — SEE THE VERIFICATION PASS: --rounds-surface-0 does not exist and ships transparent */ }
> ```
> applied to the **root element of each C1 surface only**. Custom properties resolve at computed-value time and inherit, so an inline `style={{ color: 'var(--color-linear-text)' }}` **does** pick it up. Flag-OFF: the class attribute is present, no rule matches, zero pixels move — provable by inspection, not by a snapshot.

The bridge carries **colour and nothing else**. Shape, type, radius and spacing still need real classes, and for those the contract is:

**The C1 restyle contract (four rules, pinned by a unit test in C1-b):**
1. **Never mutate an existing style object or class.** Spread a Rounds delta: `style={{ ...inputStyle, ...(rounds ? roundsInput : {}) }}`. `isSkinRounds()` is build-time, so flag-OFF is byte-identical *by construction* — no computed-style pin needed.
2. **Every node whose appearance Rounds changes carries a `qm-rounds-*` class**, applied only when the flag is on. This is not decoration — it is the **currency the axe ownership rule spends** (`rounds-a11y.spec.ts:247`, `ROUNDS_OWNED = /qm-rounds-/` over the nearest classed ancestor-or-self). A restyled node without one is invisible to Gate C.
3. **Colour-only nodes get neither** — they inherit through the host bridge. This is what keeps the diff at ~40 forked objects instead of 560.
4. **No token naming a STATE or a FILL is used as text without its `-text` sibling** (`rounds-tokens.css:69-79`).

### D2 — Which branch of each two-branch file is real

| File | Branch that ships | Ruling |
|---|---|---|
| `/opt/meddoc-pro/apps/transcribe-md/src/components/ui/auth-shell.tsx` | `isSkinBeta()` → `qm-c3-auth` card (:69). Prod `docker-compose.yml:543` defaults SKIN_BETA **true**; `:rounds` image builds `--build-arg NEXT_PUBLIC_SKIN_BETA=true` (`e2e.yml:283`) | Restyle the **C3 branch only**. **Do not add a third branch.** The Linear split-screen (:103-366, incl. the `!important` `<style>` block at :114-130) is dead in every environment except the `a11y.yml` job, which is old-skin territory. |
| `/opt/meddoc-pro/apps/transcribe-md/src/app/settings/page.tsx` | C3 section-rail (:226-536) | Restyle C3 only. Legacy stacked (:538-901) = **SKIP**, ledger-recorded. |
| `note-format-manager.tsx` `TemplateRow` | simple row (:770-908) once C1-a lands | Restyle simple only. Legacy (:909-968) = **SKIP**. |
| `native-template-manager.tsx` | **neither** — `true && !true` = null in prod | **PARK** (see §4). |

### D3 — Three restyle *levels*, assigned per surface, recorded in the ledger

- **FULL** — forked style objects + `qm-rounds-*` classes + new shape/type. Gets screenshots and axe.
- **BRIDGE** — host class only, zero markup change. Colour comes to tokens; geometry stays. Legitimate for "to tokens" and honest about it.
- **SKIP** — untouched, named in the ledger with the reason.

Without D3 written down, C1 is ~9,600 lines of restyle. With it, FULL is ~1,400.

---

## 1. The split — seven PRs, dependency order

### C1-a · `ci(rounds): the :rounds image builds the settings production ships`
**No product code. Merge this first and alone.**

- `/opt/meddoc-pro/.github/workflows/e2e.yml:280-289` — add `--build-arg NEXT_PUBLIC_SETTINGS_SIMPLE_ROW=true`, `NEXT_PUBLIC_DOC_PREVIEW=true`, `NEXT_PUBLIC_TEMPLATE_NATIVE_PDF=true`, `NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX=true`, `NEXT_PUBLIC_VISIT_DOC_PAGE=true` (the last two are B4's named inheritance to C2 — pay them here).
- ⚠️ **`/opt/meddoc-pro/apps/transcribe-md/Dockerfile` does NOT declare `ARG NEXT_PUBLIC_TEMPLATE_NATIVE_PDF`** (declared: SKIN_BETA:74, SKIN_ROUNDS:82, ULTRASOUND:93, TEMPLATE_NATIVE_DOCX:104, UX_SIMPLIFY:114, REVIEW_DOC_VIEW:123, SETTINGS_SIMPLE_ROW:128, DOC_PREVIEW:130, VISIT_DOC_PAGE:132, CHAT_EDITOR:134). Docker discards an undeclared build-arg **silently** — this is the exact failure that shipped the first flag-ON build with the old skin. Add ARG+ENV at :128.
- `/opt/meddoc-pro/apps/transcribe-md/src/lib/__tests__/gate-flag-coverage.test.ts` — five new rows in the `:rounds` `needs` list, each with its `why` in the file's established voice.
- `/opt/meddoc-pro/docker-compose.qa.rounds.yml` — header comment updated (it already lists the build line; a stale comment here is how the next reader builds the wrong image by hand).

**Proves:** units (`gate-flag-coverage`, `gate-project-env`) + **the merge-commit `e2e` run with all five existing Rounds packs re-executed**. Verify the inlining grep on the new chunk (0 surviving runtime reads, against a positive control), per AGENTS.md.
**New project:** no.
**Budget one red cycle.** B4 explicitly warned this perturbs `rounds-board/stage/gates/signed`. `DOC_PREVIEW` changes the visit doc surface `rounds-stage` and `rounds-signed` render. That is the point of merging it alone: a red here is unambiguous.

---

### C1-b · `feat(rounds): C1 foundation — control tokens, the host bridge, and the authority doc`
**Touches:**
- `/opt/meddoc-pro/apps/transcribe-md/src/app/rounds-tokens.css` — (i) close the state-token debt: `--rounds-processing-text` (`#3b6fd4` is ~3.0:1 on `--rounds-surface-1`), `--rounds-em-text` (`--rounds-em-fill` is *lighter*, a fill not a text colour), `--rounds-danger` + `--rounds-danger-text` (the Danger zone and `delete-account-dialog.tsx` hardcode `rgba(212,87,74,·)` at five alphas; only `--rounds-critical-on-dark` exists). (ii) The **control primitive layer** that does not exist today: `.qm-rounds-field`, `-label`, `-input`, `-textarea`, `-select`, `-check`, `-error`, `-help`, `-link`, `-btn`, `-btn-secondary`, `-btn-danger`, `-btn[disabled]`, `-panel`, `-alert`, `-pill`, `-skeleton`. (iii) `.qm-rounds-host` — the D1 bridge.
- `/opt/meddoc-pro/docs/design-tokens.md` — new **Controls** and **States** sections. This file calls itself the authority; C1 invents the vocabulary settings and templates will both use, so amending it here is not paperwork, it is the thing that stops the next session guessing.

**Proves:** units only. Extend F0's exhaustiveness guard with three new assertions, each **negative-controlled**: (1) every `--rounds-*` token naming a state or fill has a `-text` sibling; (2) every `--color-linear-*` name read by a file on the C1 surface list appears in the bridge block (grep-driven — the failure mode is a bridged screen with one unbridged colour, which reads as a bug in one component); (3) the four C1-restyle-contract rules where they are statically checkable (no `qm-rounds-*` class in a file that has no `isSkinRounds()` import).
**New project:** no. **Zero runtime change** — nothing applies `.qm-rounds-host` yet.

---

### C1-c · `feat(rounds): error, empty and loading — and a door to render them`
**Touches (FULL):**
- `/opt/meddoc-pro/apps/transcribe-md/src/components/error-fallback.tsx` (225) — the single component behind all five `error.tsx` shims. Preserve the `sendBeacon` to `/api/client-errors` (:59-93) and the `isStaleDeploymentError` "Reload" branch (:57) exactly.
- `/opt/meddoc-pro/apps/transcribe-md/src/app/not-found.tsx` (116) and `src/app/visits/[id]/not-found.tsx` (65). The root 404 pulls in `AnimatedGrid` + `GradientText` + a sage radial — **delete-and-replace under the flag fork**, not a token swap; the Rounds stage is its own radial treatment.
- `/opt/meddoc-pro/apps/transcribe-md/src/components/skeleton.tsx` (148) — the one already-class-based states file. Pure `[data-skin='rounds']` rules, no markup change.
- `/opt/meddoc-pro/apps/transcribe-md/src/app/visits/[id]/loading.tsx` — **rewrite**: it draws the old tabbed layout (56px bar, three chips, `max-w-4xl`) while Rounds renders an 820px paper on the stage. A skeleton whose shape contradicts what resolves is worse than none.
- **New** `/opt/meddoc-pro/apps/transcribe-md/src/app/board/loading.tsx` — `/board` has `page.tsx` and nothing else. Needs a lane-shaped skeleton; add `SkeletonRoundsLane` to `skeleton.tsx`.
- **Extract** `RoundsEmptyState` from `/opt/meddoc-pro/apps/transcribe-md/src/components/rounds/board.tsx:219-271` (currently inlined, unexported, hardcoded copy, `color:'#fff'` literal at :259) and re-point the board at it. This touches A2's merged surface — **justify in the ledger**. It is the right trade: the extracted component is where the `qm-rounds-*` class rule 2 demands actually hangs, and it kills the second white-on-accent literal.
- **Recovery-destination fork.** `not-found.tsx:94`, `visits/[id]/not-found.tsx:57`, `error-fallback.tsx:203-220` all send the doctor to `/dashboard`, which is not in the Rounds nav (`board-chrome.tsx:132` is `/board`). Fork on `isSkinRounds()` — **never a hard swap**: flag-OFF `/board` 404s by design (`app/board/page.tsx:17-18`), so a swap builds a 404 loop.
- **New** `/opt/meddoc-pro/apps/transcribe-md/src/app/dev/states/page.tsx`, modelled exactly on `/opt/meddoc-pro/apps/transcribe-md/src/app/dev/rx-warnings/page.tsx` (dev-only, `notFound()` in production builds): a `?throw=1` trigger for the boundary, both `isStaleDeploymentError` branches, every skeleton, every `EmptyState` kind, both 404 bodies. **This is the split's real deliverable.** `scenarios/27-error-resilience.spec.ts:16-21` says in source that the boundary cannot be deterministically forced without a throw route; a `loading.tsx` paints for <100ms on the QA stack. Without this route, Gate C cannot cover the one component behind all five `error.tsx` files, and CDP throttling would flake.

**Proves:** units — the dev route returns `notFound()` when `NODE_ENV==='production'` (negative-controlled), the recovery destination is `/board` iff the flag is on, the beacon and stale-deploy branches still fire. Plus the existing default `chromium` run (`27-error-resilience.spec.ts` drives both 404s today) stays green, unchanged, flag-OFF.
**New project:** no.
**EmptyState scope:** restyle `/opt/meddoc-pro/apps/transcribe-md/src/components/ui/empty-state.tsx` itself (BRIDGE + a Rounds fork), but do **not** touch its only three call sites — `app/patients/page.tsx:155,:282` and `app/visits/page.tsx:187`. Those routes are not in SPEC's "Also restyle", not Rounds screens, and not in the Rounds nav. See §4.

---

### C1-d · `feat(rounds): auth to tokens — and the pack that can prove it`
**This is the ONE split that pays the full six-part flag-ON pack chain.**

**Touches (FULL):**
- `auth-shell.tsx` — the `qm-c3-auth` branch only: add `qm-rounds-host qm-rounds-auth` to its wrapper; override `.qm-c3-auth*` (globals.css:5233-5330) under `[data-skin='rounds']`. `AuthFieldLabel` (:387) and `AuthFieldError` (:424) get forked objects + `.qm-rounds-label` / `.qm-rounds-error` (taking `--rounds-critical-on-dark`, **not** `--rounds-critical`).
- Six page.tsx files (~207 lines, mostly copy props) — **where the copy-register work lands**. Preserve `/login`'s `robots:{index:true}` override (`login/page.tsx:15`) and `/waitlist`'s deliberate no-`auth()`-no-redirect (`waitlist/page.tsx:9-14`).
- Six forms — **BRIDGE for the ~60 colour-only objects, FULL for the ~40 that carry shape** (inputs, buttons, panels, banners). `login-form.tsx`'s five stateful sub-screens (MFA :146, recovery :187, crossAppRedirect :227, needs-verification :260), `waitlist-form.tsx`'s success panel (:30-47), `forgot-password-form.tsx`'s submitted panel (:71-113), `reset-password-form.tsx`'s no-token (:55-87) and done (:119) states — each gets its treatment **and its driven state in the pack**.
- `waitlist-form.tsx:105-124` — its submit button is the only inline-styled primary in the product; class it `qm-rounds-btn`.

**Hard prohibitions (each is a red suite, not a red test):**
- `waitlist-form.tsx:136-147` and `signup-form.tsx:114` — the `textDecoration:'underline'` on the `/signup` and `/waitlist` links is a **recorded axe fix** (link-in-text-block, SERIOUS). It survives verbatim.
- `signup-form.tsx` — the accessible names `Invite code` / `Full name` / `Email` / `Password` (exact) / `Confirm password`, the `htmlFor`↔`id` association, the single `getByRole('checkbox')`, and `create account` are a **contract held by 40 spec files** via `/opt/meddoc-pro/apps/transcribe-md/tests/e2e/helpers/signup.ts:35-43` — including all five Rounds packs. **No second checkbox on `/signup`** (a show-password toggle is the obvious Rounds-era addition and it throws Playwright strict mode at `signup.ts:43`, `14-auth-signup-onboarding.spec.ts:33` and `:66`).
- Do not touch `src/actions/auth.ts`, `src/lib/signup-invite.ts`, or `auth-schemas.ts`. Skin-only.

**The new pack — `rounds-c1`. All six items, in one PR:**
1. `/opt/meddoc-pro/apps/transcribe-md/playwright.config.ts` — new project after `rounds-a11y` (:218), `testMatch: ['**/rounds-c1.spec.ts']`.
2. Same file, chromium `testIgnore` (:80) — with the comment in the established voice: *`/login` and `/settings` EXIST flag-OFF, so omitting this line does not 404 — it fails on missing Rounds testids while the old skin renders perfectly. A2 defect 0's slower variant.*
3. `/opt/meddoc-pro/.github/workflows/e2e.yml` — a **contiguous** `recreate on :rounds → --project=rounds-c1` block, appended after the `rounds-a11y` step at :377-382 and **before** the artifact upload. Nothing between the recreate and the run.
4. `gate-flag-coverage.test.ts` — the `:rounds` `needs` list already covers it after C1-a; add the project→spec pairing row.
5. `gate-project-env.test.ts` — `'rounds-c1': ['docker-compose.qa.rounds.yml']` in `EXPECTED`.
6. `/opt/meddoc-pro/apps/transcribe-md/tests/e2e/scenarios/rounds-c1.spec.ts` — new.

**Pack construction rules (non-negotiable, each is a recorded past failure):**
- **Extract** the ownership adjudicator, the `incomplete` bucket and the two-part positive control out of `rounds-a11y.spec.ts` into `tests/e2e/helpers/rounds-axe.ts` and have **both** packs import it. A copy means the ownership rule drifts and B4's fix decays.
- **Widen the positive control** to a C1-shaped node: today it plants a violation on a classed Rounds element and on a classless one inside a Rounds container. Add a third: a **bridged** node (host class on the ancestor, no `qm-rounds-*` of its own). If that case is classified as inherited, say so in the header — it is the D1 bridge's blind spot and C2 must know it.
- **`requireSeed()`, never `test.skip(!seeded)`.** `a11y.spec.ts:294-303` is one of the untreated ones (B3: eleven never-run tests exiting 0).
- **Cleared contexts per auth route.** `/login`, `/signup`, `/forgot-password`, `/reset-password` each `auth()`+`redirect('/dashboard')` inside the server component (there is **no middleware.ts** anywhere in the app). A pack holding `storageState` screenshots a dashboard redirect and exits 0. Copy `a11y.spec.ts:310`'s posture.
- **Screenshots to `rounds-shots/`** (outside every `outputDir`), `if: always()`, `if-no-files-found: error`. B4 defect (1).
- **Synthetic values only** into `?email=` and `?token=` — `check-email/page.tsx:14-29` interpolates the raw query value into rendered prose and the artifact is retained by CI.

**Also fix, and say so:** `14-auth-signup-onboarding.spec.ts:71` asserts `getByText(/invite-only during the pilot/i).first()`, which DOM-order-resolves to the **static** helper paragraph at `signup-form.tsx:113`, not the server refusal. It passes whether or not the gate fired. C1 rewrites both strings under the copy register; scope the assertion to `AuthFieldError` in the same PR or it keeps proving nothing in new type.

---

### C1-e · `feat(rounds): settings — the C3 rail and its panels`
**Touches (FULL):** `settings-sections-c3.tsx` (76 lines, already fully classed — the cheapest file in C1) + globals.css:5142-5231 overrides; `profile-form.tsx`; `change-password-form.tsx`; `session-panel.tsx` (both states — populated and the null fallback); the "Your data" and "Billing" inline panels (`page.tsx` C3 :376-421, :422-460 — Billing's permanently `disabled` button is a real disabled-state token treatment Rounds does not have yet); the Danger zone panel + `delete-account-dialog.tsx` (322) and `change-email-dialog.tsx` (345) — both modals, both on `--rounds-danger-text` from C1-b.
**BRIDGE:** `mfa/page.tsx` + `mfa-enrollment-panel.tsx` (416) + `mfa-management-panel.tsx` (329) — see §4.
**Extract first:** the 2FA status card is ~55 lines of inline JSX **duplicated verbatim** in both `page.tsx` branches (C3 :286-343, legacy :692-748). Extract to a component before restyling, or you restyle it twice and only one is real.
**Proves:** `rounds-c1.spec.ts` grows a settings describe — **activate the rail tab first**; all seven panels stay mounted with the `hidden` attribute and `.qm-c3-set-panel` sets no `display`, so `page.goto('/settings')` + `fill('#currentPassword')` (the pattern in `16-account-settings.spec.ts:45-48`, `5-note-format-upload-activate.spec.ts:52-53`, `helpers/noteFormat.ts:27-29`) **fails on a prod-shaped build**. The only working example is `doc-preview.spec.ts:40`.
**New project:** no — `rounds-c1` already exists.

---

### C1-f · `feat(rounds): templates — the note-format panel and its six views`
**Touches (FULL):** `note-format-manager.tsx` views `home` (:654-706), `entry` (:969-1063), `rejected` (:1078-1105, `role=alert`, hardcoded amber → `--rounds-em-*`), the simple `TemplateRow` (:770-908) incl. the `⋯` `role=menu`, the pills and the inline `NativeDocumentPreview` with its `preview===null` state; `upload-flow.tsx` `ProcessingStages` (:87-130) and `ConfirmCard` (:170-344) — 40 classNames / 4 inline styles, the one templates file a CSS-only override already reaches (`.qm-ux-proc*` / `.qm-ux-stage*` / `.qm-ux-confirm*`, globals.css:6122+).
**⚠️ `ProcessingStages` renders state as TEXT** (`.qm-ux-stage.is-active .qm-ux-stage-label`, globals.css:6197, plus a `role=status` live region). This is where `--rounds-processing` becomes the **fifth** instance of the named defect. Use `--rounds-processing-text` from C1-b. Non-negotiable.
**BRIDGE:** `template-review-editor.tsx` (927 lines, 92 objects) — see §4.
**Proves:** `rounds-c1.spec.ts` drives the state machine (`MOCK_AI_CALLS` + `NOTE_FORMAT_E2E=1`, the `helpers/noteFormat.ts parseToReview()` path). Six views are **client state behind one URL** — nothing is deep-linkable.
**Re-prove at 390px:** `template-review-editor.tsx:467`'s sticky action bar and the ConfirmCard actions are covered by `MobileNavC3`. The one hit-test assertion (`doc-preview.spec.ts:93-103`, `document.elementFromPoint`) lives in a pack whose image has no `SKIN_ROUNDS`. Port that assertion into `rounds-c1`. MEMORY records this being misdiagnosed once as a "React-19 save-button quirk".
**New project:** no.

---

### C1-g · `fix(rounds): the surface tells the truth about where things live`
Small, flag-independent, unit-provable, and it fixes a **live customer email** — merge it whenever it is ready, it blocks nothing.
- **`/settings/note-format` does not exist.** No `page.tsx` under `/opt/meddoc-pro/apps/transcribe-md/src/app/settings/note-format/` (components only), no rewrites in `next.config.ts`. `board-chrome.tsx:133` points the Rounds "Templates" nav item there → 404 today. So does `src/lib/email.ts:371`, pinned by `src/lib/__tests__/template-certified-email.test.ts:44-45`. **Create the route segment** (renders `/settings` with `note-format` preselected — `SettingsSectionsC3` needs an `initialSection` prop; it reads no hash, no query, no router sync today). Fixing the route rather than the link fixes the email too.
- **The 2FA card lies.** Both `page.tsx` branches (:338-341, :743-745) say *"TOTP setup + recovery codes UI lands in the next batch of Settings work"*. It shipped, at `/settings/security/mfa`, whose **only doors are a typed URL and `app/admin/layout.tsx:84`'s redirect**. Fix the sentence **and** add the link. Restyling a lie into new type is the failure this bullet exists to prevent.
- **Billing** — *"Stripe customer portal integration lands in the next Settings wave"* behind a permanently disabled button. Rewrite to the copy register; keep the button disabled.
- **Copy register sweep**, the whole of it: `/signup`'s *"Free for 14 days. No credit card."* subtitle predates invite-only and reads absurdly beside a required invite field. `VerifyToast`'s *'Request a new one from Sign in, then click "resend".'* names actions — hold them to *actions keep their names end-to-end*.
- **Proves:** units (the email test now passes against a route that exists) + one assertion in the **default chromium** project that `/settings/note-format` returns 200 and renders the manager — flag-OFF, cheap, real.
- **No nav-model work.** None of the five nav components (`sidebar-c3.tsx:23-25`, `top-nav-c3.tsx:12-15`, `top-nav.tsx:32-34`, `mobile-nav-c3.tsx:21-36`, `icon-rail.tsx:37-38`) contains a `/board` link, and `AppFrame` has no Rounds branch — a doctor who reaches Templates from the board has no way back. **That is a Screen-1 chrome problem, not C1's.** Record it as a finding for C2/D; do not absorb it.

---

## 2. Which splits need the full flag-ON pack chain

| Split | Product code | Units | Flag-ON E2E | Axe | **Full 6-part chain?** |
|---|---|---|---|---|---|
| C1-a | none | ✅ + re-run of 5 Rounds packs | inherits | inherits | **no** |
| C1-b | none (tokens only) | ✅ 3 negative-controlled guards | — | — | **no** |
| C1-c | ✅ | ✅ | — (dev route + existing chromium) | deferred to C1-d's pack | **no** |
| **C1-d** | ✅ | ✅ | **new `rounds-c1` pack** | ✅ (shared helper) | **YES — the only one** |
| C1-e | ✅ | ✅ | grows `rounds-c1` | ✅ | no |
| C1-f | ✅ | ✅ | grows `rounds-c1` | ✅ | no |
| C1-g | ✅ | ✅ | default chromium | — | no |

**One new project for all of C1**, not four. Each project costs a full image recreate in a 55-minute job, and `gate-project-env.test.ts` demands a contiguous block per project. Rationale for `rounds-c1` over extending `rounds-a11y`: `rounds-a11y`'s `beforeAll` signs a user up and walks authenticated, which **contradicts** the cleared-context posture six auth routes require; and keeping Gate B's pack byte-unchanged means a C1 red can never be misread as a Gate B regression — which is precisely the diagnosis cost `gate-project-env` was written to eliminate. The axe *logic* is shared via `helpers/rounds-axe.ts`, so there is one ownership rule, not two.

---

## 3. Traps, ranked by expected CI cost

1. **C1-a's flag additions redden `rounds-board/stage/gates/signed`.** `DOC_PREVIEW` and `VISIT_DOC_PAGE` change the visit surface those packs walk; `SETTINGS_SIMPLE_ROW` changes `TemplateRow`. B4 named this and deferred it. ~55 min per cycle, likely ≥2. **Merge C1-a alone so a red is unambiguous.**
2. **`TEMPLATE_NATIVE_PDF` has no `ARG` in the Dockerfile.** Docker discards it *silently*. The build goes green, the image is wrong, and the pack fails somewhere else entirely. Verified above — declare it at Dockerfile:128, and confirm by the inlining grep on the shipped chunk, never by reading env.
3. **The axe gate goes green vacuously on every C1 surface.** `grep -rn qm-rounds app/settings/ app/login/ app/signup/ app/waitlist/ app/not-found.tsx components/error-fallback.tsx components/ui/empty-state.tsx components/skeleton.tsx` returns **zero**. Ownership climbs to the nearest classed ancestor — a `qm-lin-*`/`qm-c3-*` node, or `<body className="min-h-screen antialiased">` — and every violation is logged as inherited, not gated. `violations: []` while measuring nothing. This does not cost a cycle; it costs the gate, silently, which is worse. **Cure: contract rule 2, plus the third positive-control case.**
4. **The D1 mechanism decided *after* implementation starts.** All three inventories independently proposed the same three losing options. If a session starts restyling `login-form.tsx` before D1 is written down, the work is thrown away. **C1-b exists to prevent exactly this.**
5. **`signupFreshUser`'s selectors.** `helpers/signup.ts:35-43` is imported by 40 specs including every Rounds pack. Break a label association or add a second checkbox to `/signup` and the **entire suite** reds — auth, rounds, a11y, mobile-tap-targets, doc-preview. ~55 min, and the failure reads as "Rounds broke everything".
6. **Missing chromium `testIgnore` entry for `rounds-c1`.** `/login` and `/settings` exist flag-OFF, so no fast 404 — the default run fails on missing testids while the old skin renders correctly, *before* the step that builds the flag-ON image runs, so the pack the line protects never executes. `gate-flag-coverage.test.ts` catches it in a unit, **if** the row is added.
7. **`gate-project-env` ordering.** The `rounds-c1` recreate→run block must be contiguous and must not be inserted between another pack's recreate and its run. The 2026-07-29 precedent cost 25 of 55 minutes and pointed at innocent code. Caught in 30 ms by the unit — *if the `EXPECTED` row is added in the same PR*.
8. **Restyling `auth-shell.tsx`'s split-screen or `settings/page.tsx`'s legacy stack.** ~1,000 lines that render in no environment that matters. Costs a session, not a cycle — and leaves a third visual vocabulary in the tree at the F flip.
9. **State-token-as-text, instances five and six.** `--rounds-processing` (no text variant at all) on the note-format processing label; `--rounds-em-fill` (lighter, a fill) used as text on the rejected card; no `--rounds-danger` at all for the Danger zone. Closed by C1-b before any surface can reach for them.
10. **Dropping the `/waitlist` and `/signup` link underlines.** A recorded SERIOUS axe fix on the highest-traffic unauthenticated page — the one Gate C names by name — and today nothing flag-ON would catch its removal.
11. **`test.skip(!seeded)` in the new pack.** B3 proved eleven never-run tests exiting 0; *"can I reach the database"* and *"did this seed succeed"* are different questions. `requireSeed()` from the first line.
12. **`page.goto('/settings')` then fill.** Six of seven panels carry `hidden` on a prod-shaped build. Every existing settings spec works only because chromium pins `SKIN_BETA=false`.
13. **Screenshots into `test-results/`, or a real `?email=` in the URL.** B4 defect (1): four later `playwright test` invocations `fs.rm` every `outputDir`, so on a green run zero screenshots leave the runner. And `rounds-shots/` is uploaded and retained — synthetic query values only, and shred `.playwright-mcp/` + `/tmp` at session close.
14. **The invite field clears on rejection.** `actions/auth.ts:413` omits `inviteCode` from `values`; `signup-form.tsx:101` reads `values.inviteCode ?? ''`. Invisible today, conspicuous the moment the field gets a Rounds error treatment. **Record the decision; do not change the action's return shape in a skin-only item.**

---

## 4. PARKED — with the trigger written down

- **`native-template-manager.tsx`** (473 lines, 34 inline objects). Mounted at exactly one call site, `settings/page.tsx:215`, behind `templateNativeDocxEnabled() && !isSettingsSimpleRow()` — prod sets both true, so it is `null`. Zero production screens; Gate C cannot photograph it. **Un-park trigger: `NEXT_PUBLIC_SETTINGS_SIMPLE_ROW` goes false in production, or the Template Twin park is lifted — i.e. a pilot doctor explicitly needs their native form bytes back.** Nothing else. (AGENTS.md already records this as the deliberate steady state; do not re-diagnose it.)
- **The old-skin branches: `auth-shell.tsx:103-366`, `settings/page.tsx:538-901`, `TemplateRow` :909-968.** Dead in prod and on the `:rounds` image; still compiled and still shipped. They are old-skin territory and the `a11y.yml` flag-OFF run is the only thing that sees them. **Un-park trigger: none — item F deletes the old skin and they die with it.** If F slips past the pilot, revisit.
- **`template-review-editor.tsx` (927 lines, 92 objects, 80 `--color-linear-*` reads) — BRIDGE only.** Colour comes to tokens through the host class; geometry, the sticky action bar and the five sub-components (`SectionCard`, `SafetyCallout`, `StructureOutline`, `SampleMarkdown`, `SamplePreview`) keep their shape. It is the densest file in C1 and reachable only via ConfirmCard's *"Something's off"* or `⋯` → *Advanced editor*. **Un-park trigger: a pilot doctor edits a template through the advanced editor, or a template lands whose parse the ConfirmCard cannot confirm.**
- **`mfa/page.tsx` + the two MFA panels (~880 lines) — BRIDGE only.** C1-g gives them a door, so they must be bridged and axe-walked; they must not be redesigned. **Un-park trigger: MFA becomes required for pilot doctors, or the settings 2FA card shows real traffic.**
- **`app/dashboard/loading.tsx`.** Its four-cell stats row and eight-row list draw the dashboard, and the dashboard is not a Rounds screen — Rounds' home is `/board`. **Un-park trigger: `/dashboard` enters the Rounds nav, or item F.** (`visits/[id]/loading.tsx` is **not** parked — it precedes Screen 2 and is rewritten in C1-c.)
- **`EmptyState`'s call sites: `app/patients/page.tsx:155,:282` and `app/visits/page.tsx:187`.** The component is restyled; the pages are not. Neither is named in SPEC's "Also restyle" (:171-174), neither is a Rounds screen, and neither appears in `board-chrome.tsx`'s three nav links. **Un-park trigger: either route enters the Rounds nav.**
- **`AppFrame`'s missing Rounds branch and the absent `/board` link in all five nav components.** A doctor who reaches Templates from the board is stranded in old-skin chrome. This is a Screen-1 chrome defect, not a restyle. **Un-park trigger: it is C2's or D's to own — raise it in the ledger when C1-g merges, and do not absorb it into C1.**

---

## Relay bookkeeping

C1 is one ledger row and seven merge commits. Per **rule 2a**, the row is not `DONE` until the **last** PR's merge-commit CI is cited by run id — `CI`, `e2e`, `secrets-scan`, all success, and the `e2e` run read **step by step** to confirm `rounds-c1` **executed** and does not read `skipped`. A cancelled run is absence of evidence. Per **rule 2b**, no pushes while an E2E run is in flight. `NEXT_PUBLIC_SKIN_ROUNDS` stays **OFF** through all seven — every C1 change ships dark, and the only place the skin is ever seen is a separately-tagged `:rounds` image on the isolated QA stack.