> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **5 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## Template Twin — the parked steady state

**Read this before concluding anything about Template Twin.** An audit in July
2026 raised 173 facts about it and **17 of 24 load-bearing claims were corrected
under challenge** — a 71% correction rate. That was the cost of illegibility, not
of anyone's carelessness. This paragraph is the cure: it is the deliberate steady
state, and none of it is a bug.

**PARKED 2026-07-28.** Verdict: absorb into the shipped `note_templates` pipeline.
The RETIRE column was executed (PR #442). The INTEGRATE column is **post-pilot
roadmap**. **Trigger to un-park early: a pilot doctor explicitly needs their native
form bytes back.** Nothing else.

What is true, and intended:

- **`NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX` stays ON in production.** It is not a
  half-shipped feature left switched on by accident. It gates the OOXML ingest +
  fail-closed security fork that runs on **every** `.docx` template upload
  (`note-template-parse/docx-to-text.ts:39` dynamically imports the twin ingest),
  and the shipped `pdf-native` feature imports twin storage. That code is
  **absorbed in place and load-bearing** — deleting it breaks working paths.
- ⚠️ **THE PER-VISIT FILL STEP NO LONGER SHORT-CIRCUITS ON EVERY VISIT, AND
  THIS BULLET ASSERTED THAT IT DID.** *Previous wording:* **"The per-visit fill
  step short-circuits `not_certified_twin` on every visit, by design. `worker.ts`
  calls it; it declines because no CERTIFIED compiled version exists in
  production."**

  The premise — *no CERTIFIED compiled version exists in production* — became
  false on `2026-08-17`. Measured on the three production visits bound to that
  template, in creation order:

      cmsxitmvq…  no manifest      <- PREDATES the certification
      cmt2744qm…  VERIFIED
      cmt32zvca…  VERIFIED

  So the short-circuit is **no longer universal**: it still fires for every
  visit on every OTHER template, and it demonstrably stopped firing for the
  certified one. The sentence was right about most visits and wrong about its
  own reason, and **a bullet that is right about the count and wrong about the
  mechanism will be cited for the mechanism.**

  ⚠️ **HONEST LIMIT: what was measured is that the MANIFESTS EXIST and read
  `VERIFIED`, not which code path wrote them.** Attributing them to `worker.ts`'s
  per-visit step specifically would be inference — the twin has also been driven
  by hand on QA, and this programme has already paid for naming a mechanism it
  only read rather than ran. See the certification entry below.
- ⚠️ **THE FOLD IS SELECTIVE SINCE 2026-08-16T21:29Z, AND THERE IS A DOOR IN.**
  **This bullet used to say the opposite, in the present tense, and it was
  correct until the minute F5-b deployed.** It read: *"`NEXT_PUBLIC_SETTINGS_
  SIMPLE_ROW=true` renders `NativeTemplateManager` as null. There is therefore
  **no door in**, which is why prod has zero certifications while the flag is
  on."*

  What is true now, verified in the shipped bundle rather than asserted:
  `settings/page.tsx:255-260` mounts `NativeTemplateManager` gated **only** on
  `templateNativeDocxEnabled()` (`true` in production), and folds **only the
  UPLOAD half** via `showUpload={!isSettingsSimpleRow()}` (`false` in
  production). So the **CONFIRM** surface is reachable and the **UPLOAD** ritual
  is still retired. `NEXT_PUBLIC_SETTINGS_SIMPLE_ROW` is unchanged — still
  `true`; the fold moved into the code, not the flag.

  ⚠️ **PROD HAS A CERTIFIED TWIN. A PHYSICIAN HAS WALKED THROUGH THE DOOR.**
  **Measured 2026-08-23**, and this bullet said the opposite until that
  measurement:

  | table | reading |
  |---|---|
  | `template_twin_compiled_versions` | **1**, `certificationStatus = CERTIFIED`, 80 fields, compiled `2026-08-17T17:39:17Z` |
  | `template_twin_fill_manifests` | **2**, both `VERIFIED`, `roundTripVerified = true` (`2026-08-21T00:18:46Z`, `2026-08-21T15:07:53Z`) |
  | production visits bound to that template | **3**, all three carrying tables |

  *Previous wording, kept because the correction is the point:* **"PROD STILL
  HAS ZERO CERTIFICATIONS, AND THE REASON IS NOW A DIFFERENT ONE. The old reason
  was *no door*. The new reason is that no physician has walked through it yet —
  which is the correct steady state, not a defect."**

  ⚠️ **AND THE FILE ALREADY CONTRADICTED ITSELF, WHICH IS THE FINDING RATHER
  THAN THE TYPO.** The rollback-constraints entry accepted 2026-08-21 describes,
  in as many words, *"the owner's first certified-twin visit — the very record
  whose Word download he confirmed carried his letterhead"*, and dates its
  manifest to `00:18:46Z`. That is **the same manifest** in the table above. So
  one part of canon recorded the certification while another went on asserting
  zero, in the present tense, for two days.

  **Two statements that can disagree is the exact failure the ledger design
  exists to prevent** — and it happened inside the file that names it.

  **This is the `DEPLOYMENT_RUNBOOK.md §5.6` shape** — a document asserting an
  intended state in the present tense, read by everyone as a description of the
  running system. §5.6 was false for two months and cost six hours. This bullet
  was corrected **in the same change that deployed the behaviour**, which is the
  only timing that works.
- **`MAPPINGS_NOT_READY` is a deliberate refusal and stays strict.** Certification
  refuses until every field has a physician-confirmed mapping. **Never weaken the
  gate to shrink the wall** — a certified twin that nobody confirmed is worse
  than no twin. The work, if the park is lifted, is the imaging concept registry
  and the confirmation flow.

  ⚠️ **THE WALL IS NOT "79 OF 80". THAT FIGURE WAS INHERITED, NEVER MEASURED,
  AND IT CONFLATES TWO DIFFERENT QUANTITIES.** It originates in
  `docs/qa-reports/template-twin-integration-verdict-20260728.md:10` and was
  copied verbatim into **six** places — this file, `RELAY.md` ×2,
  `template-twin-mappings.ts:109`, and two test headers — without anyone
  re-running it. Measured 2026-08-16 against the real customer form by running
  F5-a's own gate (8 of 8 green, and it carries a non-vacuity control asserting
  the form compiles to 80 fields before any count is read):

  | the question | the answer |
  |---|---|
  | fields lacking a **physician-confirmed** mapping | **80 of 80** — every fallback mapping is `needs_confirmation`, asserted by a dedicated arm |
  | fields needing a physician to **supply a concept** | **75 of 80** before F5-a · **22 of 80** after |

  The partition is **5 manual / 53 proposed / 22 unproposed**, reconciled to 80.
  **Neither quantity has ever been 79**, in any era — so the old figure was not
  merely stale, it was wrong when written. This is AGENTS.md's own *"a count
  carried forward from another session's report is a fabricated number"* rule,
  caught in this file.
- **The twin HAS worked end to end**, on QA, by hand: upload → compile (80 fields,
  1 table) → fill manifest (`VERIFIED`, `roundTripVerified=true`) → native DOCX
  export (`nativeTemplate=true`). Two earlier "never proven" conclusions were
  wrong: `template_twin_fill_manifests` read empty because its `visitId` FK
  cascades on fixture re-seed, and the "0 native exports ever" figure was
  prod-scoped while QA held ten.

Full evidence: `docs/qa-reports/template-twin-integration-verdict-20260728.md`
and `…-absorb-plan-20260728.md`.

