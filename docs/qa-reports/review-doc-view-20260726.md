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

---

# E/M REACHABILITY + HARDENING — promoted 2026-07-26

## 1. The codes row expands to the real billing panel

`BillingCardC3` and `CodesTab` render inside the row, verbatim — the same
components the tabs had, same enforcement, same audit. Collapsed by default; the
inline confirm card is still the gate. Verified in the browser:

```
expanded: true   billingCard: true   "Why this level?": true
override <select>: 1   codes tables: present
BILLING SUPPORT · AMA 2021
Supports a level 4 visit, 99214 — established patient, moderate complexity.
The documented level changed to 99214 — you'll confirm it when you sign.
Why this level? / Set a different code / 99211 …
```

Screenshot: `review-doc-shots/rdoc-07-codes-row-expanded.png`.

Acknowledging a level and changing one are different acts, and they now have
different controls: the inline card confirms, this row changes. No doctor needs
the flag toggled to disagree.

## 2. E2E pack — 10 tests, green

```
npx playwright test --project=review-doc
  10 tests in 1 file → rc=0, no failure artifacts
```

Covers: document renders / tab strip gone · placement per section · read-gate
locked → unlocked · **a card taller than the viewport still unlocks** · single
adopt (and the gate NOT re-locking) · accept-remaining · critical-Rx typed
override · E/M confirm · the expanded codes row · sign with an asserted download.

**Its own Playwright project.** The default chromium gate builds the pre-C3 skin
with the flag OFF, where this surface does not exist — left in the default sweep
the pack would have failed the required gate for an environment reason rather
than a real one. CI builds a separately-tagged flag-ON image, runs
`--project=review-doc`, then restores the fixture image for phi-reject/rx-safety.

**Four of the first failures were the TEST being wrong**, and each is recorded in
the seed because a seed that does not match production is a test of the seed:

| symptom | cause |
|---|---|
| override rendered `undefined`, server refused it | invented warning fields; L7c writes `{severity, rx_drug, message, evidence_quote}`, identity POSITIONAL |
| E/M card said "unknown → unknown" | `parseEmPendingChange` is strict and fails closed; `{from,to}` without `cause`/`at` coerces to null |
| codes toggle never appeared | nothing seeded any codes — the product correctly renders no row |
| bar never said "scroll to review" | a pending drug warning outranks it; asserting on bar text tested message priority, not the gate |

The sign test needed `dispatchEvent('click')`: the submit reports
visible/enabled/stable but the actionability wait never settles behind a browser
download. The real handler still runs — it bypasses Playwright's wait, not the
application.

## 3. Runbook — standing law

`AGENTS.md` gains **"Production verification — standing law"**: a real doctor's
visit is never a smoke target; production verification is structural (health,
image digests, migrations, flag inlined in the shipped bundle, co-tenants, DOM
presence without mutation, synthetic smoke-doctor flows only); the full clinical
walk lives on QA against a byte-identical build; never rebuild prod's `:latest`
to stage something. And: an unverified step named honestly beats a green tick
bought with a patient's record.

## 4. Promotion

```
rollback   images meddoc-pro-transcribe-md{,-worker}:pre-emrow-20260726
           git tag pre-emrow-20260726
           prod before: app 19b73a057cb6 / worker 6b5b155ff435
deployed   app 42954b04d7e8 / worker 3399454681a2 — 9/9 healthy
structural qm-rdoc-meta-panels + qm-rdoc-sugg-end present in the shipped bundle
co-tenants app 307 / pro 200 / quillmd.com 200 / admin 404
baseline   visits=18 patients=9 strays=0 — no prod data touched
```

Verification was structural only, per rule 3 — the same rule this run wrote down.

---

# DOCUMENT-FIRST 1a — the settings row. Promoted 2026-07-26.

## What shipped

Rows are now **name · status · Replace · Delete · ⋯** (advanced editor and
Duplicate behind the overflow). The "Set up native export" CTA, its setup prose,
and the separate "Native template (beta) — upload your .docx to certify" block
are gone. When we cannot fill the doctor's own page it is one line of fact —
*"Exports use a styled copy — Replace with your blank form to use your own"* —
not a job handed back.

Screenshot: `review-doc-shots/p1a-02-settings-row-after.png`.

## The finding that changed 1a's shape

The brief assumed absorption could migrate Kasra's live row automatically. **It
cannot, and no amount of code makes it possible:**

- the blank-form bytes are never retained — `certifyPdfTemplateAction` takes a
  fresh upload
- `carry-forward` can only inherit from a prior CERTIFIED template with a
  matching structure hash
- Kasra has **exactly one** template: `cms1fenrn…`, v1, active, uncertified, no
  structure hash, no predecessor. There is nothing to carry from.

So the honest fix is not a migration that pretends to absorb. It is deleting the
ritual and letting the one real action do the job: **Replace already activates,
certifies, sets form-only and previews once.** A separate step asking for the
same file under a different name was ceremony. Recorded rather than papered over.

## Promotion

```
rollback   images meddoc-pro-transcribe-md{,-worker}:pre-docfirst-p1a-20260726
           git tag pre-docfirst-p1a-20260726
           prod before: app 42954b04d7e8 / worker 3399454681a2
deployed   app 788438a6b24a / worker 3d15de5ddbf7 — 9/9 healthy
flag       NEXT_PUBLIC_SETTINGS_SIMPLE_ROW=true (+ Dockerfile ARG + compose arg)
structural template-row-replace present in the shipped bundle;
           "Set up native export" absent from every shipped chunk
co-tenants app 307 / pro 200 / quillmd.com 200 / admin 404
```

