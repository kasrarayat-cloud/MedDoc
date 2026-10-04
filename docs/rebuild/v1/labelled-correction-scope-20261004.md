# Bounded labelled correction and explicit prior patient assertion

On frozen candidate `7907ae5aa38c2a6c9e27eab1b09a758df315125b`, actual Oct4 attempts 26 and 27 unnecessarily held the unchanged Chief complaint `Patient presents with a rash on both forearms.`. Their later Allergy correction has an explicit labelled antecedent: `Allergies: penicillin. Sorry, I mean amoxicillin.`, or the same repair on the next nonblank line. The complete retained provider wires select the rash and classify the correction independently; its ordinary relation is valid. The old `v3_relation_corrections` filter nevertheless held every assertion preceding a bare repair.

The source change uses the existing closed bare-repair grammar and existing topic/key independence proof. An earlier assertion may be apart only if its complete ordinary relation is valid, every selected source explicitly names the patient, and the established backward-reference/invalidation guard finds none. It supplies no actor from a pronoun, heading, family line or correction. It changes no words, units, destinations, model settings or wire contract. Same-topic/shared-word repairs, global corrections, wrong-patient remarks, uncertainty, prior invalidation, missing qualifiers and absent ordinary relations remain held. The original C08 ambiguity is untouched.

The two retained whole provider responses and actual physical field mappings are pinned in `core/tests/labelled_correction_first_pass_controls.json`, with hashes of the original request, response, notes, mapping and first adopted answers. The new replay changes only the desired-positive rash: all other original statuses remain unchanged, Allergy remains conflict and Smoker stays supported. The answer, current review reading and finalization decision reader agree; these are pure replay controls, not another provider send or persisted HTTP workflow. These cases are exposed historical controls, not holdout cases.

The existing historical `BareBackwardRepair` selector now expects the correct prior rash in the exact N11/N12 sources, while retaining its unbounded/forward/same-topic negatives. The former two blanket-before expectation failures are preserved in `labelled-correction-scope-first.log` rather than erased. The distinct new source packet passes its three methods, including eighteen finite safety/control inputs. The corrected affected packet passes seven methods in 14.752 seconds, actual exit 0, including repeated repaired-value and medication-change controls. Network and database connections were blocked. A larger initial packet was bounded at 100 seconds and exited 124 before completion; it also included one mistaken class selector. It is partial evidence and is not cited as a passed gate.

All raw logs are retained under `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/clinical/voice-retained-003-005/`:

- `labelled-correction-scope-first.log`: first focused result, four methods with two obsolete prior-rash expectation failures; exit 1.
- `labelled-correction-scope-second.log`: new three-method finite controls, 4.806 seconds; exit 0.
- `labelled-correction-affected-first.log`: incomplete broader packet, exit 124; no full gate claim.
- `labelled-correction-affected-second.log`: finished seven-method affected gate, 14.752 seconds; exit 0.

This is a finished bounded repair for independent refutation. It does not claim the remaining N01, N04 or procedure overholds are fixed, does not reopen the closed campaign and provides no real-patient release approval.
