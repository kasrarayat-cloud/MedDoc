# Pre-sign review as the document — QA report, 2026-07-26

Flag `NEXT_PUBLIC_REVIEW_DOC_VIEW`, **default OFF**. QA only.
**Not promoted. Awaiting Kasra's approval of the screenshots below.**

Staged on the isolated QA stack (`meddoc-qa`, :9020, synthetic DB) running a
separately-tagged `meddoc-pro-transcribe-md:review-doc` image via
`docker-compose.qa.reviewdoc.yml`. Production's `:latest` was never rebuilt and
never referenced.

---

## What it is

The tabbed workspace asks the doctor to assemble the note in their head: the
prose on one tab, what the verifier set aside on another, the drug warning that
blocks signing on a third. Every blocker is one tap from invisible.

Flag ON, the screen renders the thing being signed, and puts every decision at
the place in the page where it applies.

---

## Verified in the real UI

| # | Requirement | Result |
|---|---|---|
| 1 | Document renders as the page, tab strip gone | ✅ `documentViewPresent=true`, `tabStripPresent=false`, 6 sections on the ultrasound note |
| 2 | Set-aside content inline, in place, as proposed text | ✅ 3 claims placed under **Subjective / Objective / Plan** — their own sections, not a list |
| 2 | Accept = the existing adopt action | ✅ accept → 3→2 suggestions, accepted text now reads as note body, no longer a card |
| 3 | Hard gates inline, individual, never hidden | ✅ `PRESCRIPTION SAFETY` (the real RxTab rail, per-warning override buttons) **and** `DOCUMENTATION LEVEL CHANGED` both render in the document |
| 3 | Blocker visibility | ✅ bar reads "Confirm the documentation level above"; **Sign & Download disabled** |
| 4 | "N suggestions remaining" | ✅ "3 suggestions remaining — scroll to review" |
| 4 | Bulk-accept ONLY after full scroll-through | ✅ locked before scroll; after every card is fully on screen → **"Accept remaining (3)"** |
| 4 | Bulk-accept audits as individual adoptions | ✅ by construction — a loop over the same per-claim `adoptSuggestionAction`, never a bulk endpoint |
| 5 | Codes + billing one slim row, dictation behind a link | ✅ `CODES · BILLING I83.891` / `TRANSCRIPT` rows, collapsed |
| 5 | Rx row only when a warning exists | ✅ absent on the ultrasound note, present on the Rx visit |
| 6 | No prose advisory banner | ✅ the set-aside advisory is gone; its content is the inline highlights |
| — | Mobile-first, 390px | ✅ document reads top-to-bottom; bar pinned above the mobile nav |

### Three defects found and fixed during QA

1. **The scroll-through gate never unlocked.** The `IntersectionObserver` was
   built in `useEffect`, which runs *after* ref callbacks, so no card was ever
   observed. It failed safe — which is exactly why it survived a read-through:
   *a gate that has not unlocked yet and a gate that can never unlock look
   identical on screen.* Caught by scrolling every card into view in a real
   browser and watching the button not appear. Observer is now built on first
   attach.
2. **Suggestions could vanish after an inline edit.** Placement keyed on
   `parseNoteSections`' generated id, but the slot's section comes from
   SoapBody's parse of its own editable text; the two diverge the moment the
   doctor edits. Now keyed on the section LABEL — which is what the adopt action
   joins on anyway.
3. **Flag-OFF DOM was not byte-identical.** The section slot wrapped every
   section in a `<div>` on *every* surface, including the ones that do not use
   it. With no slot, `SoapBody` now renders exactly what it always rendered.

---

## What is NOT changed — the rails

- **The gates are surfaced, not moved.** `RxTab` goes into the document
  verbatim: same `OverrideConfirmModal`, same `recordOverride`, one button per
  warning, never bulk-able. The E/M confirmation inside `SignAndSendModal` is
  untouched and **remains the enforcement** — the inline card is an additional
  visible blocker in front of it, not a replacement. `POST /sign` keeps both
  server gates (422 `OVERRIDE_REQUIRED`, 400 `EM_CHANGE_UNACKNOWLEDGED`).
- **Adoption** is `adoptSuggestionAction` per claim, with its content-identity
  check. Bulk-accept is a loop over it.
- **Sign + export** is the existing `SignAndSendModal` → existing sign route →
  existing download (native vs styled is chosen server-side, as today).
- **The note** is still rendered by `SoapEditor`: markdown fidelity (the
  ultrasound measurement tables render intact), inline editing, status pills,
  copy affordances. `SoapBody` gained one optional `afterSection` slot that
  nothing else passes.
- Verifier, audit logging, auth: untouched.

### Edited-then-accept
Unchanged from today. There is no pre-adoption edit affordance in the current
product either — the path is adopt verbatim, then edit the appended text inline
(`SoapInlineEdit` → `saveSoapDraftAction`). That still works here.

---

## Screenshots for approval

| File | What it shows |
|---|---|
| `rdoc-01-ultrasound-desktop.png` | KOKAB-class ultrasound visit as one document — both leg measurement tables intact, no tab strip, slim CODES·BILLING and TRANSCRIPT rows, bar reads "Reviewed · Sign & Download" |
| `rdoc-02-suggestions-inline-desktop.png` | SOAP control — three suggestions sitting **in place** under Subjective, Objective and Plan, sage-lit, "suggested — couldn't verify", Accept / Dismiss |
| `rdoc-03-bulk-unlocked-desktop.png` | after full scroll-through: **"Accept remaining (3)"** appears beside Sign & Download |
| `rdoc-04-gates-inline-desktop.png` | both hard gates inline — PRESCRIPTION SAFETY with the per-warning rail, DOCUMENTATION LEVEL CHANGED with "Confirm 99214"; bar says "Confirm the documentation level above", Sign disabled |
| `rdoc-05-suggestions-390.png` | 390px — document reads top-to-bottom, bar pinned above the mobile nav |

### Known cosmetic issue (pre-existing, not introduced here)
At 390px the section `REVIEWED` pill and the `GAP TO NEXT TIER` hint overlap.
That is existing `SoapSection` chrome, visible on the current tabbed surface
too. Flagging it rather than quietly fixing it inside a skin-only change.

---

## Not yet done

- **Sign → file downloads**, end to end on this surface. The path is the
  existing `SignAndSendModal` submit and unchanged, but I did not sign a QA visit
  to watch the file land. It should be walked before promotion.
- **All 4 gates re-verified / auditor 0 BLOCK.** Not run in this pass.
- **Flag-OFF byte-identical** is argued from construction (build-time constant,
  the OFF branch is the untouched `ReviewTabsV2` path, and the one shared-file
  change is now inert without the slot) and from 313 unit tests passing — but I
  did not stand up a flag-OFF image side by side to diff it.

## Promotion

**Blocked on Kasra's approval of the screenshots.** Nothing has been promoted;
prod runs the same images and the same flags it ran before this work.