Verification structural only, per the runbook law.

---

# CONVERTER SIDECAR — live on prod 2026-07-26

## Resource + isolation, verified on the deployed container

```
image        gotenberg/gotenberg:8  (1.68 GB pulled; disk 46 G free)
networks     meddoc-pro_converter ONLY  (internal: true — Docker installs no
             gateway, so there is no route off this box)
published    3000/tcp -> null   (no host port; unreachable from outside)
memory       1024 MB cap, 1.5 cpus
persistence  /tmp is tmpfs (rw,noexec,nosuid,256m); NO volume
privileges   no-new-privileges:true;  --chromium-deny-list=.*  as a second belt
health       curl /health, 30s interval — reports "up"
egress test  curl https://example.com  ->  000 / BLOCKED;  no external DNS
conversion   the real WM_IOV form -> 87,214-byte PDF, HTTP 200
```

## HIPAA note — exactly what happens

**What crosses:** a *filled* DOCX. It carries PHI, because the point of the
preview is that the doctor sees their real document.

**Where it goes:** over the internal `converter` Docker network to a container
with no gateway and no published port. It cannot reach the internet, and the
internet cannot reach it. It is not on the default network with the rest of the
stack; only the app is dual-homed.

**Where it lives:** in RAM. `/tmp` is a tmpfs, so LibreOffice's scratch never
touches disk and dies with the container.

**What persists: nothing.** There is no volume, no cache, no log of content. The
PDF is returned in the response body and the request ends.

**What depends on it: nothing clinical.** Certify, export and sign do not call
the converter, and `__tests__/convert.test.ts` asserts no clinical path imports
it. On timeout (12 s hard ceiling, inside Gotenberg's own 25 s), error, or a
sidecar that is not deployed at all, the client returns a named reason and null
and the caller renders the true bytes in the browser. A preview that could block
a signature would be worse than no preview.

Rollback: `docker compose stop gotenberg` — nothing breaks, previews fall back.
Tag `pre-docfirst-converter-20260726`.

## Prod

10/10 healthy (9 + gotenberg). Co-tenants 307 / 200 / 200 / 404. Structural
verification only, per the runbook law.

---

# PHASE 1b — REAL-DOCUMENT PREVIEW — live on prod 2026-07-26

## What changed

The settings "sample" was markdown in a `<pre>`. It answered *did we read your
sections* — our question. It has been replaced by the document.

| surface | before | now |
|---|---|---|
| confirm card | markdown mock, our fonts | their uploaded form. Flat PDF drawn **filled** (sample answers in their own blanks); `.docx` drawn as the page it is, captioned as unfilled |
| settings row | nothing | **"See your form"** — inline, the artifact certification itself verified |

**Drawn, not embedded.** Pages render to `<canvas>` via pdf.js rather than an
`<object>`. A browser with no PDF plugin — headless Chromium, Chrome on Android
— renders `<object>` as a blank white rectangle, which a doctor reads as *my
form came back empty*. It also made the surface unverifiable in QA. Confirmed in
the browser: the worker loads (no 404, no fake-worker warning, no page error).

## Verification

| check | result |
|---|---|
| real 3-page WM form → confirm card | `data-drawn=true`, 3 canvases, letterhead + headings intact |
| DOCX branch end to end | 49,297-byte certified artifact → **54,190-byte `%PDF-`**, reason `null` |
| sidecar unreachable | reason `converter_error`, pdf `null`, doctor still confirms + activates |
| 390px | draws; horizontal overflow **0 px**; CTA `HITTABLE` (not covered by the fixed mobile nav) |
| flag OFF | **byte-identical to HEAD's own component** across loading / rendered / failed |
| unit | 2373 passed |
| E2E `doc-preview` | 4/4 — no skips |
| a11y gate | 26/26 |
| auditor | 5 BLOCK / 12 WARN / 10 NIT → all BLOCKs and every substantive WARN fixed |

## Found in review, fixed before shipping

- **`practiceId` read from the compiled version**, which has no such column.
  `tsc` accepted it; it would have thrown on the first request. It lives on the
  source artifact. *tsc does not police Prisma selects — the probe did.*
- **A throw left the flag-ON card on "Opening your form…" forever** — the null
  check ran before the failure check, so `sampleFailed` was unreachable.
- **The flag had no compose build-arg**, so it could not be turned on at all and
  the documented rollback was vacuous.
- **The button promised a preview on a key alone** while the action also needs
  the hash — the next click would have denied the page exists.
- **Error text sat grey-on-paper (~2.6:1)** and the scrollable page stack was not
  keyboard reachable — both against a required a11y gate.
- **An integrity failure** (stored artifact no longer matches the certified hash)
  was collapsed into "storage hiccup". It is security-relevant; it now has its
  own reason and the error class is logged.
- **The "nothing clinical imports it" guard was fail-open** (`|| true`) and only
  checked direct importers. Now transitive, and proven to fail: a deliberately
  introduced import in `signing-gate.ts` turned it red.
- **PHI artifacts were staged for commit** (`twin-prod-visit.docx`,
  `twin-real-visit.docx`, filled notes) by an earlier `git add -A`. Never
  committed; unstaged and `.gitignore`d.

## Prod

`app 6ea1ae02e9a3`, 10/10 healthy. Co-tenants 307 / 200 / 200 / 404.
`NEXT_PUBLIC_DOC_PREVIEW=true`; row half also requires
`NEXT_PUBLIC_SETTINGS_SIMPLE_ROW`, already ON.
Rollback: `pre-docfirst-p1b-20260726` (git tag + both image tags).
Structural verification only — no real doctor's visit was used as a smoke target.
