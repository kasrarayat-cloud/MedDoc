# QuillMD V1 — staged Sonnet 5 qualification milestone, consolidated report (2026-09-29)

**This is not a V1-readiness claim.** Nothing here moves the installed system, closes a gate in `V1-BLOCKERS.md`, or
touches real patient data. The shared VPS remains synthetic-only.

## 1. Identities

| what | value |
|---|---|
| installed release | `dedac162` on `main`, Sonnet 4.6, synthetic-only; not deployed to, not restarted |
| candidate | `v1/release-integration` (draft PR #1291), code `1c4c4233` = `8e3dcfd0` + residual repairs + campaign tooling; docs-only descendants `526ff1e9`, `2e105767` and this report's commit. CI on `1c4c4233`: run 36529458982 (six jobs) and secrets-scan 36529458984, green |
| model | `claude-sonnet-5`, thinking disabled, effort medium, geography unset (every send metered `global`); no fallback to 4.6 occurred |
| pricing | `configured-v1:8975b158…` (model check, mapping, notes default) and `configured-v1:eb280d15…` (notes with field relations): $2 / $10 / $0.20 per million input / output / cached tokens |
| authority | owner answer "Approve the staged $40 maximum", `quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk`; structured record `QuillMD-V1-Sonnet5-Budget-Approval-20260928.json`; declaration `docs/foundation/mutations/20260928-quillmd-v1-sonnet5-staged-campaign.md` (committed `01ff8c7d` before any send) |
| credential | declared file only, mode 0600, owner-only, one line, never displayed; scrubbed environment |

## 2. Money

| stage | limit | sends | exposure | remaining | decision |
|---|---|---|---|---|---|
| model check | $5.00 | 1 | $0.00286 | $4.99714 | **passed** |
| mapping | $25.00 | 1 | $0.00984 | $24.99016 | failed-1; **not reopened** |
| ordinary notes | $10.00 | 15 | $0.066604 | $9.933396 | failed-1 (relations contract) |
| **total** | **$40.00** | **17** | **$0.079304** | **$39.920696** | no open or unknown attempt |

Figures are configured rates over provider-reported usage; unknown outcomes would have been counted at maximum × 1.1
and none occurred. Unused stage budget does not transfer. **The provider console's own charge has not been read**;
reconciling it is an owner step. The separate live Stripe payment was not approved and was not attempted.

## 3. What each stage showed (QA worker, synthetic inputs, real Sonnet 5)

- **Model check** (`sonnet5-campaign/model-check-20260929.md`): the candidate's real worker served `claude-sonnet-5`,
  `end_turn`, 840/118 tokens; request `req_011CfWpbvUpWa7eEj1zrJ4Kt`. Raw output, validator decision and review are
  kept separately; the three adopted answers are exact; reservation settled; billing audit clean; the authenticated
  export's answer cells equal the reviewed answers.
- **Mapping** (`live-stages-20260929.md`, `mapping-repair-stop-20260929.md`): the one send returned a well-formed
  envelope that misused positional references; the validator failed closed. The app then discarded the whole proposal,
  against its own design. Two repair rounds (`d40c8689`, `48aa5e8d`, branch `fix/v1-mapping-partial`, pushed) each drew
  verified HIGH refutation findings. At `48aa5e8d`, model text still reaches (R1) a signing/consent box that holds
  printed guidance or a drawing and (R2) a cell under a `Signature` column. Per the bounded-repair rule the stage stops.
  **Model-assisted mapping is unqualified and stays off.** The deterministic mapping is unaffected.
- **Ordinary notes, default path** (14 sends, 76 fields): the model's selection matched a frozen acceptable answer on
  64, a forbidden one on 7 and neither on 5. The app supported and was correct on 7, held correctly on 40 (all 7
  model errors among them), and **over-held 29 acceptable selections**. There were **0 unsafe adoptions**. N13/N16:
  the model flagged both contradictions and the app held all 4 fields. Exports: 14/14 completed and read back. The
  offline replay predicted all 76 outcomes. Usefulness is limited by the default-path hold rules, not by the model.
- **Ordinary notes, field relations** (the paused contradiction veto): the first send (N02) failed the contract. The
  model returned one context entry per selected unit rather than per source unit, and the Sonnet 5 schema transform
  does not enforce array lengths. It fails closed. **The veto was not evaluated**; six sends were not made.

## 4. Evidence, kept apart

| class | what it covers here |
|---|---|
| **QA worker, live model** | the 17 sends above, through `scripts/run-ruled-mutation.sh` into the isolated QA process (`v1-sonnet5-qa-pg`, 127.0.0.1:55731) |
| **mocked / offline** | frozen diagnostics self-test 22/22, walk 21/21, offline replay; residual repairs' suites; earlier D30/D31 authenticated workflows |
| **native Microsoft Word** | **none**. LibreOffice renders are not native acceptance (B-W3, owner) |
| **installed** | nothing new. `dedac162` was not deployed to. See the incident in §7 |

## 5. Developer defects

**Fixed this milestone** (candidate, refuted, CI green on `1c4c4233`):
- the invitation race (R-A): now answers "sign in" and creates one account;
- the settlement `DatabaseError` residual (R-B): evidenced safe, with a LOW admin-accounting repair;
- an in-doubt settlement now asserts nothing;
- account emails: ASCII only, not quoted, at most 150 characters;
- the mapping handler runs under the job lock;
- the stage runners' own refutation defects (R1, S1, RR-MONEY-1, EXPORT-CHECK-DOES-NOT-READ, RAW-RESPONSE-LOST, F1, F2).

**Open, developer-owned:**
- the mapping signing-area rule (R1/R2 HIGH, R3–R5, U1/U2 LOW);
- the design defect that one invalid change discards the whole mapping proposal (repaired only on the unintegrated
  branch);
- default-path over-holds (29/76, in the documented REMAINING-51 groups);
- the unit-keyed relations contract;
- the f5 declaration checkbox offered as answerable (N8 decision);
- D10 (unqualified) and D31's two recorded failures — **not advanced in this milestone**;
- the D03 Other write-in over-hold;
- general retention/deletion workflow — **not advanced in this milestone** (the disabled empty-draft adapter is
  unchanged; default off).

**Word breadth: the gate is unmet**, and no rate is claimed beyond the recorded ones. The historical proxy is
dev 3/40 and holdout 0/20. The candidate v2.1 development-set run is 9/22/9 documents (pass/fail/no ticked
questions) against the control's 11/20/9. No holdout was opened.

## 6. External inputs still required (unchanged; `V1-EXTERNAL-REQUEST.md`)

- **Agreements:** BAA-covered hosting (the VPS disclaims HIPAA use); the AWS BAA; the Anthropic BAA and a separate
  HIPAA organization; the Deepgram BAA; backup storage under a BAA; an email vendor decision.
- **Payments:** live Stripe account, key, webhook and bounded payment test.
- **Word and security:** native Word acceptance by the owner; an independent penetration test.
- **Counsel:** retention schedule and procedures.
- **Corpus:** independently authored corpus for the Word gate.
- **Operations:** two-custodian key custody and an outside heartbeat.

## 7. Incidents (reported when they happened)

- **Shared deploy tree moved.** 2026-09-29 05:37:31–05:37:58Z, a compound `git -C /opt/meddoc-pro checkout` of mine
  detached the shared tree for 27 s. It was restored to `main`; content equals `dedac162`, no bytecode was compiled,
  health 200/200, services not restarted. A lazy import in the window cannot be ruled out absolutely.
- **Scratch shredded.** A diagnostics repair agent shredded 30 files in the shared session scratchpad. Live evidence
  was verified intact; one mutation-proof log was lost. Agents now get their own scratch subdirectory.

## 8. Decisions for the owner

1. **Account emails ASCII-only** (accepted-capability loss): an internationalised domain must be typed in `xn--` form.
2. **Restart the installed services** to remove the residual doubt from the 27-second tree move — optional.
3. **Field-relations repair**: one bounded round (a unit-keyed contract the output schema enforces, a refutation
   pass) and the six veto sends, within the notes stage's $9.93. Not started, by recorded decision.
4. **Model-assisted mapping for V1**: ship with clinician-confirmed mapping review only, or fund another repair round
   of the signing-area rule. The mapping stage's $24.99 stays unspent either way unless reopened.
5. **N8 consent**: the lead reading (first-person declarations protected; "Consent obtained" an ordinary reviewed
   field) stands unless overruled.
6. **42 `ubuntu`-owned render files** in the session scratchpad (filled synthetic development-form PDFs from
   2026-09-27) cannot be shredded by this account and were not unlinked; they need an owner-sanctioned route.
7. **Disk**: 93% used, 22 GB free. Most of it is another tenant's 36 GB PostgreSQL volume, which was left alone.
8. **Provider console charge**: read and recorded against the $0.079304 configured-rate exposure.
