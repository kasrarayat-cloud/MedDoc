# T10 — every-screen UI audit, first pass

**Run 2026-09-04 by the Data/Audit session. READ-ONLY: no code was changed by this item.**
**Filed for the UI/design session. Nothing here is actioned by the auditing session.**

Walked the isolated **`meddoc-qa`** stack (`127.0.0.1:9020`), never production. QA posture
was asserted before the walk with `scripts/check-qa-mock-posture.sh`:
`MOCK_AI_CALLS=true` in both live containers, every vendor key a dummy, DB
`meddoc_qa_test`. The walk signs up a **fresh synthetic user** and seeds its own
visits, so no existing record — synthetic or otherwise — was read or mutated.

---

## ⚠️ READ THIS BEFORE THE FINDINGS: three of the five classes are UNMEASURED

The item named five defect classes. Two produced trustworthy results, three did not,
and saying which is which is the point of this section. **A class reported as "0
findings" by a detector nobody has seen fire is not a clean bill of health.**

| class | status | why |
|---|---|---|
| **contrast** | ✅ **MEASURED** — 5 findings | detector positive-controlled: 3 planted offenders at 4.48 / 1.92 / 1.00:1 all caught, with correct ratios |
| **dead controls** | ✅ **MEASURED** — 0 findings, a *controlled* zero | a planted `<a href="#">` was caught, so the zero is a fact about the app |
| **black-frame** | ❌ **UNMEASURED** | see below — the detector cannot tell a dark theme from an artifact |
| **old-design remnants** | ⚠️ **CANDIDATES ONLY** | the detector flags the design system itself; needs adjudication |
| **lying labels** | ⚠️ **COLLECTED, NOT ADJUDICATED** | 218 label/behaviour pairs captured; judging them is not something the collector can do |

### Why "black-frame" is unmeasured rather than clean

The detector flagged any large box with a near-black fill (`luminance < 0.02`). It
returned **34 hits across 23 routes — and all 34 are the design system's own dark
surfaces**: `rgb(18,22,30)`, `rgb(22,27,36)`, `rgb(30,37,48)` and the `--color-linear-bg`
token `#08090a` itself. In a dark-themed app that threshold cannot discriminate.

**Reporting those 34 as defects would have been a false alarm; reporting "0 real
black frames" would have been a false clean.** The class is real — this repo carries a
live branch named `fix/t3-signed-note-black-frame` — so the correct next step is to take
the signature from that branch's actual defect (most likely *a surface-coloured box where
CONTENT is expected*, i.e. large + zero text + zero children) and re-run. The collector
already records `textLen` per hit, so that refinement is small.

### Why "old-design remnants" is candidates only

The detector compares every rendered colour against the resolved `--color-linear-*`
palette. **Only 22 of 37 declared token names resolve on `:root`** — Tailwind v4's
`@theme` prunes unused tokens — and much of the real palette is defined in component
classes (`.qm-c3-*`, `.qm-rounds-*`) rather than as tokens at all. So the top "legacy"
hits are the app's own foreground (`231,235,241`), muted text (`124,134,148`) and border
(`44,52,66`) colours. **The detector is flagging the design system.**

**One candidate does survive that objection and is worth a human look:**

> `button.qm-rounds-btn-primary` renders `background: rgb(91,91,214)` — indigo `#5B5BD6` —
> on **22 of 23 routes**. The recorded design system is *"dark #08090a, sage #7AA68C"*.
> A primary button that is not the accent colour is either a deliberate Linear-style
> accent or exactly the remnant class this item is hunting. **I cannot tell from the
> outside, and guessing is how a false finding gets filed.**

---

## The findings that ARE measured

### Contrast — 5 violations of WCAG AA, all on small text

Ratios computed in-page against the first opaque ancestor background — which is the
step axe declines to take, and why its `incomplete` bucket hides the worst offenders
(canon 67, *"A SCANNER'S `incomplete` IS NOT A PASS"*).

| screen | ratio | needs | size | colours | selector | text |
|---|---|---|---|---|---|---|
| `settings-mfa` | **4.18:1** | 4.5:1 | 10.5px | `rgb(124, 134, 148)` on `rgb(30,37,48)` | `span` | "2" |
| `settings-mfa` | **4.18:1** | 4.5:1 | 10.5px | `rgb(124, 134, 148)` on `rgb(30,37,48)` | `span` | "3" |
| `visit-READY` | **3.76:1** | 4.5:1 | 10px | `rgb(124, 134, 148)` on `rgb(37,45,58)` | `span.qm-rounds-strip-dot` | "🔒" |
| `visit-SIGNED` | **3.43:1** | 4.5:1 | 12.5px | `rgb(130, 137, 149)` on `rgb(252,252,250)` | `span` | "View the original transcript" |
| `visit-record` | **3.76:1** | 4.5:1 | 10px | `rgb(124, 134, 148)` on `rgb(37,45,58)` | `span.qm-rounds-strip-dot` | "🔒" |

**⚠️ The `visit-SIGNED` row is the one to fix first.** *"View the original transcript"*
at **3.43:1** is a functional control on a **signed clinical note** — the document a
doctor is legally attesting to — and it is the only finding here on a real, labelled,
user-facing action rather than an ornament or a step number. The other four are a lock
glyph and two step numerals at 10–10.5px.

