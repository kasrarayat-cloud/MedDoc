# R5 — §2.5 POST-DEPLOY VERIFICATION

**Judged against `docs/deploy-declarations/r5-delete-rx-surface-20260814.md`,
which was committed BEFORE the act.**

## ⚠️ PROCESS FINDING, RECORDED FIRST BECAUSE IT IS THE UNUSUAL PART

**R5 shipped inside ANOTHER SESSION'S DEPLOY, and nobody judged it against this
declaration at the moment of the act.**

R5 merged as `636e69a3`. The GI session then deployed `2b527509` at `11:31:25Z`
and judged it **16 of 16** — against *their* declaration, which covered an
ICD-10 allowlist change. `636e69a3` is an ancestor of `2b527509`, so **R5 went
to production inside that deploy**, correctly and unremarkably: they deployed
`main`, which is what `main` is for.

Nothing was done wrong. But the §2.5 product — *a comparison with one correct
answer, fixed before the evidence existed* — was **not** obtained for R5 at the
moment R5 shipped. Their declaration could not have detected an R5 regression;
it was not looking for one.

> **A DECLARATION IS BOUND TO A CHANGE, NOT TO A DEPLOY. When two changes reach
> `main` before either ships, the deploy discharges only the declaration whose
> author ran the comparison — and the other one is silently left unjudged
> unless somebody notices.**

**The half that held:** the declaration was committed before the act, so its
commit timestamp provably precedes the rows, and the comparison below has one
correct answer it could not have been tuned to. **The half that did not:** the
comparison ran *after* the deploy rather than as its gate. Recorded rather than
smoothed over, because a reader finding two declarations and one 16-of-16 would
otherwise assume both were judged.

## THE COMPARISON — every declared quantity, measured on the live stack

### MUST NOT CHANGE — clinical counts

| declared | measured | |
|---|---|---|
| visits 40 | **40** | ✔ |
| signed 25 | **25** | ✔ |
| patients 29 | **29** | ✔ |
| templates 9 | **9** | ✔ |
| `rx_warning_overrides` 0 | **0** | ✔ |
| audit_logs ≥ 11360 (monotonic) | **11360** | ✔ |
| migrations 102 (no migration) | **102** | ✔ |

### MUST NOT CHANGE — extraction survives (the ruling's other half)

| declared | measured | |
|---|---|---|
| visits with drafted prescriptions | **17** | ✔ |
| prescription rows | **53** | ✔ |
| visits with warnings | **27** | ✔ |

### MUST NOT APPEAR — the deletion, in the SHIPPED artifact

⚠️ **THIS SECTION EXISTS BECAUSE OF A HABIT THE GI SESSION PASSED ON, and a
deletion is exactly the case that needs it.** Most declarations assert what must
APPEAR. A check that can only detect absence cannot detect a deletion that
failed to happen — "is the new card shipped?" would pass just as happily on a
build that still carried the whole retired surface.

Grepped inside the RUNNING production container (`/app/apps/transcribe-md/.next`):

| token | files | |
|---|---|---|
| `qm-lin-rx` | **0** | ✔ |
| `qm-warn-` | **0** | ✔ |
| `review-doc-rx-gate` | **0** | ✔ |
| `rounds-critical-band` | **0** | ✔ |
| `rx_gate` | **0** | ✔ |
| `rounds-signed-trail-rx` | **0** | ✔ |
| `qm-rounds-rx` | **0** | ✔ |
| `OVERRIDE_REQUIRED` | **0** | ✔ (the retired refusal code) |

### MUST APPEAR — the restore

| token | files | |
|---|---|---|
| `review-doc-prescriptions` | **2** | ✔ |
| `qm-rx-list` | **3** | ✔ |
| `review-doc-rx-action` | **2** | ✔ the action tag, whose absence was the second defect |

### POSITIVE CONTROLS — the grep and the traversal are real

**Eight zeroes above mean nothing without these.** A traversal that silently
covered nothing would print the same table.

| token | files |
|---|---|
| `qm-rdoc-gate` | **3** |
| `review-doc-em-gate` | **2** |
| `ATTESTATION_REQUIRED` | **1** |

### MUST NOT CHANGE — everything else

- co-tenants exactly at baseline: app **307** · admin **404** · quillmd **200** ·
  www **200** · pro **410**
- 25 containers up, **0 unhealthy**, app and worker restart counts **0**
- standing checks exit 0: `check-imaging-em-artifacts`,
  `assert-migrations-applied`, `check-composite-fk`, `check-ingress-tls`

## VERDICT

**Every declared quantity matches. No difference outside the declaration.**

No clinical record was opened, signed, exported or mutated to produce any line
above. Rollback `:pre-r5-20260814` remains tagged for app and worker, verified
against the running digests at the time of tagging.
