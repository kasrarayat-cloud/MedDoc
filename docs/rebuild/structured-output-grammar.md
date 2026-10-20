# Anthropic structured-output grammar sharing

A retained extractor request failed with HTTP 400 because Anthropic considered
its compiled output grammar too large. The schema contained 15 nullable unions;
being below the documented 16-union limit did not establish acceptance. Anthropic
also documents interacting internal grammar limits. Token counting does not
compile the output grammar and cannot qualify its acceptance.

New live Anthropic stage requests retain the original clinical schema and record
`schema_transport=anthropic-shared-local-definitions-v1`. After the pinned SDK's
supported-schema conversion, the transport shares identical object/union schemas
through local `$defs` and `$ref`. Definitions include their complete annotations;
expanding references restores the converted schema exactly. Existing references,
reference scopes, and `allOf` schemas are left unchanged. Sharing is also skipped
when its reference overhead would enlarge the serialized schema.

For the failed extractor's exact schema and Anthropic SDK 0.125.0, compact UTF-8
schema serialization decreases from 19,385 to 13,823 bytes; physical `anyOf`
nodes decrease from 15 to 9. Offline tests prove expansion equality and SDK
reference preservation. This does not prove that Anthropic's compiler accepts
the result. No provider probe is part of this repair.

Prompts, clinical schemas, response parsing, source evidence, clinical checks,
cost accounting, output limits, timeouts, and zero SDK retries retain their
existing behavior. No retained attempt is replayed or released by this change.

Primary documentation:
[Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
(schema support, complexity limits, SDK conversion, and token counting).
