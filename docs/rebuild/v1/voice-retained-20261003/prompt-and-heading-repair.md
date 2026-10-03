# Retained voice selection and exact own-heading repair

This is an offline engineering repair. It does not qualify the live provider,
correct transcription, or establish successful voice-to-form use.

The original Sonnet 5.5 results from terminal campaign
`v1-standing-api-testing-20261003`, attempts 003 and 005, remain unchanged.
Their synthetic raw notes, actual inspected mapping, raw response text, review
scope and first answer outcomes are retained in `raw-asr-response-fixtures.json`.
Offline tests use a separately derived local synthetic signed context proof;
they neither read nor reproduce the original protected signing key.

## Concrete causes and bounded repair

Attempt 005 returned Procedure, Anesthesia and Bowel preparation score source
headings as qualifiers but omitted their IDs from `unit_ids`. The existing
reader refused those selections before source governance. The application
prompt now explicitly requires the exact ordered union of answer and qualifier
IDs, with a two-unit example. It distinguishes an exact bare destination name
from headings containing clinical qualifications. The schema, partition and
unselected-qualifier refusal remain unchanged: the application does not repair
a provider response or silently adopt a missing qualifier.

A separate fixed source, `Assessment. The patient has a left ankle sprain.`,
produced a valid full selection but was then held because the question name
coupled the whole block to itself. The same patient statement without that
heading, or with a colon heading, was supported. An exact single bare heading
now discharges this question-name reference only when its own selected adjacent
complete statement already has established source evidence. It supplies no
actor, diagnosis, clinical qualifier or source words. Foreign actors, pronouns,
other destination boundaries, clinically modified headings and unresolved
qualifiers retain their guards. Review and finalization revalidate this proof.

## Verification and unchanged limits

Nine focused methods passed in 10.495 seconds. The affected 43-method packet
passed in 18.508 seconds, both with actual exit 0 and network/database connections
forbidden by the wrapper. It covers the actual 15 retained outcomes, full headed
patient answers, a complete selected clinical qualifier, omitted qualifiers,
source scope, actor, uncertainty, hypothetical findings, contradictions,
corrections, options, partition/parser and field-record vetoes. Held controls
also force a stale supported copy through page and finalization governance.

The first three positive-control failures from an incomplete helper are
preserved. A later added expectation that faithfully quoted `may have` must
hold was withdrawn after comparison with frozen 1aeb81bb: both no-heading and
colon-heading versions already preserved that exact uncertainty as useful free
text. All six baseline/candidate hypothetical IF controls remain held. The
original failed expectation and complete before/after outputs remain retained;
no unsafe clinical answer was demonstrated by the faithful uncertainty text.

Correcting only the selected-ID union in the retained provider wire leaves
attempt 003 at one useful answer of four and attempt 005 at one of eleven.
Making the three exact bare headings independent also leaves those counts
unchanged. These are explicitly modified offline wires, not new provider
outcomes or upgraded original results. Remaining source-ownership/completeness
floors need separate diagnosis. In particular, this patch does not qualify the
clear procedure facts currently held by that reader.

Raw 003 includes `strain` and `eyes wrapped` where the original synthetic audio
script says `sprain` and `ice wrapped`, plus malformed pain-correction wording.
These require explicit human transcript review; the audio script is not a
substitute source. Raw 005 scope wording is unintelligible, and blood-loss
`zero milliliters` versus `less than one milliliter` remains ambiguous. C08 is
still held. No original transcript, campaign declaration or paid send is edited.

## Evidence

Protected scratch root:
`/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/clinical/voice-retained-003-005`.
`prompt-heading-evidence-manifest.json` records exact bytes and SHA-256 hashes
for first instrument/helper failures, unchanged replay, reader return traces,
coupling proof, focused/affected gates, uncertainty baseline and complete-union
counterfactuals. The affected gate log SHA-256 is
`84d9a051aa7b286d028a856e854507aa03ada3880d12f484adf574c04393f175`;
the 15-outcome retained fixture SHA-256 is
`3fb96e40b7d0a7d7f285dddd7b0b2fb0b115de010efccfc0bc20f15d0c428150`.

Provider calls and database calls: zero. Finished-diff independent refutation,
coherent-candidate CI and prospective live qualification remain separate gates.
