# Independent refutation of semantic checker binding

Finished clinical-generation diff, 2026-10-11 UTC. Verdict: **NOTHING FOUND**.
The independent agent was instructed to refute the claims with concrete inputs
and wrong outputs. It did not author the clinical change. This result does not
claim installation or public browser verification.

Frozen source SHA-256: `5340965f12d72b3ee4e07ef1dd72ae243ea88aeb7d5ea4cc989a63113620b31e`.
Frozen tests SHA-256: `2b676945d805ab54676986943292735dec886fd95cd4e0864b742e2b27276787`.
Base: `b521c6afb7e7f6726034ef0d78107be6ccbf6e6b`.

The refuter verified all 29 production function/class ASTs and all top-level
nodes outside `CHECK_SCHEMA` and `CHECK_INSTRUCTIONS` are identical to the base.
Removing only descriptions from the checker schema recovers the old schema.
Fact, API fact, assignment, source-reference and string schemas, plus extractor
and assigner instructions, are unchanged. The parent independently repeated
the production AST comparison and ran all 65 semantic-generation tests: PASS.

The refuter independently ran the six added tests: six PASS. They cover the
actual retained CRLF SOAP source and selected `f1,f3,f4` versus passing
`f1,f2,f3,f4`, contextual extra/substituted/omitted IDs, order-insensitive exact
binding with negation retained, a mismatched second check after targeted repair,
invented/duplicate IDs and the checker API contract. Additional independent
added/substituted/removed-ID probes held the original candidate and selected
IDs. Reversing the exact set passed without discarding negation. A selected
bad-fact finding still held. The three-call path and existing five-call repair
bound remain unchanged; a passing-ID mismatch does not trigger paid repair.

These controls preserve the strict evidence binding rather than adopting a
checker-expanded selection. The actual retained SOAP provider response and
accounting are preserved; its candidate was clinically correct but was held by
the existing exact-ID gate. Read-only diagnostic SHA-256:
`38165d5dcb6de1df15e37ec5fd402ee011e86d017ec4e6877b4d320089037f05`.
No provider, production database, credential or native service action occurred
during the independent clinical refutation. Public verification remains a
separate prospective action under the standing synthetic-testing authority.
