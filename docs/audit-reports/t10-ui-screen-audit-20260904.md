# T10 — every-screen UI audit

**Run 2026-09-04 by the Data/Audit session. READ-ONLY: no product code was changed.**
**Filed for the UI/design session. Nothing here is actioned by the auditing session.**

Walked the isolated **`meddoc-qa`** stack (`127.0.0.1:9020`), never production. QA posture
was asserted first with `scripts/check-qa-mock-posture.sh`: `MOCK_AI_CALLS=true` in both
live containers, every vendor key a dummy, DB `meddoc_qa_test`. The walk signs up
**fresh synthetic users** and seeds their own visits, so no existing record was read or
mutated.

**26 screens censused**, including all six `/admin/*` (as a real `SUPER_ADMIN`), a
`FAILED` visit, an open dialog, four unauthenticated screens and four mobile viewports.

---

## ⚠️ THIS REPORT SUPERSEDES ITS OWN FIRST DRAFT — 3 of 5 findings were mine, not the app's

The first pass of this audit reported **5 contrast violations**. **Three of them do not
exist.** They are recorded here rather than quietly dropped, because the correction is
more useful than the original claim.

The contrast detector resolved a text node's background by walking ancestors for the
first opaque `background-color`. **It ignored `background-image`.** The user avatars on
`/admin/users` are painted with a *light* `linear-gradient` over a transparent
background-color, so the walk went straight past the gradient to the dark page
background and compared dark text against it — producing **12 confident "1.06:1"
violations on invisible text that renders perfectly well.**

Verified against the live element before changing anything:

```
div.flex.h-full.w-full   backgroundColor: rgba(0, 0, 0, 0)
                         backgroundImage: linear-gradient(135deg, rgb(185,178,217), …)
```

**A gradient has no single background colour, so there is no honest ratio to report.**
The detector now returns *undeterminable* for those nodes and **counts them** — 112
across 26 screens — instead of inventing a number. That count is the report's own
`incomplete` bucket, and it is stated rather than hidden (canon 67: *a scanner's
`incomplete` is not a pass*).

---

## Findings

### Contrast — 2 violations, both surviving the corrected instrument

| screen | ratio | needs | size | colours | text |
|---|---|---|---|---|---|
| `visit-SIGNED` | **3.43:1** | 4.5:1 | 12.5px | `rgb(130,137,149)` on `rgb(252,252,250)` | **"View the original transcript"** |
| `visit-READY` | **3.76:1** | 4.5:1 | 10px | `rgb(124,134,148)` on `rgb(37,45,58)` | `🔒` |

⚠️ **The first row is the one to fix.** It is a **functional, labelled control on a signed
clinical note** — the document a doctor is legally attesting to — and it is the only
finding here on a real action rather than an ornament. The second is a 10px lock glyph.

### Tap targets — 3 primary navigation links are 20px tall on mobile

WCAG 2.5.5 asks for 44×44 CSS px. Measured at a 390×844 mobile viewport:

| link | size | selector | seen on |
|---|---|---|---|
| `Board` | **36x20px** | `a.qm-rounds-topbar-link` | 15 screens, 4 mobile |
| `Patients` | **48x20px** | `a.qm-rounds-topbar-link` | 15 screens, 4 mobile |
| `Settings` | **49x20px** | `a.qm-rounds-topbar-link` | 15 screens, 4 mobile |

All three are the **primary top-bar navigation**, so this is every mobile screen's main
way of moving around the app. (The `sr-only` "Skip to main content" link also measures
1×1 and is **excluded by design** — that is the standard visually-hidden pattern, and
flagging it would be a false positive on an accessibility *feature*.)

### Black frames — 0, and this zero is proven

The pass-1 detector flagged **34** and every one was a false positive: it caught the
design system's own dark surfaces (`rgb(18,22,30)`, `rgb(22,27,36)`, `rgb(30,37,48)`).
Refined to the real signature — *large, dark, and empty of any content* — and re-proved
with **three negative controls**: a themed surface with text, a light empty box, and an
empty `<textarea>`. All three must stay unflagged; the planted black box must be caught.

