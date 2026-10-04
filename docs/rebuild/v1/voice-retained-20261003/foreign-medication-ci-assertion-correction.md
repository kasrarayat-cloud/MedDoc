# Foreign medication ownership CI assertion correction

Exact CI run 37158506012 retained four subtest failures: two source orders,
under the explicit Sonnet 5 relations switch and the Sonnet 5.5 default.
`The patient takes warfarin 5 mg daily.` was faithfully supported beside
`Her husband switched to apixaban.`. The old blanket assertion expected that
foreign person's own switch to end the patient's medication, which contradicts
the independently established source-owner separation. It does not demonstrate
an unsafe patient answer. Original official logs and all 95 failure blocks stay
unchanged under the protected clinical CI scratch.

The narrow test correction separates that survivor from patient/ambiguous-agent
changes. It strengthens both source orders with active/passive husband switches,
including explicitly named warfarin, and refuses using the husband's own source
as the patient's medication. Explicit patient, personal-pronoun, clinician-agent,
subjectless switch, named replacement and cessation controls still hold through
the whole wire, stale-supported page and finalization readers. No application
source, safety floor, frozen corpus or original failure denominator is changed.

Before correction, the exact two affected methods reproduced four failures in
12.211 seconds, actual exit 1. After correction, those methods and the two model
variants of the stronger ownership control passed: four methods in 20.423
seconds, actual exit 0. Database/network calls were forbidden; provider calls
were zero. Logs are `clinical/ci-run-37158506012/clinical-cost/`
`husband-assertions-d3ce-first.log` and `husband-assertions-corrected-first.log`
under the existing storage-resume scratch. The retained 28-case actor packet and
its first outputs remain separate evidence; this is a CI test correction.
