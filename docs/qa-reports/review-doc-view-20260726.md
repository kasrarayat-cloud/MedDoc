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

---

# CLOSE-OUT — promoted 2026-07-26

## 0. Teardown — the premise was wrong; nothing had been exposed

There was no port publish or nginx rule to revert. Verified:

```
docker-compose.qa.yml:157   "127.0.0.1:9020:3011"   (unchanged; last touched by an
                                                     unrelated 2026-06 commit)
host listener               LISTEN 127.0.0.1:9020
nginx rules mentioning 9020 none
curl http://5.231.107.93:9020/   -> 000
ufw                         inactive;  iptables rules for 9020: 0
```

**Why it was unreachable: not the firewall — the loopback bind.** ufw is off and
there is no packet filter on 9020; the app simply never listened on a public
interface. The QA stack has been localhost-only by design since it was built (its
own header says "reach it via an SSH tunnel"), and every drive in this work was
from inside the box. QA remains localhost-only.

## 1. Sign → download, walked

Signed `qa_shot_ultrasound` on the new surface; both files landed
(`visit-eleanor-whitfield-2026-07-26.pdf` / `.docx`). Grep of the downloaded DOCX:

```
SIGNED DOCX — dictated values: 10/10 | missing: none
has IMPRESSION: True     has signature: True
```

## 2. Gates re-verified on the new surface

| Gate | Evidence |
|---|---|
| Critical-Rx typed override | inline rail → "Override…" → 108-char reason → **Confirm override** → `RX_OVERRIDE_RECORDED` audited → "Overridden" chip → bar "Reviewed" → Sign enabled |
| E/M confirm | bar "Confirm the documentation level above", Sign **disabled** → Confirm 99214 → card `is-done`, bar "Reviewed", Sign enabled |
| Review-lane adoption | accept → DB claims 2→1, `SUGGESTION_ADOPTED` audited **individually** |
| Audit rows | `RX_OVERRIDE_RECORDED`, `SUGGESTION_ADOPTED` ×2, `EXPORT_PDF_DOWNLOADED`, `EXPORT_DOCX_DOWNLOADED`, `VIEWED_VISIT` |

**code-quality-auditor: 1 BLOCK → fixed → re-audited 0 BLOCK.** The BLOCK was
real: `emConfirmed` never reset, so the card could assert "Level confirmed" for a
level the doctor never saw. Five WARNs fixed alongside it, two of which would
have degraded the feature for real doctors:

- the scroll gate could not unlock for a card taller than the viewport
  (intersectionRatio only reports on threshold-bucket changes, so a card 5%
  taller tops out at 0.75 and never satisfies any test). Replaced with a
  zero-height sentinel at the card's bottom edge — height-independent.
  **Verified against a forced 1.05×-viewport card: locked → unlocked.**
- `### Right` / `### Left` claims orphaned client-side while the server appended
  them into Findings — the doctor reviewing in one place and signing in another,
  on the ultrasound template that is live in production.

## 3. Flag-OFF byte-identity — diffed

Same visit (`qa_shot_ready_02`), two images from the same commit:

| | flag-OFF | flag-ON |
|---|---|---|
| tab strip | present, 6 tabs | absent |
| document view | absent | present |
| `qm-rdoc` nodes | **0** | 12 |
| section-slot wrappers | **0** | 4 |
| note subtree | 7697 chars | 7873 (+176 — exactly the 4 wrappers) |

Flag-OFF carries none of the new markup.

## 4. Rider — 390px overlap

Measured, not eyeballed: 2/2 section headers wrap, `anyOverlapping: false`.

## 5. Promotion

```
rollback   images meddoc-pro-transcribe-md{,-worker}:pre-reviewdoc-20260726
           git tag pre-reviewdoc-20260726
           prod before: app b6be7e434ffc / worker 43bf217e8e7a
flag       NEXT_PUBLIC_REVIEW_DOC_VIEW=true in .env (+ compose build arg)
deployed   app 19b73a057cb6 / worker 6b5b155ff435 — 9/9 healthy
bundle     the surface is inlined in the prod client chunk
co-tenants app 307 / pro 200 / quillmd.com 200 / admin 404 (incl. LeatherERP)
baseline   twin_compiled=0, synthetic strays=0
```

**Prod flow smoke was NOT walked end-to-end on production, and that is
deliberate.** Prod now carries live clinical work — `kasra.rayat@gmail.com`
created and signed a "kokab" ultrasound visit today — and the only unsigned
visits there belong to real doctors. Signing or adopting into someone's actual
note to produce a screenshot is not a smoke test. The full behavioural walk
(suggestions inline → gates inline → scroll-unlock → sign → file downloads) was
run on QA against the byte-identical build, and prod was verified structurally:
new images, flag inlined in the shipped bundle, 9/9 healthy, co-tenants green.

## Screenshots (QA, for the record)

`docs/qa-reports/review-doc-shots/` — 6 PNGs:
`rdoc-01-ultrasound-desktop`, `rdoc-02-suggestions-inline-desktop`,
`rdoc-03-bulk-unlocked-desktop`, `rdoc-04-gates-inline-desktop`,
`rdoc-05-suggestions-390`, `rdoc-06-rider-390-no-overlap`.

## Still open

- E/M **override / rescore is unreachable** on the new surface (codes row is
  read-only per the spec). A doctor who disagrees with the level cannot change it
  without the flag off. Flagged before promotion; unresolved by design.
- No E2E coverage for the surface; the normaliser parity invariant is now a unit
  test, the rest is not covered.
- Three copies of the section normaliser remain (client lib, server action,
  worker verifier) — now pinned by a test rather than a comment.
