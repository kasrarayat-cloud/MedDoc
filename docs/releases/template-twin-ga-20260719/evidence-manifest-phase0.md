# Template Twin GA Phase 0 evidence manifest

Generated: 2026-07-19T06:13:48Z

This manifest contains identifiers and hashes only. It contains no credentials, patient data, physician documents, or production dump contents. Mutable status documents must be re-hashed in a later manifest whenever they change.

| Evidence | Identifier / SHA-256 | Notes |
|---|---|---|
| Accepted remediation commit | `79c04e88785a16e8e3b37b58544e107e3a16996e` | Git object verified from `origin/pr/370`. |
| Accepted remediation tree | `1450b6fe4acdd78f0d6c46df5ef276e86735ab93` | Equals consolidated merge tree. |
| Consolidated merge commit | `719eea4b27c68cc76e6bf485612c833705cef913` | Parents `1be101912f01293de3b8fddae722c823ecc86f29` and `79c04e88785a16e8e3b37b58544e107e3a16996e`. |
| Equivalent preflight report | `519d771c30906d3e5c6a0f1645fa6ac5e21380ed2dd9297b20ec95001cf847ba` | `docs/preflight-reports/preflight-20260719T055320Z.md` |
| Phase status snapshot | `2f3f1b192540adf7c29422ec66fea5f3ce0b34dc059fbd132dbacab508d4a9f7` | Status at 2026-07-19T06:13:48Z. |
| Decision/blocker snapshot | `c8f53ed4ca1276afde42b351402a85b16365e3e5eb0e3db8eeba72d6272cff75` | Blocker register at 2026-07-19T06:13:48Z. |
| Release checklist snapshot | `fba7f01b2afd58b5999e1f46b295b704e820168b67eae8d0d441e01d15196041` | Checklist at 2026-07-19T06:13:48Z. |
| Rollback plan snapshot | `22aee12ade81e69797a19f7e29c4df6802dcfe5140439b91067bd73fbc5f6ac8` | Plan remains FAIL pending rehearsal. |
| Preserved app image config | `sha256:95f57158e3fe56acc832793be3f5da972cc1fdc6c3b85166f8387b3a103f1f90` | Exact running pre-release image ID. |
| Preserved worker image config | `sha256:412dd3157475fd60a77d417a6db6880343d58755aaf76f044be035fba4acf44e` | Exact running pre-release image ID. |
| Preserved image archive | `73bde836cc4983e7803caf2bda605955023e7eb2ad26f045d5b0fb9d87af8b3a` | Mode-0600 file outside Git; gzip integrity passed. |
| Latest production backup container file | `4312095f509e284ac5d7fe016898764f71d571ff36474a38cc54d1bb8df51823` | Gzip integrity only; PHI-bearing contents were not opened in QA. |
| Disposable restore PostgreSQL image | `sha256:8ed3192326bb9d114cd5ef9acace453d5dae17425bd089d089330584c84c5a34` | Network-isolated schema-only restore target. |

The source observations supporting infrastructure FAIL states are deliberately summarized in the status and blocker register rather than exporting configuration or command output that could contain sensitive operational details.
