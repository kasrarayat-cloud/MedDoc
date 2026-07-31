## Release status

**NOT RELEASED. Production rollout remains 0%.** This draft consolidates the
accepted Template Twin stack and its additive defensive hardening. It does not
authorize production migration, deployment, credentials, PHI, provider calls,
canary, or physician rollout.

- Accepted remediation: `79c04e88785a16e8e3b37b58544e107e3a16996e`
- Lossless integration merge: `719eea4b27c68cc76e6bf485612c833705cef913`
- Provider-ownership implementation: `db1cab904ac5c8d6c7f25878f59d71e1b094a223`
- Authentication/authorization implementation: `9a1ded49055d1aef153864b28267c81ab1b0506d`
- Additive runtime/database authority remediation:
  `bcf5c0bbc098ec777ab850cc3df4e72070453402`
- Exact worker-role remediation after detached review:
  `2d9c8f8e41fc0e20279ae3d6a253ec10405bc367`
- Base: `1be101912f01293de3b8fddae722c823ecc86f29`
- PRs #362–#370 and their audited history remain unchanged.

## What changed and why

The hardening closes authentication and authorization integration defects that
were not covered by the earlier scoped review. Production startup now requires
one exact, closed runtime identity spanning service role, database principal,
connection profile, verifier profile, and authentication-safe flags. MedDoc
mock authentication is non-production only, current database-backed
entitlements replace stale token authority, and configured partial identities
fail closed. The Next build-only exception is bounded to an unconfigured build
phase and runtime start uses a guarded entrypoint. The clinical worker also
binds itself to the exact `transcribe-md-worker` role before database proof or
queue construction.

The database boundary now validates canonical connection options, exact
least-privilege principals, SCRAM attestation, a closed role graph including
the backup principal and predefined read role, target-bound online auth-token
approval, and dump/restore/re-provision behavior. All changes are additive; the
default rollout and kill switch remain fail closed.

## Verification

- Full TranscribeMD units: 417 files / 5,614 tests PASS.
- Full MedDoc units: 11 files / 103 tests PASS against a fresh disposable
  synthetic PostgreSQL database after 97/97 migrations.
- Both application type checks and production builds PASS.
- Prisma 7.8 format/validate/generate and v9 generator sync PASS.
- Production runtime census: six long-lived services, migrator excluded, PASS.
- Production/QA database-principal censuses: seven/two services, PASS.
- Disposable PostgreSQL exact-principal, role-graph, auth-token,
  authentication-email, bootstrap-log, and backup dump/restore/re-provision
  proofs PASS; provider calls remained zero.
- No new lint debt versus the exact parent. Dependency audit reports 0
  critical/high. Verified-only secret scan reports 0 verified secrets.
  TypeScript Semgrep reports 0 findings.
- Independent exact-head reviews: PENDING while this draft body is prepared.

## Remaining gates

The authoritative PASS/FAIL/HUMAN PENDING checklist, blocker register, evidence
manifests, and rollback plan are under
`docs/releases/template-twin-ga-20260719/`. Production remains blocked on CI,
final RC verification, immutable images, a real six-runtime rollback rehearsal,
complete backup/PITR/object/queue recovery, production least privilege and
transport, credential-rotation closure, desktop Word evidence, and signed
Clinical Safety, Privacy/Legal, Operations, and authorized-physician decisions.

No production system was changed by this hardening.
