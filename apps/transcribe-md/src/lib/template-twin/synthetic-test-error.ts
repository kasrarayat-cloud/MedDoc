// ============================================================================
// The typed refusal the synthetic-test path throws.
// ----------------------------------------------------------------------------
// ⚠️ THIS LIVES IN ITS OWN LEAF MODULE ON PURPOSE. It used to sit in
// `synthetic-test.ts`, which imports prisma, storage, the fill engine and the
// docx parser — so importing the ERROR CLASS dragged the whole persistence
// chain in, and a unit test asserting nothing but the error's shape could not
// load. A pure value type that cannot be imported without a database is a
// contract nothing can guard.
//
// `synthetic-test.ts` re-exports it, so every existing importer is unchanged.
// ⚠️ New tests should import from HERE, not from the re-export — a grep that
// resolves a symbol through a barrel has not found its definition, and this
// file is the definition.
// ============================================================================

export class TemplateTwinSyntheticTestError extends Error {
  readonly code:
    | 'NOT_FOUND'
    | 'IMMUTABLE'
    | 'CONFLICT'
    | 'MAPPINGS_NOT_READY'
    | 'VALIDATION_FAILED'
    | 'SYNTHETIC_EVIDENCE_REJECTED'
    /** F5-i. No self-test could be GENERATED for this template's own shape, so
     *  nothing was run. ⚠️ Distinct from every code above, which report that a
     *  proof RAN and failed — conflating them would let "we never tested your
     *  form" read as "your form was tested". */
    | 'ENCOUNTER_NOT_DERIVABLE';

  /** For VALIDATION_FAILED: "<fieldId>:<issueCode>" per blocking check.
   *  For MAPPINGS_NOT_READY: "<fieldId>:<no_mapping|unconfirmed|no_concept>".
   *  For ENCOUNTER_NOT_DERIVABLE: the single EncounterNotDerivable reason.
   *  Ids and codes only — never encounter text or filled values. */
  readonly blocking: readonly string[];

  /** For MAPPINGS_NOT_READY: how many fields the compiled version has in
   *  total, so a caller can say "6 of 80" without re-querying.
   *
   *  ⚠️ NULL, NOT 0, WHEN UNSUPPLIED. Every other throw site constructs this
   *  error with no detail; defaulting to 0 would make them all silently claim
   *  "0 fields", which is a confident wrong number where null is an honest
   *  absence the caller can degrade on.
   *
   *  ⚠️ A COUNT, NEVER A LABEL. The template is the customer's own form and
   *  its field labels are theirs — this number and the opaque `fieldId`s in
   *  `blocking` are the ONLY things about it that may cross to a UI. */
  readonly totalFields: number | null;

  constructor(
    code: TemplateTwinSyntheticTestError['code'],
    message: string,
    detail?: { blocking?: readonly string[]; totalFields?: number },
  ) {
    super(message);
    this.name = 'TemplateTwinSyntheticTestError';
    this.code = code;
    this.blocking = detail?.blocking ?? [];
    this.totalFields = detail?.totalFields ?? null;
  }
}
