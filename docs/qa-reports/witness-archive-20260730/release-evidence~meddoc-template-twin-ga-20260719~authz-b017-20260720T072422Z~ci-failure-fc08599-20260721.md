# Sanitized CI failure and log-exposure receipt

Recorded: 2026-07-21T08:50:00Z

Exact PR head: `fc08599533f75dbd7bdf878a9d23595ab83d4be0`

Production verdict remains **NOT RELEASED**, availability **0%**.

## Failed checks

1. E2E run `29815703035`, job `88586438447`, failed before application or
   database services started because `QUILLMD_POSTGRES_IMAGE` was absent and
   the production Compose contract requires an immutable digest.
2. Office/human-gate run `29815703432`, job `88586439995`, failed in the static
   database-principal census because `docker compose config --no-interpolate`
   left a required MFA keyring volume expression unresolved; Compose parsed its
   `:?` syntax as extra short-volume colons and did not emit valid JSON.

## Credential-log incident

The E2E job generated disposable synthetic database/object-store credentials
and exported them through the job environment without first registering them
with the GitHub Actions masking channel. GitHub consequently rendered the
generated values in the failed build step's environment preamble.

No credential value is reproduced or retained here. The Compose failure
occurred before service startup, and the values were scoped to the disposable
CI job. Nevertheless, unmasked credential logging violates the release
security boundary and is a blocking workflow defect.

The exact run metadata and sanitized root-cause summary above are retained.
The raw logs for only run `29815703035` are being deleted through the GitHub
Actions API to remove the exposed values; that deletion is irreversible. The
run/check metadata remains available.

## Required additive closure

- Register every generated secret with `::add-mask::` before writing it to
  `GITHUB_ENV` or using it in later steps.
- Provide all immutable image variables required by the E2E Compose build.
- Make the static Office principal census resolve non-secret structural
  placeholders without weakening unresolved service-principal checks.
- Add workflow source-contract tests for masking order, immutable image inputs,
  and the valid static-census command.
- Rerun local verification, obtain fresh detached exact-head reviews, publish
  additively, and require fresh CI.
