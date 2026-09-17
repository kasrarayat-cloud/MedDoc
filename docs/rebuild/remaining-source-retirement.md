# Remaining old source retirement — 2026-09-17

The owner-authorized fresh start includes removal of old application implementation. This follow-up removed only the following tracked source files from the isolated fresh worktree. Shared main, live cron, running services, credentials, historical documentation and ignored generated reports were not changed.

## Exact files removed

| Path | SHA-256 before removal |
| --- | --- |
| `scripts/deploy-prod.sh` | `773decd38d85d1957db56b4524efaf51236ca0c48fdb6457d65d6b2145f70f2e` |
| `tests/automated/e2e/email-destination-guard.spec.ts` | `381871d7a5b220df4dc23d5039ccba654ccfa47b3564f0507ff00d946f9d511e` |
| `tests/automated/e2e/full-visit-flow.spec.ts` | `8d8182b6dbf9babf6dfdc872c65c489b0a9d55a4471312bd798a56a59e18afc2` |
| `tests/automated/e2e/helpers/auth.ts` | `c5cc97f3e82c2a4458ad00166885844a44e6fa9e4e923ba29cb9d77f3ba8ecc6` |
| `tests/automated/e2e/helpers/env.ts` | `ae86e3b501776988d1559fd1d63ae40519d46b040d4e8f335a0b1de195f07024` |
| `tests/automated/e2e/helpers/similarity.ts` | `44c07ba3a56a30bd1987b611077a9864d57abfddf4e8e47e6eb71440a4ea3fe3` |
| `tests/automated/e2e/mobile-responsiveness.spec.ts` | `32b3c46fee34e54a1b02f6f2b6b9571b462c3c073b485dcf04052ae179641896` |
| `tests/automated/e2e/password-policy.spec.ts` | `925800ca70686257acf853d1f8e353b505999dc4d554e14974b4ceb9fad41c46` |
| `tests/automated/e2e/playwright.config.ts` | `de3be492febda66f352e89862339b79575b5b4cdb9a0f99f13efb6ef37a32e53` |
| `tests/automated/e2e/product-separation.spec.ts` | `3fc2cf3aca97c2694ba05face892d954325227ccee95f95f176532fe567e0bf9` |
| `tests/automated/e2e/rate-limiting.spec.ts` | `84444f08faf9037f094a216ba3ba0d51c0cd8a2e0707d8d52f295e89e82dde4f` |
| `tests/automated/e2e/soap-determinism.spec.ts` | `5428029bbefe5b25f3001b886b480cd60daa69953d06b6710f2f127913f1c2e5` |
| `tests/automated/lib/flatten_playwright.py` | `a246750037889a903ca7e7a2ca923c667d66a59999f50d18ec030340a46e0859` |
| `tests/automated/lib/render_report.py` | `d64c6537929c6a1b572faf4f52d23e1368b9b8428b643ad8d9ce528edab016e9` |
| `tests/automated/reports/.gitkeep` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/automated/reports/template.html` | `5ccd01ceef3d31a3d1b2af2a15b166e8290f69017c3c7f9173c6fff920553878` |
| `tests/automated/run-all.sh` | `50b3738c5b388dfe57f9c9e296f2129c55f48167a6c8e2ef2b5a325e7792491b` |
| `tests/automated/smoke/auth-flow.sh` | `39bf23347a4b1b4ef90948d183f63b20aa640851c71664eeec72b9784eeabb49` |
| `tests/automated/smoke/health.sh` | `85c1c0e7585dde6fa314b62d5236569b206c69a0cab6568e9060731465ea763e` |

## Ownership and preserved dependencies

The old E2E and smoke suites authenticated against the retired Next.js app and used its deleted fixtures/workspace. Their runner and report renderer/template have no remaining monitoring consumers. The old deployment script built and started the retired application, worker and Prisma migration services; preserved Compose services, GitHub workflows, inspected systemd units and cron jobs do not call it. Remaining references in shared guards are explanatory comments or historical instructions.

The monitoring scripts, `tests/automated/lib/common.sh`, environment files, report outputs, historical README/FIXTURES documents, notification configuration, and reboot/encrypted-mount checks remain. `tests/automated/setup-cron.sh` now installs only uptime, disk and container monitors; its old nightly smoke/E2E entry was removed from the source template. The installer was not executed.

Only unambiguous old entry points were removed. Shared sandbox/process and deployment-guard helpers remain; this cleanup does not treat incidental old names in historical comments as service ownership. The UI agent owns the independent uptime/reboot verifier updates.

## Verification

Static shell parsing of the modified installer passed. Its cron template contains exactly the three preserved monitoring commands and no old application runner. File deletion was preceded by tracked clean-state, path/symlink and source-ownership checks. No live mutation or notification was used for verification.
