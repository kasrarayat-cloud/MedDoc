# Exact-head lower-severity dependency debt

Generated: 2026-07-21T07:17:00Z

Exact head: `3a9151584c295ec168515f8d515c9bd3c7fb8a56`

## Gate result

- Production dependency audit: 1,195 dependencies
- Critical: 0
- High: 0
- Moderate: 12
- Low: 1
- `npm audit --omit=dev --audit-level=high`: PASS

This register is not an acceptance. Every row requires targeted remediation or
an authorized final-RC risk disposition. No automated force-fix or unsupported
major downgrade is authorized.

| Package | Severity | Direct | Reported affected range | Reported remediation constraint |
| --- | --- | --- | --- | --- |
| `@anthropic-ai/sdk` | moderate | yes | `0.79.0 - 0.91.0` | npm proposes `0.112.4`, a SemVer-major application/provider change |
| `@babel/core` | low | no | `<=7.29.0` | transitive update reported available |
| `@hono/node-server` | moderate | no | `<1.19.13` | transitive update reported available |
| `@opentelemetry/core` | moderate | no | `<2.8.0` | transitive update reported available |
| `@opentelemetry/instrumentation-http` | moderate | no | `<=0.16.0` or `0.19.1-alpha.7 - 0.218.0` | transitive update reported available |
| `@opentelemetry/resources` | moderate | no | `0.8.0 - 2.7.1` | transitive update reported available |
| `@opentelemetry/sdk-trace-base` | moderate | no | `<=2.7.1` | transitive update reported available |
| `@prisma/dev` | moderate | no | `<=0.24.8` | transitive update reported available |
| `@sentry/nextjs` | moderate | yes | `8.0.0-alpha.2 - 10.53.1` | update reported available; integration regression required |
| `@sentry/node` | moderate | yes | `8.0.0-alpha.1 - 10.53.1` | update reported available; observability regression required |
| `next` | moderate | yes | `9.3.4-canary.0 - 16.3.0-canary.5` | npm proposes an unsafe major downgrade; do not apply automatically |
| `postcss` | moderate | no | `<8.5.10` | npm routes through the unsafe Next downgrade; targeted override/update analysis required |
| `prisma` | moderate | yes | `6.20.0-dev.1 - 7.9.0-dev.31` | update reported available; migration/client regression required |

Required disposition evidence for each row: installed path, advisory identity,
runtime/development reachability, chosen fixed version or compensating control,
test result, owner, approver, and expiry/revisit date. Until recorded, blocker
`B-029` remains FAIL.
