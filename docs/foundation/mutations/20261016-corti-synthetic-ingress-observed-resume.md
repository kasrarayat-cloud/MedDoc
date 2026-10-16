# Prospective declaration: observe asynchronous nginx publication

Carry forward the exact scope and preservation requirements of the two prior
20261016 Corti synthetic HTTPS declarations. The only installed application remains
40f78febd847b79efce3c13912d2edccc51eee16. No candidate restart, source change,
rebuild, migration, provider request or new test encounter is authorized here.

The first ingress resume validated/reloaded nginx successfully, but its immediate
public health request returned HTML rather than candidate JSON, and rollback
restored the original ingress. Its validation/reload/rollback logs and original
baseline remain preserved. Original hash was read back unchanged. Native unit
PIDs and original health revision remain unchanged. Asynchronous reload is a
possible cause, not yet a demonstrated explanation.

Execute updated ops.corti_https_publish_resume through the ruled-mutation gate.
Change only the retained candidate prefix; validate and reload with the existing
host sudo commands. Observe publication with at most 30 read-only public health
probes (2 second timeout each, 0.25 second intervals), preserving status/content
classification without response tokens. Require exact installed health revision
and synthetic-only/doctor identity. Roll back on failure. This is a server
publication check, not clinical generation, coding replay or provider inference.

Write new -02 logs/baseline/probes rather than overwriting the first attempt.
The existing root dashboard and all other ingress bytes must remain unchanged;
native unit identities must match before/after. Keep every original response,
FAIL verdict, clinical document, approval and test artifact. CPT remains held.
