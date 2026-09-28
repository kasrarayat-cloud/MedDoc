# Explicit patient copular complements — 2026-09-28

The unchanged D31 MAPPA source was held by the ordinary reader despite an exact affirmative full-question match. This bounded repair retains the complete statement and original evidence under the existing signed field-relation contract. Parent independent refutation and the actual D31 application route remain pending at this freeze.

Base: `fba37e2fec9df86bee18b31798c22e44014be3c3`. Isolated branch: `fix/v1-patient-copular`. No provider, installed data, database, deployment, or network access was used by these probes.

## Verified cause and scope

The pinned parser reads “The patient is subject to Multi-Agency Public Protection Arrangements (MAPPA).” as finite `is`, explicit subject `patient`, adjective complement `subject`, and nominal preposition `to`; it does not parse a passive. The generic patient reader marks `to` unsettled, the sentence fallback declines an existing finite verb, and the literal entity reader excluded the patient. All three prerequisites were therefore false despite the intact source.

`core/v3_literal_facts.py:96` now recognizes one explicit patient subject, one finite copula, one adjectival complement, and one complete nominal prepositional object. Any otherwise-unsettled `to` must be the actual parsed nominal preposition. The global unsettled-word list and legacy contract are unchanged. Nested predicates, foreign or ambiguous subjects, modal/hypothetical statements, uncertainty, incomplete complements, and additional unowned syntax gain no allowance. The entire source, including explicit negation and acronym, remains in free text. This helper does not grant an option choice or bypass destination, source-policy, context, signature, or stored-answer checks.

The product delta is confined to this helper and its call from `_simple_fact`. Request/profile/rate/compiler/reservation/dispatch and scanner source are byte-identical to the base; `manifest.json` records their identities. No scanner pin was refreshed.

## Evidence

- Original actual D31 mapping and response bytes replayed unchanged: target `v3_48` changes from conflict/empty to supported/exact 78-character source; current stored governance retains the same text and has zero governed decisions. Runtime `final-witness.py` asserts this result.
- First baseline retained: three new test methods produced five failing subtests before the repair. Final 20 field-relation methods pass in 3.328s; 31 adjacent literal, syntax and history methods pass in 3.273s. Both runs skip the unused database.
- Positive controls include the original MAPPA statement, its explicit negative, responsive-to-physiotherapy affirmative/negative, and the pre-existing dependent-on-assistance control. Foreign actor, patient advocate, ambiguous pronoun, modal, hypothetical, apparent/possible status, unfinished object, omitted contrary/qualifier context, modified stored text and disabled contract are held.
- Original retained 15-note replay is unchanged: five-note subset 12/12; ten-note original selections 26/77. Zero answer status/text changes, and all stored projections agree. Original 77 and 12 inputs and the 34-valid/7-judgment/10-invalid remaining-selection classifications are preserved. This historical-contract result is not an evaluation score for a newly invented relation oracle.
- The separate pre-existing history-context fixture still supports exactly its five positive targets; the sixth, note 2 HPI, remains held. Original picks and relation fixture were unchanged.

Evidence directory: `rebuild/.runtime/patient-copular-20260928/`. The ignored runtime preserves original full inputs, first results, runnable socket/DB-denied probes, final results, and source/input hashes. The committed manifest and test logs record the finite tested scope. Parent must refute the finished diff, replay its saved original and bounded countercontrols, and run its actual D31 route before integration. Broader ordinary-note qualification and unresolved family work remain separate.
