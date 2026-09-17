# QuillMD

Fresh doctor and administrator application in [rebuild/](rebuild/README.md). The existing marketing site remains in `apps/marketing` with `packages/shared`.

The 2026-09-17 owner decision starts with empty application data: no import of old accounts, patients, documents, templates, balances or history. Development and verification use synthetic data on localhost. Historical documentation describes the retired application and must not be used as a setup or migration plan.

- [Durable continuation checkpoint](docs/rebuild/CHECKPOINT.md)
- [Private hosting and access](docs/rebuild/private-hosting.md)
- [Cost definition](docs/rebuild/cost-definition.md)
- [Document capabilities and SDK evaluation](docs/rebuild/document-sdk-evaluation.md)
- [Authorized private test scope](docs/rebuild/pentest-scope.md)

Marketing: `npm ci --ignore-scripts` then `npm run build`. Fresh application setup and tests: [rebuild/README.md](rebuild/README.md).