⚠️ **The empty-textarea arm exists because the refined detector's only hit across 26
screens was `textarea#nf-paste`** — a working input, which matches "empty" by definition.

### Dead controls — 0, and this zero is proven

Across **~330 interactive elements on 26 screens**: no anchor with a missing, empty, `#`
or `javascript:void(0)` destination, and no control lacking both an accessible name and
an icon. A planted `<a href="#">` is caught, so the zero is a fact about the app.

⚠️ **Honest limit:** it deliberately does not try to prove a button has a handler. React
attaches via delegation, so an absent inline `onclick` proves nothing.

### Old-design remnants — one question, not a finding

The detector compares rendered colours against the resolved `--color-linear-*` palette.
Only **22 of 37** token names resolve on `:root` (Tailwind v4's `@theme` prunes unused
ones) and much of the real palette lives in component classes, so its top hits are the
app's own foreground and border colours. **The detector flags the design system.** One
candidate survives that objection:

> `button.qm-rounds-btn-primary` renders **`#5B5BD6` indigo** on nearly every screen,
> while the recorded design system is *"dark #08090a, sage #7AA68C"*. Deliberate accent,
> or remnant? **An outside measurement cannot settle it, and guessing is how a false
> finding gets filed.**

### Dialogs — 1 opened, correctly labelled

Only one modal was reachable by a non-destructive trigger: **Settings → "Change"** (email
change). It carries `aria-labelledby`. ⚠️ It does **not** set `aria-modal`, which is worth
a look but is not a defect on its own.

**Why only one:** triggers are filtered by a deny list — nothing that could sign, delete,
archive, send, discard or revoke is ever clicked, even on synthetic data. Most dialogs in
this product sit behind exactly those verbs. **31 components match `Dialog|Modal|Drawer`,
so dialog coverage remains largely open**, and closing it needs a human deciding which
triggers are safe to exercise.

---

## Per-screen census

| screen | contrast | undeterminable | black-frame | dead | tap<24px | controls |
|---|---|---|---|---|---|---|
| `admin` | 0 | 1 | 0 | 0 | 0 | 13 |
| `admin-hipaa` | 0 | 1 | 0 | 0 | 0 | 12 |
| `admin-queues` | 0 | 1 | 0 | 0 | 0 | 1 |
| `admin-threats` | 0 | 1 | 0 | 0 | 0 | 10 |
| `admin-usage` | 0 | 2 | 0 | 0 | 1 | 9 |
| `admin-users` | 0 | 21 | 0 | 0 | 0 | 9 |
| `anon-forgot-password` | 0 | 2 | 0 | 0 | 1 | 3 |
| `anon-login` | 0 | 2 | 0 | 0 | 2 | 4 |
| `anon-signup` | 0 | 2 | 0 | 0 | 4 | 6 |
| `board` | 0 | 4 | 0 | 0 | 3 | 9 |
| `check-email` | 0 | 2 | 0 | 0 | 1 | 3 |
| `dlg-settings:Change` | 0 | 1 | 0 | 0 | 3 | 28 |
| `mobile-board` | 0 | 4 | 0 | 0 | 3 | 9 |
| `mobile-patients` | 0 | 4 | 0 | 0 | 3 | 7 |
| `mobile-settings` | 0 | 1 | 0 | 0 | 3 | 25 |
| `mobile-visits` | 0 | 4 | 0 | 0 | 3 | 8 |
| `patients-list` | 0 | 4 | 0 | 0 | 3 | 7 |
| `settings` | 0 | 1 | 0 | 0 | 3 | 25 |
| `settings-mfa` | 0 | 1 | 0 | 0 | 3 | 7 |
| `settings-note-format` | 0 | 4 | 0 | 0 | 3 | 25 |
| `visit-FAILED` | 0 | 4 | 0 | 0 | 3 | 8 |
| `visit-READY` | 1 | 16 | 0 | 0 | 4 | 16 |
| `visit-SIGNED` | 1 | 20 | 0 | 0 | 3 | 15 |
| `visits-list` | 0 | 4 | 0 | 0 | 3 | 8 |
| `visits-new` | 0 | 3 | 0 | 0 | 3 | 8 |
| `waitlist` | 0 | 2 | 0 | 0 | 1 | 3 |