### Dead controls — 0, and this zero is controlled

Across **218 interactive elements on 21 distinct screens**: no anchor with a missing,
empty, `#` or `javascript:void(0)` destination, and no control lacking both an
accessible name and an icon. The detector caught a planted `<a href="#">`, so it works.

⚠️ **Honest limit:** it deliberately does NOT try to prove a button has a click handler.
React attaches via delegation, so an absent inline `onclick` proves nothing, and a
detector that flagged it would produce noise on every screen. **A control that is wired
but wired to the wrong thing is the "lying labels" class, and that is not settled here.**

---

## Coverage — what was walked, and what was NOT

**21 distinct screens captured**, 23 screenshots at 1440×900 (full-page).

| walked | |
|---|---|
| unauthenticated | `/login`, `/signup`, `/forgot-password`, `/` (→ login) |
| pre-auth flow | `/check-email`, `/waitlist` |
| app | `/board`, `/visits`, `/visits/new`, `/patients`, `/settings`, `/settings/note-format`, `/settings/security/mfa` |
| visit states | READY, SIGNED, PROCESSING (seeded synthetic) |

### ⚠️ NOT covered — named so nobody reads this as a full sweep

1. **All six `/admin/*` screens returned 404 and were never rendered.** The audit user is
   a `DOCTOR`; admin is gated on `SUPER_ADMIN` + `mfaEnabled` + 12h session freshness.
   What is in the census for those rows is the **404 page, six times**.
2. **`/visits/[id]/record` was never seen.** It redirects to the visit page for a READY
   visit. Reaching it needs a visit in a recordable state.
3. **`/dashboard` is not a distinct screen** — it redirects to `/board` under this skin.
   ⚠️ An earlier run of this collector listed `/login`, `/signup`, `/forgot-password` and
   `/dashboard` as authenticated routes; **all four redirected to `/board`, so it captured
   the same screen four times and audited zero unauthenticated screens.** Corrected by
   walking them in a genuinely anonymous browser context. Recorded because the failure
   was invisible in the output — four rows, four screenshots, one screen.
4. **Mobile viewports were not walked.** Desktop 1440×900 only.
5. **No modal, drawer, dialog or error state was opened.** 31 components in the tree match
   `Dialog|Modal|Drawer|Sheet`; a walk that only visits routes sees none of them.
6. **No `FAILED`-state visit was rendered**, though QA holds 18 of them.

---

## ⚠️ THE SCREENSHOTS ARE NOT ATTACHED, AND THAT IS DELIBERATE

The item asked for a *screenshot inventory*. **23 full-page screenshots were captured
(2.7 MB) and they are NOT in this commit.** Three of them — `visit-SIGNED.png`,
`visit-READY.png`, `visit-record.png` — are full-page renders of a **clinical note**.

AGENTS.md is unambiguous and does not leave this to judgement:

> *"A filled clinical export outside a sanctioned path is treated as PHI — regardless of
> whether the patient is real or synthetic. **The posture does not depend on knowing
> which**, because by the time you are asking, the file already exists somewhere it
> should not."*

A committed render of a signed note is the same class as a committed filled `.docx`,
and that class has already cost this repository **two full `filter-repo` history
rewrites** — the second one ~200× the first, purely because it sat longer. The visits
here were seeded synthetic and the account was a fresh signup, so the *content* is
almost certainly harmless. **"Almost certainly harmless" is not the standard the rule
sets**, and a screenshot is not made safe by the auditor's confidence about what is in it.

**What is preserved instead:** every number in this report is derived from the DOM, not
from a picture, and the section above records exactly how to re-derive each one. The
findings do not depend on the images. The images were reaped with the scratch worktree.

If the design session wants the visuals, the right move is to re-run the collector
locally against QA and look at them **without committing them** — the walk takes 50
seconds.

## How to re-run

The collector is **not committed** — this item forbids code changes, and a throwaway
harness in the tree is a maintenance liability. It lived in a scratch worktree and was
reaped. What matters for reproduction is recorded here:

- signs up via `tests/e2e/helpers/signup.ts`, seeds via `helpers/seedVisitStates.ts`
- one `page.evaluate` per route computing all five classes from the CSSOM
- **the positive control must import the same census string, not re-read it off disk.**
  An earlier control extracted it as raw file text; the template literal's escapes were
  left unprocessed, the `rgb()` regex could not match, and **every detector reported
  zero**. That verdict was a fact about the control, and it very nearly got recorded as
  "the detectors are broken". *A refusal caused by your own substitution is evidence
  about your substitution.*

## Suggested order for whoever picks this up

1. `visit-SIGNED` contrast on *"View the original transcript"* — 3.43:1, signed-note surface.
2. Decide the `#5B5BD6` primary-button question; it is one answer that settles 22 screens.
3. Re-point the black-frame detector using the real signature from `fix/t3-signed-note-black-frame`.
4. Extend coverage to admin (needs a `SUPER_ADMIN` fixture), modals, mobile, and `FAILED` visits.
