# Composite date/narrative typing — independent refutation

**NOTHING FOUND within the bounded finished-diff claims.** Read-only review of
`/opt/meddoc-pro/.worktrees/v1-workflow-candidate`, parent
`ab41d7107f8ccb34bf64b034fdb28446fc7478b4`, dirty frozen engine SHA256
`21399290ec826f9c0c2b9e419b725a93008f39da565558ded076372990af0bc6`.
That source matches the author's `composite-kind-20260928/candidate.py` snapshot.
The baseline engine is SHA256
`c82ef298b59780238c4f995c6da4056d87ca939282b62c15e74ef185f362cad8`.

The finished delta only moves the existing LONG_LABEL check before existing
TIME_LABEL/DATE_LABEL checks in `Detector.kind_for`. Existing signature/initials
branches remain first. No regular expression, destination, writer or native date
control rule changed. The new test module is explicitly included in CI.

Twelve independently constructed pure-engine controls passed:

- Plain date of birth, D.O.B. and time retain their former kinds.
- Composite date plus description/details and time plus reason become long text.
- Signature plus comments and initials plus details remain signing kinds.
- Patient name and comments remain text and long text respectively.
- Two native date controls with narrative date/time aliases remain exactly equal
  to baseline, including kind, label, locator, context and fingerprint.

For the ten ordinary fields, every mapped property except the intended kind is
identical. Applicable populated exports are byte-identical between the two engines
for a synthetic full date/restrictions/time string. Signing fields were not filled.
The probe refuses network access and used no database, provider, corpus or renderer.

This is a narrow source/typing refutation, not independent confirmation of the
separate author's D30 workflow/render evidence or all possible label semantics.
No broader clinical or compatibility success is claimed.

Durable script/results: `composite-kind-independent-evidence-20260928/`.
Private immutable source snapshots:
`rebuild/.runtime/composite-kind-independent-20260928/{baseline,candidate}.py`.
