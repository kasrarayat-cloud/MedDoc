---
id: A12-P2-003
title: No CHANGELOG; no OpenAPI / external API contract; no BAA template PDF; no DPA
severity: P2
domain: docs/external-contract
---

# Issue

Three smaller-but-related missing artifacts:

1. **No CHANGELOG.md or release notes.** Milestones exist (T-M10..T-M17.2 per memory; up to Phase 7 + §22 Phase 6.2 in POST_MERGE_TODO). They are documented inline in POST_MERGE_TODO sections — but that's a 1421-line operational scratchpad, not a release log a customer or auditor can read. There is no published per-release changelog.

2. **No OpenAPI / API contract for external consumers.** `docs/PROTECTED_CONTRACTS.md` lists 62 internal API routes — but this is a remodel-protection doc, not an external contract. There is no machine-readable API spec, no published API documentation, and no Postman/Insomnia collection. Likely fine if QuillMD is closed-API-only — but the LAUNCH_CHECKLIST §10 ("Out of scope: EHR integrations") suggests integrations may come — and `apps/marketing/src/app/security/page.tsx` likely references a partner integration story.

3. **No BAA template PDF for clinic customers.** The HIPAA page commits to executing a BAA with each Covered Entity that signs up (`apps/marketing/src/app/hipaa/page.tsx:84-96`). LAUNCH_CHECKLIST §7 has "[ ] BAA template (for clinic customers)" unchecked. There is no draft template, no `docs/legal/BAA_TEMPLATE.md`, no PDF on the marketing site at `/baa-template.pdf` (the LAUNCH_CHECKLIST proposes that path). The first practice that asks for a BAA forces ad-hoc generation.

4. **No Data Processing Addendum (DPA).** GDPR-relevant if QuillMD ever serves European clinics; California-relevant under CMIA; broadly relevant in B2B SaaS. Nothing in `docs/` or `apps/marketing/src/app/`.

5. **No SOC 2 readiness checklist.** LAUNCH_CHECKLIST does not gesture at SOC 2; not strictly needed for pilot. But the longer the pilot runs, the higher the chance a prospect asks "are you SOC 2?" — having a "we plan to start the SOC 2 process at <user-count milestone>" line is enough; the absence of any mention is the gap.

# Evidence

```
$ ls /opt/meddoc-pro/CHANGELOG.md
ls: cannot access '/opt/meddoc-pro/CHANGELOG.md': No such file or directory

$ find /opt/meddoc-pro -type f \( -name "openapi.*" -o -name "swagger.*" \) -not -path "*/node_modules/*"
(no results)

$ find /opt/meddoc-pro -type f -iname "*BAA_TEMPLATE*"
(no results)

$ find /opt/meddoc-pro -type f -iname "*DPA*" -o -iname "*data-processing*"
(no results)

$ find /opt/meddoc-pro -type f -iname "*SOC*"
(no results)

$ ls /opt/meddoc-pro/apps/marketing/public/baa-template.pdf 2>/dev/null
(no such file)
```

The closest things to a changelog:
- `POST_MERGE_TODO.md` — operational scratchpad, 23 numbered sections, mix of in-progress and completed. Useful internally; not customer-facing.
- Git tags (`phase-7-landing-v6-live`, `ci-fully-green`, `phase-6.2-backup-scripts-shipped` etc.) — exist but no human-readable release notes attached.
- `LAUNCH_ANNOUNCEMENT.md` — single-shot launch announcement variants; not a recurring changelog.

The closest thing to API documentation:
- `docs/PROTECTED_CONTRACTS.md` (62 internal routes table) — internal, remodel-scoped, doesn't claim to be an external contract.
- Per-route file headers in `apps/transcribe-md/src/app/api/**/route.ts` — JSDoc-ish, scattered.
- `apps/transcribe-md/WORKER.md` — pipeline-level only; not API.

