# R1-05 qualified fixture wire — 2026-10-04

The unchanged synthetic R1-05 route still held Plan after the document-status
source repair. Two actual-route failures are retained separately on exact
`1684c2b8105534d66895783f78443215c33c4d59`. Both used the same original hash
`a6e0f938487cc6c9eca71d72840e66df7ae72dad46f7714fa1b5f01e7a49ce42`, the actual
partial-coverage mapping containing only Plan, and notes:

```
Consent form signed and dated: Yes
Plan: Rest.
```

The first route used the historical fixture default `gpt-4.1-mini`, an invalid
Anthropic request profile and `natural-v1`, with no ordinary field relation.
One method failed in 14.979 seconds. The distinct qualified rerun stored
`claude-sonnet-5-5`, `claude-sonnet-5-5-ordinary-v1`, between-tools thinking,
medium effort, a 20,000-token limit and `ordinary-field-relations-v4`. It also
failed, in 14.893 seconds. Each database was destroyed and a direct catalog
query proved it absent. Neither run sent a provider request or exported a file.

The qualified fixture wire classified the consent-status source as unresolved
because its human destination had been explicitly removed from the current
mapping. That unresolved relation invalidated Plan's complete relation. The
pure source tests had used an independent status relation, so they had not
qualified this actual fixture output.

Two intermediate diagnoses are withdrawn explicitly. The invalid historical
profile was a real limitation of the first run, but was not the complete cause
of this route failure. The missing `answer_text` in the assembler call was not
the qualified relation's rejection: the relation reader permits `None`. Its
unresolved source relation was the demonstrated rejection.

The repair changes only fixture relation classification. An otherwise unresolved
status can become independent for a selected ordinary field only when the
existing `completed_document_status_boundary` proves a closed affirmative
document event and its separate exact own-labelled answer. Questions, negation,
future/conditional/incomplete status, human actor subjects, foreign preceding
clinical scope and invalidated status remain unresolved. Other unresolved source
governors stay in the whole wire. The validators, relation requirements, prompt,
provider request contract and no-relation behavior are unchanged.

The new six-method fixture packet was run before the repair: three positive
answer assertions and three affirmative-wire ownership assertions failed in
4.732 seconds; the negative and invalid-profile guards passed. After repair,
33 focused methods passed in 37.966 seconds, including completed-status,
reviewed-speaker and retained prompt/evidence controls. Three existing labelled,
ambiguous/repeated and option/part-schema fixture methods passed in 3.055 seconds.

A separate offline replay uses the actual captured original mapping and the
same validators, loading the retained caedf fixture body read-only in memory.
Its 20 fixed inputs contain three affirmative positives and 17 negative cases.
The retained fixture supports 0/3 positives; the repaired fixture supports 3/3.
Both support 0/17 negative cases. The repaired negatives also remain held at the
page and forced-supported finalization boundary. This is deterministic fixture
evidence, not provider or microphone qualification.

Runtime evidence is under
`storage-resume-20261003T215613Z/clinical/r105-actual-1684-diagnosis` and
`clinical/r105-qualified-1684-capture`; both first route outputs and originals
remain intact. The Word-owned route-test patch is supplied separately as
`r105-qualified-test-proposal.patch` for the integration owner. It qualifies
the unchanged route under the actual application profile and asserts its first
automatic Plan answer, evidence and stored configuration before review. The
post-repair actual route, persisted finalization and original DOCX export still
require the integration owner's serialized QA run.

The independent numeric procedure-date correction false hold remains open. Its
read-only diagnostics were preserved and paused; this change does not repair it.
