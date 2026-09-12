# SLICE-0 adversarial pass — colon twin + TEMPLATE-CHOICE-1 (2026-09-12)

Mandatory refutation pass over the finished diff (this path decides which
Template Twin fills a clinical note). Five distinct lenses, each told to REFUTE;
every finding independently verified before a line was changed. Two lenses found
NOTHING (tenancy-scope-leak, migration-schema).

| # | lens | sev | verdict | fix |
|---|------|-----|---------|-----|
| 1 | wrong-twin-fill-mismatch | MINOR | REAL | A de-certified practice-default that is the viewing doctor's OWN active/draft template was still pre-selected — the picker guard checked list-membership (`seenTemplate`), not certification. **Fix:** guard on a `certifiedIds` set (`page.tsx`); gate arm forbids the `seenTemplate` form and requires `certifiedIds.has(...)`. |
| 2 | twin-authoring-cert-readiness | MAJOR | REAL | P5's PHI scan matched only attribute-free `<w:t>`, so a filled value in `<w:t xml:space="preserve">…</w:t>` escaped; and it scanned the source constant, not the committed `.docx`. **Fix:** regex `<w:t\b[^>]*>([\s\S]*?)</w:t>` (attributed + multiline), and scan the committed `.docx`'s `document.xml` as well as the constant. |
| 3 | twin-authoring-cert-readiness | MINOR | **FALSE** | P4's fresh-build compares only aliases — but no real regression passes green (P4 also pins document.xml sha + structureSha + every fieldId from the committed artifact). Fully backstopped; no change. |
| 4 | owner-gate-and-false-green | MAJOR | REAL | The gate's `clinicalReads()` classifier short-circuits on `file ∈ DOCTOR_SCOPE` BEFORE `isScoped()`, so deleting `practiceId` from the picker's certified arm leaked **every** practice's certified templates yet both gate suites stayed green (measured 28/28). **Fix:** a dedicated positive control asserting the certified picker read carries `practiceId: session.user.practiceId` — mutation-proven: it REDs on exactly that deletion, reverts clean. |
| 5 | owner-gate-and-false-green | MINOR | REAL | The non-owner behavioural arm asserted `reason: 'NOT_PRACTICE_ADMIN'`, a value production can never emit (`requirePracticeAdmin` emits `ROLE_MAY_NOT_ADMINISTER` / `UNAUTHENTICATED`). **Fix:** assert the real `ROLE_MAY_NOT_ADMINISTER`; noted the real guard is exercised in `gate-admin1-practice-admin.test.ts`. |

**After the fixes:** tsc clean; the three affected gates 35/35 green; the F4
leak mutation and the P5 attributed-run vacuity both demonstrated and closed.
No cross-tenant leak and no wrong-content misfill was found in the shipped code;
findings 1/4 were latent false-greens that would have hidden a FUTURE regression,
which is exactly what the pass exists to catch.
