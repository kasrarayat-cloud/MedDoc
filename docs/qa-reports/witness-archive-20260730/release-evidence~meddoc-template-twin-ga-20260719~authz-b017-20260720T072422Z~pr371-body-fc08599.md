## Release status

**NOT RELEASED. Production rollout remains 0%.** This draft preserves the
accepted Template Twin stack and adds the reviewed authentication,
authorization, database-principal, operator-race, cleanup, and evidence-record
hardening series.

## Exact review head

- Branch: `release/template-twin-ga-20260719`
- Exact commit: `fc08599533f75dbd7bdf878a9d23595ab83d4be0`
- Tree: `445709204e165da4f82b88b6a21cc8adba106027`
- Base: `1be101912f01293de3b8fddae722c823ecc86f29`
- Accepted remediation: `79c04e88785a16e8e3b37b58544e107e3a16996e`
- Lossless integration merge: `719eea4b27c68cc76e6bf485612c833705cef913`
- PRs #362–#370 remain unchanged and in history.

## Exact-head technical evidence

- Full TranscribeMD unit census: **427/427 files, 5,759/5,759 tests PASS**.
- Fresh closed synthetic database replay on the unchanged runtime tree:
  **97/97 migrations PASS**, MedDoc **11/11 files, 103/103 tests PASS**, and
  zero labeled container/volume/image residue.
- Exact-head formatting: **8/8 PASS**; evidence-document regression contract:
  **12/12 PASS**.
- Independent scoped delta/document review: **ACCEPT**, no P0/P1/P2; receipt
  SHA-256
  `e7bcfef3c8c7c99859c061299f9cf9b67221ac1c538b4a02674d39175d96afd1`.
- Independent whole-head security review: **ACCEPT**, no P0/P1/P2; strict
  Semgrep **791/791** with zero skipped/errors/findings, focused **150/150**,
  all secret modes zero verified, shell **13/13**, and dependency gate zero
  critical/high. Receipt SHA-256
  `11d411ee0bf00fa123c2021f25f2121674729612d4c647e0fbc5af4d10a5cebd`.
- Independent whole-head authentication/operator review: **ACCEPT**, no
  P0/P1/P2; strict HBA, focused auth/operator/cleanup suites, both fresh
  PostgreSQL 16 adversarial harnesses, exact-principal/RI-trigger restoration,
  offline classification, and zero-residue cleanup pass. Receipt SHA-256
  `2af20d2d1e3a224ab22de3c62855bd7566abd795cbb0b0445533e70a4bd6ea0c`.
- Dependency debt remains explicit: **12 moderate and 1 low**, with no owner
  disposition fabricated.

## Gates that remain closed

This PR stays draft. CI at this exact published head, final identical-manifest
census, browser/load/Office evidence, immutable images, production
backup/restore and rollback, credential rotation, and production infrastructure
gates remain open. Desktop Word, Clinical Safety, Privacy/Legal, Operations,
and physician approvals remain HUMAN PENDING.

No production migration, deployment, feature-flag mutation, provider call,
public-registration change, or PHI-bearing test was performed.
