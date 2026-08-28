# A REFUSAL CAUSED BY MY OWN SUBSTITUTION IS EVIDENCE ABOUT MY SUBSTITUTION

**Standing 2026-08-28. Caught mid-report, one sentence before it would have
become an owner-class finding about a customer's document.**

> **When you supply an input to reach a code path, every result downstream of
> that input is a fact about YOUR INPUT until you re-establish it on evidence
> the substitution cannot touch.**

## The case

The R5 walk needed the certification engine to get past its mappings-readiness
gate, which refuses any non-manual field carrying no `clinicalConcept`. QA
cannot reach a model, so the concept the note-selection step would propose was
**substituted** — the same move the QA walk's leg 2 makes, and it was said out
loud at the time:

    UPDATE template_twin_semantic_mappings SET "clinicalConcept" = 'exam.vascular'
     WHERE ... "clinicalConcept" IS NULL AND "sourceType" <> 'manual';   -- UPDATE 35

The certify job then ran production code and refused:

    status=proof_failed confirmed=35 reason=ENCOUNTER_NOT_DERIVABLE:no_measurement_rows

That was read as a finding about the owner's form: *his GI consult carries no
measurement rows, so it cannot certify.* The conclusion happened to be true.
**The evidence for it was manufactured.**

`verification-encounter.ts:272-275` counts a measurement row by testing
`clinicalConcept.startsWith('measurement.')`. The substitution had set **all 35**
mappings to `exam.vascular`. `measurementRows` was therefore **forced to zero by
the UPDATE**, and the refusal that followed was the engine correctly describing
the input it was handed. Any form — venous, imaging, operative — would have
produced the identical refusal under that substitution.

## Why it nearly shipped

⚠️ **BECAUSE THE WRONG EVIDENCE AGREED WITH THE RIGHT ANSWER.** A GI consult
genuinely has no measurement rows, so the prediction and the artifact matched,
and a matching result is the one nobody re-examines. This is
[the most dangerous wrong number is the one the prediction
expects](65-the-most-dangerous-wrong-number-is-the-one-expected.md) arriving
through a new door: there the instrument was stale, here the instrument was
perfect and the UNIVERSE was one I had authored.

⚠️ **AND THE SUBSTITUTION WAS DECLARED, WHICH IS WHAT MADE IT INVISIBLE.**
Saying *"this is substituted, and said out loud"* discharges the honesty duty
and creates the illusion that the duty is finished. It is not: a declared
substitution still propagates into every number downstream, and the declaration
does nothing to stop a later reading from treating those numbers as
measurements of the subject. **Declaring an input is not controlling for it.**

## The practice

- **Before reporting any refusal, ask which of its inputs YOU supplied.** If the
  answer is "the one the refusal names", it is not yet a finding.
- **Re-establish on evidence the substitution cannot touch.** Here that was the
  form's own 35 field labels — `Age`, `Referring MD`, `Allergies`, `Family
  History`, `Impression`, `Plan`, HPI narrative — read straight from
  `template_twin_field_definitions`. Those are properties of the uploaded
  document; no `UPDATE` of mine authored them.
- **Say which half survived.** The corrected claim is *"his form's LABEL SET
  contains no clinical measurement"*, plus the engine's own recorded scope
  (`verification-encounter.ts:236` — *"a non-venous template ... now cannot
  certify at all"*). What is NOT claimed, and was not measured, is what concepts
  a live model proposes in production.

⚠️ **THE ASYMMETRY THAT MAKES THIS WORTH A RULE:** a substitution that causes a
**refusal** looks like a discovery, and a substitution that causes a **pass**
looks like success. Both are self-portraits. The refusal is the more dangerous
of the two only because it arrives wearing the costume of rigour — you went
looking for a problem and found one, which feels like the process working.

**Sibling entries:** [a well-chosen fixture disguises a wrong
universe](09-a-well-chosen-fixture-disguises-a-wrong-universe.md) — there the
fixture was somebody else's and the universe was wrong by inheritance; here the
universe was wrong by authorship, which is harder to see because you remember
building it and remember it being reasonable.
