# Ordinary field relations — prepared, not clinically qualified

This change carries complete original field objects and complete source into a
versioned interpretation request. It permits useful ordinary answers for distinct
repeated questions, with original option identities and retained source evidence.
`QUILLMD_V3_FIELD_RELATIONS=0` remains the default. No provider, token-count,
payment, production-data, deployment, push or merge call was made.

## Original failures and preserved history

The first probe on `5fd062e1ef86f3d2bb7aa8ce1d36fd3979ffae8b` found:

* Original D03 has four `Other:` fields in different complete questions. The
  ordinary sentence `The patient reports that the headache usually feels like
  intermittent buzzing.` was supported by source validation but changed to
  conflict by repeated-label adoption. Its provider request omitted original
  context and option structure.
* A unique `Right knee` field accepted `The patient has left knee pain.` and a
  forced historical supported answer escaped the shared finalization reader.
  The existing batch suite recorded this as an expected failure.
* The useful same-side `The patient has right knee pain.` was held as a
  reference to its own question, while the wrong-side sentence escaped it.

Baseline source, complete inputs, output, first test failures and instrument
errors are retained in `rebuild/.runtime/ordinary-release/`. The initial WIP is
preserved at `693fd4e554b20734932ddd378909c850cce67508`, branch
`preserve/v1-ordinary-first-wip`. The working branch was rebased onto the frozen
batch integration `9f2bdad0`; its rebased WIP is
`6090c456bc271ace660673db7da0a9cd1a4a16e7`. No old worktree was changed.

## Request, adoption and shared review

`ordinary-field-relations-v1` is restricted to the exact native Sonnet 5 model
and the complete-source v3 contract. It cannot run simultaneously with the
older history-context contract. The compiler includes every original field
verbatim, including protected fields, full context, linked-question metadata,
source locators and source-bound author/attestation policies. The model receives
all source units and only the requested output field IDs. Nothing is truncated.

Every requested field returns complete source IDs, original option IDs and an
explicit relation for every source unit in supplied order: answer, qualifier,
independent, contrary or unresolved. Unknown, missing or duplicate references
refuse the response. An omitted qualifier, contrary/unresolved context or a
declared conflict holds the answer. Missing selections remain missing.

The server signs a record bound to the exact complete catalogue, source,
contexts, destination, original options and competing repeated-field outputs.
It derives answer text from original source units or original printed options;
the model cannot compose replacement text. Distinct repeated question contexts
can receive distinct ordinary source. Indistinguishable contexts, ambiguous
labelled source and the same statement assigned to competing repeated questions
remain held. Generation, page display, unchanged save and finalization use the
same record reader. Changed source, mapping, destination, text, evidence or flag
invalidates the record. Historical answers gain no new interpretation record.

Shared deterministic guards cover explicit side, source-printed patient
authorship, document-review attestation and event-relative destinations. Source
policies require their associated exact anchor (`source` or
`attestation_source`); both policies may apply to one field. Patient comments
require an explicitly attributed patient report. A clinical observation cannot
become the patient's words. Review attestation requires explicit completed
patient review or an opportunity to comment on the report. Negation, uncertainty,
future review and general procedure facts cannot assert it.

## Two counterexamples found during implementation

The first prepared schema accepted a deliberately wrong model response that
selected `Yes` for `The patient does not smoke.` It also accepted the current
buzzing sentence when assigned solely to the pre-headache `Other:` destination.
These are developer-owned defects, preserved in `semantic-limit-first.json`;
default-off status did not discharge them.

The bounded repair adds two reusable checks:

* Binary Yes/No, True/False and Present/Absent options need a complete explicit
  matching patient predicate and compatible polarity. Regular inflections and
  agent nouns match without a topic/synonym guess. Qualified or unknown clauses
  remain held; an opposing explicit predicate anywhere in complete source
  vetoes a contradictory option. Exact own-labelled options remain valid.
* A question explicitly asking before/after an event needs that same relation
  and event in the retained source. Missing time is ambiguous; an opposite time
  is held. Current headache sensation remains useful for its ordinary question,
  and an explicit pre-headache statement is a separate useful positive.

This is bounded entailment, not a universal clinical ontology. In particular,
the older syntax reader still holds the short positive `The patient smokes.`;
`The patient does smoke.` supplies the tested affirmative predicate. The first
failed positive remains in `semantic-repair-first.log` and
`semantic-repair-second.log`; it was not reclassified as an unsafe source.

## Batch and financial boundary

The single and batch paths use one actual SDK keyword-argument compiler. Each
child keeps the same complete source, catalogue, protected context and qualified
form constraints. Only requested output IDs differ. Deterministic partitions
preserve physical source groups, at most 100 fields and 256 field×source-unit
relations per child, at most eight children, and at most 512,000 serialized
request bytes. A conservative closed-response byte bound must fit the exact
profile's output-token cap. Indivisible over-limit groups or a form needing more
than eight children are refused before reservation or provider use.

Response capacity can require batches even below 100 fields. Quote and enqueue
use that same decision. Every child's reserve is priced from its actual compiled
request bytes plus the existing overhead, exact profile output cap, configured
rates, geography multiplier and existing charge multiplier. All child holds
precede the first send. The existing immutable ledger, complete-result adoption,
unknown-outcome hold, cancellation and no-automatic-retry rules remain in force.
Unknown form-wide constraints still refuse batch admission.

With the new flag absent, legacy single-request configurations, prices and SDK
requests for Sonnet 5 and 4.6, plus stored batch v1 and v2 request reconstruction,
were compared byte-for-byte against frozen 9f. Both serialized probe files have
SHA256 `81e1209b719eee4c1dbb61a84a5d52db87cc4c00fdb37f6ae7b607433c3bd149`.
This is a bounded legacy-byte comparison, not a claim about every old payload.

## Workflow evidence and remaining gates

The original D03 blank questionnaire was uploaded and confirmed through the
authenticated application. A mocked SDK response passed through the real worker,
validation, adoption, review, unchanged answer save, finalization and authenticated
download. The target full sentence stayed `supported`; all other areas were
explicitly reviewed blank. No answer correction or checkbox invention was used.
The exported bytes matched the stored export hash and the original bytes stayed
unchanged. A user outside the department was refused export. Synthetic same-side
and ordinary negative-predicate option workflows exercise the same path.

Testing uses a fresh dedicated PostgreSQL container
`v1-ordinary-release-pg-20260928`, ID prefix `de4eac17185c`, empty tmpfs database,
synthetic credentials, no published port. Tests create and drop only their own
`test_ordinary_release` database in this container. Existing databases and
containers are not test targets. SDK calls are mocked and external Python socket
connections are denied in workflow tests. Synthetic accounting records have
positive charges from simulated receipts to exercise real ledger invariants;
they represent no external spend.

The prior 26/77 ordinary-selection baseline is not replaced by this preparation.
Full ordinary clinical usefulness, the remaining genuine ambiguities, complete
native Sonnet 5 qualification, source-complete temporal/role interpretation beyond
these bounded checks, model/profile eligibility, and independent finished-diff
refutation remain release gates. Neither passing mocks nor a complete closed
relation matrix proves that an arbitrary model context classification is true.
Activating the flag requires those gates and a priced authorization for actual
provider work; this report grants neither.