---

## Coverage

| covered | |
|---|---|
| unauthenticated | `/login`, `/signup`, `/forgot-password` |
| pre-auth | `/check-email`, `/waitlist` |
| app | `/board`, `/visits`, `/visits/new`, `/patients`, `/settings`, `/settings/note-format`, `/settings/security/mfa` |
| **admin (as SUPER_ADMIN)** | `/admin`, `/usage`, `/users`, `/queues`, `/hipaa`, `/threats` — all **200** |
| visit states | READY, SIGNED, **FAILED** |
| mobile 390×844 | board, visits, patients, settings |

### Still NOT covered

1. **Dialog states beyond one** — see above; 31 candidate components.
2. **`/visits/[id]/record`** redirects for a READY visit; needs a recordable state.
3. **Error and empty states** — no 500, no network-failure, no empty-list rendering.
4. **Keyboard-only and focus-visible traversal** — not attempted.
5. **`/dashboard` is not a distinct screen** — it redirects to `/board`.

⚠️ Pass 1 listed `/login`, `/signup`, `/forgot-password` and `/dashboard` as
*authenticated* routes. **All four redirect to `/board` for a signed-in user**, so it
captured the same screen four times and audited zero unauthenticated screens — invisible
in the output, which showed four rows and four screenshots. They are now walked in a
genuinely anonymous context.

---

## ⚠️ The screenshots are not attached, and that is deliberate

Full-page renders of a **clinical note** were captured. AGENTS.md:

> *"A filled clinical export outside a sanctioned path is treated as PHI — regardless of
> whether the patient is real or synthetic. **The posture does not depend on knowing
> which.**"*

That class has already cost this repository **two `filter-repo` history rewrites**. Every
number in this report is derived from the DOM rather than from a picture, and the section
below records how to re-derive each one. The images were shredded with the scratch tree.

## How to re-run

The collector is **not committed** — this item forbids product-code changes, and a
throwaway harness in the tree is a maintenance liability. What matters for reproduction:

- `tests/e2e/helpers/signup.ts` → fresh user; `helpers/admin.ts` `promoteToSuperAdmin()`
  → grants `SUPER_ADMIN` **and** `mfaEnabled`, which is what makes `/admin/*` render;
  `helpers/seedVisitStates.ts` → READY/SIGNED/PROCESSING.
- one `page.evaluate` per screen computing every class from the CSSOM.
- **the positive control must import the same census string, not re-read it from disk.**

### Three instrument defects, each caught by controlling a zero

Every one would have produced a confident, wrong report:

1. **The gradient blindness above** — 12 fabricated violations.
2. **`getComputedStyle(el)[i]` does not enumerate custom properties in Chromium.** The
   token reader found 0 tokens on every route, then skipped the whole legacy-colour check
   behind an `if (size > 0)` — emitting an empty finding list that read as a clean result.
3. **A single-escaped `\(` inside a template literal collapses to `(`.** The colour regex
   then captured `"(255, 255, 255"`, `parseFloat` returned `NaN`, and **every comparison
   silently went false** — including the luminance filter, since `NaN > 0.06` is false. A
   *light* empty box would have been reported as a black frame. Only a negative control
   aimed at the opposite answer could see it, which is why one now exists.

## Suggested order

1. `visit-SIGNED` — "View the original transcript" at 3.43:1, on a signed clinical note.
2. The three 20px mobile nav links.
3. Decide the `#5B5BD6` primary-button question; one answer settles every screen.
4. Extend to dialogs (needs a human safety call on triggers), error states, keyboard.
