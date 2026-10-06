# Supplemental voice score correction — 2026-10-03

The independently authored eleven-field voice form and per-audio form pin are
preserved. Commit `0532fb97226b2032463fcd7a57d3bdc1a436effa` corrects the
supplemental scorer's claim: matching words are literal reference matches and
cannot certify the subject, polarity, time, certainty, or correction meaning.
There is no application adoption-path change in this correction.

The retained first refutation of `8aea7b78` demonstrated two false correctness
scores. A family member's statement and a negated follow-up statement each
received one `correct_adopted_answers` count when their reference words appeared
in an affirmative answer. These are scoring defects, not demonstrated unsafe
application adoption. The first result and all historical campaign evidence
remain unchanged.

The replacement schema is `supplemental-literal-reference-v2`. It separately
reports available literal references, first-pass supported/unadopted/missing
answers, literal matches/mismatches, required hold shapes, and citation shapes.
`correct_answers`, `unsafe_answers`, and `unnecessarily_held_answers` are null
pending independent source adjudication. Clinician corrections receive zero
first-pass credit. Neither a required hold's shape nor a citation's valid shape
is called semantic accuracy.

Twelve isolated tests passed in 6.143 seconds, exit 0, without a database,
provider, or Internet connection. They cover the two original false-green
counterexamples, an ordinary literal positive, ignored clinician corrections,
the genuine eleven-destination form, per-audio pin enforcement, the final
request-ledger check, and unchanged historical manifest inputs. The lead's
finished-diff refutation is retained independently; this report does not
substitute for adjudicating a real transcription and first response.

The authored form SHA is
`1d2240c577e2472f25521e9c59fdb8d10ab109b514fc4aa043db095ee309fd8e`;
its manifest SHA is
`64fed2b82500f1bc9f8533eb28da27c75abfbacb3b2c91d6c7184846df6a3381`.
It has synthetic provider-upload rights and is supplemental evidence, excluded
from the frozen Word corpus qualification denominator.

Protected continuation evidence lives under
`rebuild/.runtime/v1-sol-continuation-20261002/word/`: the original
`refute-voice-fit-8aea/` artifacts and `refute-voice-fit-8aea-first.log`, plus
`voice-literal-tests-0532-first.log`. These include source witnesses and the
original failed scores. No paid request was made by this correction or its
verification.