The BAA template:
- `docs/BAA_CHECKLIST.md` — tracks subprocessor BAAs (i.e. we sign with them). Does not include a template for the BAA that we (as the BA) offer to a CE customer.

# Risk

- **Customer trust at first ask**: a doctor's practice asking "send me your BAA template" expects a polished PDF, not "we'll draft one for you." First impressions are load-bearing in B2B medical SaaS.
- **Audit history reconstructability**: a reviewer asking "what changed between Phase 5 and Phase 7?" reads POST_MERGE_TODO §8 + §13 prose. A two-line CHANGELOG entry per PR would let the reviewer skim a year of releases in 5 minutes.
- **Sales-ops drag**: every prospect-info request (BAA template, DPA, SOC 2 status) is bespoke. A pre-written one is a 90% reduction in cycle time.
- **Pilot doctor onboarding**: KASRA_HANDOFF §C asks pilot intakes to record "specialty, average daily charting time, current EHR" — the BAA + DPA are the next questions practice admins ask. Pre-positioning these accelerates pilot expansion.

# Recommended fix

**1. CHANGELOG.md (root)** — the standard "Keep a Changelog" format. One entry per PR / phase. Link the SHA, the PR, and the milestone. The entries already exist as POST_MERGE_TODO sections; lift the headlines into a CHANGELOG. Maintenance going forward: every merged PR adds a line under `## [Unreleased]`; every tag promotes Unreleased to a dated section.

Skeleton for the existing history:
```
## [Phase 7 — landing-v6] - 2026-05-03
### Changed
- marketing/quillmd.com redesigned to "Apple Product Page" (POST_MERGE_TODO §13, PR #95, e4644dc)
### Performance
- Lighthouse desktop 100 / mobile 88 (LCP-bound; documented optimization)

## [Phase 6.2 — backup scripts] - 2026-05-04
### Added
- `infra/minio-offsite-sync.sh` for MinIO offsite encrypted backup
- `scripts/restore-drill.sh` for Postgres restore validation
### Pending
- MinIO restore drill runbook (A12-P1-002)
- Activation post step 11 of POST_MERGE_TODO §22
```

**2. OpenAPI spec.** If pilot is closed-API-only, document the decision as an ADR (per A12-P1-004) and skip. If any integration is in scope (DrChrono read-only cache, future EHR exports), generate an OpenAPI 3.1 spec from the Zod schemas already in `packages/types/`. `zod-to-openapi` works for this. Publish at `/openapi.json` on `app.quillmd.com` so a consumer can `curl` it.

**3. BAA template (we → CE).** Draft a markdown template in `docs/legal/BAA_TEMPLATE.md`. Once counsel-reviewed, ship as `apps/marketing/public/baa-template.pdf` and reference from `apps/marketing/src/app/hipaa/page.tsx`. Sections: parties, definitions per §164.103, permitted uses + disclosures, safeguards, breach notification (60-day per §164.410 — already committed publicly), subprocessor flow-down (linked to BAA_CHECKLIST), term + termination, return/destroy of PHI on termination, indemnity (modest cap consistent with TermsOfService §7).

**4. DPA.** Companion to the BAA but data-protection-law-shaped (CCPA, GDPR if applicable, state-level consumer privacy). Same file pattern: `docs/legal/DPA.md` → `apps/marketing/public/dpa.pdf`. Lower priority than BAA pre-pilot.

**5. SOC 2 readiness mention.** Add a short "Compliance roadmap" section to `apps/marketing/src/app/security/page.tsx` or `apps/marketing/src/app/hipaa/page.tsx`: "We plan to begin the SOC 2 Type 1 process at <N doctors / <date>>. The HIPAA Security Rule controls already in place (audit logs, access controls, encryption, BAA framework) are the foundation for the eventual SOC 2 audit." Honest, brief, expectation-setting.

For all five — once the doc exists, add a row to `docs/HIPAA_COMPLIANCE.md` (BAA template) and to `docs/ONBOARDING.md` (per A12-P1-003) so onboardees know where to find them.
