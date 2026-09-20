# Stripe return verification repair — 2026-09-20

## Demonstrated runner defect

An unauthenticated GET of the actual private application's configured success
URL, `http://localhost:9130/billing/?payment=processing`, returned HTTP302 with
`Location: /login/?next=/billing/`. The runner had authenticated at `127.0.0.1`,
whose host-scoped session is unavailable at `localhost`. The former Playwright
wait required the intermediate billing URL to become the committed page URL;
the HTTP redirect commits the login page instead. That wait could therefore
fail after Stripe had already accepted payment.

The repair observes an actual GET navigation in the main-document response
chain to the exact configured success origin, path and query. It accepts the
resulting HTTP200 login redirect or an HTTP200 authenticated billing page,
then continues reading balances at the canonical origin. Direct login visits,
another origin, wrong/extra success parameters, fetches and iframe navigation
do not supply this evidence. Cookies, application access policy and billing code
are unchanged. Observed URLs in reports contain only the private application
location; hosted Checkout links and credentials remain excluded.

The optional `--attempt <label>` accepts a bounded lowercase filename label and
retains exclusive evidence creation. Use it only after inspecting the previous
attempt. For example, `--attempt 20260920-a1` keeps the original failed dry-run
report unchanged. This changes the evidence filename, never the checkout limit
or the rule against automatically repeating uncertain payment requests.

## Focused execution evidence

Executed locally with real Chromium and two ephemeral loopback HTTP servers:

```text
node --test rebuild/ops/test_stripe_verification_navigation.mjs rebuild/ops/test_stripe_verification_outcome.mjs
```

Result: **17 tests passed, 0 failed, 0 skipped**. The positive redirect test
simultaneously observed the repaired chain and demonstrated the old committed-URL
wait timing out. Remaining browser cases qualify the authenticated return and
reject the five false-evidence classes above. Argument checks reject ambiguous
modes, duplicate/unknown options, invalid SHAs and unsafe attempt labels. Existing
outcome tests retain incomplete status without verified duplicate/retry/order
receipt. No Stripe/provider request, checkout or application write was made by
these isolated tests. Their local servers and browsers were closed afterwards.

These are runner checks, not real Stripe sandbox acceptance. That remains the
separately declared application/CLI exercise and its private execution evidence.
The earlier readiness reports and failed attempt remain historical records.
