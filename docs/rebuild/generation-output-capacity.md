# Generation output capacity

New ordinary semantic-generation jobs configured for Anthropic
`claude-sonnet-5-5` use `bounded-output-32k-v2`: at most 32,000 output tokens
and a 240-second SDK I/O timeout per request. The input configuration is not
changed. Other configured models keep `bounded-output-16k-v1` (16,000/120).
The new profile refuses any other provider/model pair when read from a job.
Thinking, effort and temperature remain absent from the request, preserving
the provider's adaptive defaults.

The signed page quote and immutable job quote are recalculated for five
32,000-token requests at the recorded prices and discount. An old quote cannot
authorize the larger profile. Existing jobs retain their original configuration,
request bytes and quote: v1 remains 16,000/120, and no-profile jobs remain
4,000/60. Retained independent revalidation stays on its existing one-call v1
contract. Definition preparation remains two calls at 16,000/120.

The existing 512,000-byte request bound, five-call maximum, zero SDK retries,
completion/schema/source checks and metered failure accounting still apply.
An output-limit stop remains a failed retained response even if its text parses
as JSON. It produces no automatic retry or replacement answers. The timeout is
an SDK I/O limit, not a guaranteed whole-request wall-clock deadline; stale-job
reconciliation derives its existing additional 60-second grace from the stored
profile. Backup validation admits v2 through a separate exact provider/model
and typed-limit branch, preserving the historical branches.

This increases finite capacity; it does not guarantee every future source fits.
Any further capacity failure must retain its raw evidence and stop.
