# Fresh private verification — 2026-09-17

## Executed results

- Full fresh Django/PostgreSQL suite: **70 tests pass**, 10.897s in final local run. Actual isolated PostgreSQL test database created and dropped. Includes concurrent wallet/grant/job/payment operations, scope/membership checks, MFA, CSRF, immutable records, signed usage quotes, terminology, workflow and optional-email mocked HTTP tests.
- Isolated document suite: **14 tests pass**, 10.207s. The actual kernel sandbox rejects filesystem/network/process escape. Word/PDF originals, output values, formatting, overflow refusal and malformed/malicious inputs are exercised.
- Portable browser gate: **12 checks pass** against an actual temporary fixture server/worker. Upload and mapping, supported answers with source evidence, review/finalization/DOCX download, mobile layouts, access exclusion, browser JS and Axe checks pass. Test server stopped and temporary screenshots/download deleted; JSON report retained. CI uploads only that exact JSON file, including its hidden parent directory.
- Django system check: no issues; schema drift check: no changes. HTTPS deployment check has only HSTS include-subdomain/preload policy warnings: these are deliberately not asserted across preserved shared hosts.
- Marketing clean dependency install and production build passed (13 static pages); production npm audit reports zero vulnerabilities. Python locked dependency audit reports no known vulnerabilities.
- Latest real queue smoke at08:48:57Z: Anthropic535 input/79 output tokens, defined cost0.002790000000, charge0.004185000000. Deepgram1.0second, defined cost0.000071666700, charge0.000107500050. Both jobs succeeded and ordinary ledger rows equal exact1.5×cost. Voice input was generated silence; this proves API/metering integration, not speech accuracy. `live-provider-verification.json` records provider units/results.

## Refutation and repair

Finished clinical-generation/document diff was challenged with concrete counterexamples. Repaired: extraction of a reassuring substring from a negated/uncertain/family-history line; omission of conflicting repeated labels; loss of inherited multiline scope; cached revoked-user permission; changed payer/rates after reservation; repeated transcription billing; financial receipt lost on output-storage failure; accepted coding evidence stale after voice edit; draft validation500; hidden Word answer runs; a malformed second placeholder silently ignored. Regression tests now exercise these cases. Source quotes remain conservative and complete; model output does not invent clinical prose.

Service/CI review found a hidden-directory artifact upload that would silently drop the browser report; fixed with the exact report.json path and include-hidden-files. Obsolete public status expectations and retired QA boot advice were replaced with declared maintenance/private service checks. Mocked service/HTTP probes passed; a transient systemd-readiness exception was also repaired before activation. No notification was sent as a test.

## Boundaries

All clinical material and accounts used are synthetic. Tests are internal authorized adversarial work under pentest-scope.md, not an independent penetration-test certificate. Stripe/provider email mocks are not live integrations. No real Stripe payment, refund or clinical CPT lookup occurred. Advanced arbitrary Word/PDF/OCR support is not implemented without the required SDK/qualification. Remote CI and post-merge private activation are recorded separately by exact commit, never inferred from these local results.
