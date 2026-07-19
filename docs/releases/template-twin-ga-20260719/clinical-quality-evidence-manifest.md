# Clinical-quality evidence manifest

Generated: 2026-07-19T07:42:03Z  
Evaluated technical head: `a351fa7309a59d114a9bdee736c8d9b3b32b5d01`

All inputs are committed synthetic fixtures, deterministic tests, or aggregate historical reports. No patient document, physician document, real clinical audio, credential, or environment file is included.

| Evidence file | SHA-256 | Role |
|---|---|---|
| `apps/transcribe-md/src/lib/template-twin/__tests__/voice-text-docx.e2e.test.ts` | `0b954925f043267a28de7ce6afdbe6abaddf4778a8efe90628230d499b3a164b` | Voice/typed DOCX behavior |
| `apps/transcribe-md/src/lib/template-twin/__tests__/fill-engine-equivalence.test.ts` | `41876f73cb407583760f5bbeaca109458bfd3695a922ccaa26fbba0d99333a89` | Matched canonical resolution |
| `apps/transcribe-md/src/lib/template-twin/__tests__/encounter-evidence-verification.test.ts` | `8f007fc47da03667f04df31332d2c216b2b42e3d7b0a3904cdf75a57d46d7039` | Exact source-anchor revalidation |
| `apps/transcribe-md/src/lib/template-twin/resolver/__tests__/resolver.test.ts` | `d66845e725d82f2b6bd319c1e2591dcc012e4613849473ae9c9f1f97f79eaac1` | Resolution, exact options, missing units/laterality |
| `apps/transcribe-md/src/lib/template-twin/validation/__tests__/validation.test.ts` | `f2dc9aeaca3ddf5f4b521df3bacc89703292867f7c79b307fd89fddf3eb2639f` | Independent value/evidence validation |
| `apps/transcribe-md/src/lib/template-twin/__tests__/certification-coverage.test.ts` | `79c31859885cbad302d3319d8cb0809a27de8dc17675eedfd65eb2d8c246b502` | Certification exercise coverage |
| `apps/transcribe-md/src/lib/template-twin/custom-concepts/__tests__/custom-concept-extraction.test.ts` | `dcd87e5e991e460aa93751ba4870d18013f78479c86cda415aecf325e65b9104` | Custom scalar extraction boundary |
| `apps/transcribe-md/src/lib/template-twin/custom-concepts/__tests__/custom-concept-runtime-integration.test.ts` | `dbc4118a62d155fb7c1a6ba2fa1ef1d8b3a6251f16999eff7093e1d1e5c2c1b4` | Custom scalar runtime integration |
| `apps/transcribe-md/src/lib/template-twin/__tests__/supported-concepts.test.ts` | `d3f4c1892ccbf63a3206bc81638a2c714890458023d8aa760779670724ded327` | Declared concept boundary |
| `apps/transcribe-md/src/lib/template-twin/__tests__/synthetic-evidence-gate.test.ts` | `69cbb9439ece836c6cfd21d7550283cd73f5cd5aaf89e67c96648a659525e097` | Synthetic evidence fail-closed gate |
| `docs/qa-reports/pre-pilot-baa-status-20260610T152350Z.md` | `e71ee5da398491a964cf2ce962b46a72530cb20c6738f43999d956814fa41f82` | Historical processor/BAA inventory |
| `docs/qa-reports/hallucination-reconciliation-20260611T072219Z.md` | `db0df3693725dd2b828ff3850200a90258cd1b2f0ae502b32bb74bed4b2b2101` | Historical metric reconciliation |
| `docs/eval-runs/primock57-fullchain-fabrication-20260706T205036Z.md` | `eef536cc55965ab780551331d0dc000ada37e130b532144dd4a7a0622f3d7646` | Historical provider context only |

Deterministic cohort result: 10/10 files, 176/176 tests PASS.  
Release-head live-provider Template Twin result: `n=0`, FAIL / not measured.
