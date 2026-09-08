/**
 * GATE — #288: THE VALIDATOR HOLDS NO SECOND COPY OF THE OMIT DECISION.
 * ----------------------------------------------------------------------------
 * ⚠️ THE NINTH MIRROR, FOUND BY ROUND NINE AFTER EIGHT ROUNDS HAD CLOSED EIGHT.
 * `validation/index.ts` carried three of `requiresClinicianInput`'s five clauses
 * inline — dropping `field.unknownPolicy` and `mapping.blankPolicy` — and applied
 * them to a `not_mentioned` the ladder had produced for the OPPOSITE reason.
 *
 * ⚠️ AND IT WITHHELD THE DOCTOR'S OWN FORM. The two ladder rows that return
 * `not_mentioned` without consulting the predicate — `manual_source_not_filled`
 * and `awaiting_note_selection` — exist because blocking on them "refused the
 * native document on every visit, forever, and the export fell back to the
 * styled path". The partial copy re-decided the same question and emitted
 * `REQUIRED_FIELD_NOT_MENTIONED` at BLOCKING on exactly those rows, so
 * `validation.valid` went false and `fill-engine.ts:198` returned `render: null`.
 *
 * ⚠️ IT SURVIVED NINE ROUNDS BECAUSE NOTHING NAMED IT. Measured before the fix:
 * `grep -rn REQUIRED_FIELD_NOT_MENTIONED src --include=*.ts` returned exactly ONE
 * line — the emission itself. The omit-door gate could not see it either: the
 * biconditional compares the offer against `resolveOne`'s reasonCode and never
 * calls `validateTemplateTwin`.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { field, mapping, factFor } from './resolver-probe';
import { resolveTemplateFields } from '../resolver';
import { validateTemplateTwin } from '../validation';
import { fieldDemandsInput } from '../ir';

const SRC = join(__dirname, '..', 'validation', 'index.ts');

/** Drive the REAL resolver and the REAL validator over one field. */
function run(fieldOverrides = {}, mappingOverrides = {}) {
  const f = field('1', fieldOverrides);
  const m = mapping(f, 'ros.cardiovascular', mappingOverrides);
  const facts = [factFor('2', 'chief_complaint', 'Patient here for a rash.')];
  const resolutions = resolveTemplateFields({
    fields: [f], mappings: [m], facts, allowUncertifiedForSyntheticTest: true,
  });
  const validation = validateTemplateTwin({
    fields: [f], mappings: [m], facts, resolutions,
    allowUncertifiedForSyntheticTest: true,
  });
  return { f, m, resolution: resolutions[0]!, validation };
}

describe('#288 — the validator calls the shared predicate', () => {
  it.each([
    ['manual_source_not_filled', { sourceType: 'manual' as const }],
    ['awaiting_note_selection', { sourceType: 'verified_note_selection' as const }],
  ])(
    '⚠️ a REQUIRED %s field is NOT blocked — the document still renders',
    (expectedReason, mappingOverrides) => {
      const { resolution, validation } = run({}, { ...mappingOverrides, required: true });

      // REACHABILITY CONTROL: the input must actually exit at the ladder row
      // this arm is about, or the assertion below is about some other field.
      expect(
        resolution.reasonCode,
        'the input did not reach the ladder row this arm names',
      ).toBe(expectedReason);
      expect(resolution.status).toBe('not_mentioned');

      const blocking = validation.issues.filter((i) => i.severity === 'blocking');
      expect(
        blocking.map((i) => i.code),
        'the validator blocked a field the ladder deliberately left blank — the ' +
          "doctor's own form is withheld on every visit, which is exactly what " +
          'that ladder row exists to prevent',
      ).not.toContain('REQUIRED_FIELD_NOT_MENTIONED');
      expect(validation.valid, 'the document is withheld').toBe(true);
    },
  );

  it('POSITIVE CONTROL — the code STILL fires where it should', () => {
    // ⚠️ WITHOUT THIS, THE FIX COULD BE "NEVER EMIT THE CODE" AND BOTH ARMS
    // ABOVE WOULD PASS FOR THE WRONG REASON.
    //
    // ⚠️ AND THE INPUT HAS TO BE HAND-BUILT, WHICH IS ITSELF THE POINT. The
    // resolver can never produce it: `missingResolution` returns
    // `requiresInput ? 'needs_clinician_input' : 'not_mentioned'`, so a field
    // that requires input never exits as `not_mentioned`. The validator takes
    // `resolutions` as an INPUT, and an inconsistent one — not_mentioned for a
    // field that requires input, under a reason that is NOT a designed blank —
    // is precisely what this issue exists to catch.
    const f = field('1', { required: true });
    const m = mapping(f, 'ros.cardiovascular');
    const facts = [factFor('2', 'chief_complaint', 'Patient here for a rash.')];
    expect(fieldDemandsInput(f, m), 'the fixture does not demand input').toBe(true);

    const validation = validateTemplateTwin({
      fields: [f], mappings: [m], facts,
      resolutions: [{
        fieldId: f.fieldId, status: 'not_mentioned', value: null,
        sourceFactIds: [], evidenceAnchorIds: [], reasonCode: 'fact_not_mentioned',
        selectedOptionOrdinal: null, clinicianReviewed: false,
      }],
      allowUncertifiedForSyntheticTest: true,
    });
    expect(
      validation.issues.map((i) => i.code),
      'the fix silenced the code entirely',
    ).toContain('REQUIRED_FIELD_NOT_MENTIONED');
  });

  it('⚠️ CLASS CLOSURE — the validator restates no clause of the shared predicate', () => {
    // #288 closes the CLASS, not the instance. The partial copy is gone; this
    // arm reds if any of the five clauses is written out again here.
    const code = readFileSync(SRC, 'utf8')
      .split('\n')
      .filter((l) => !l.trimStart().startsWith('//') && !l.trimStart().startsWith('*'))
      .join('\n');

    // ⚠️ THE BAN IS ON THE CONJUNCTION, NOT ON THE TOKENS — and the first
    // version of this arm got that wrong and red on shipped, correct code.
    // `field.required` and `mapping.required` are read legitimately at :572 and
    // :588 to choose the SEVERITY of `FIELD_AMBIGUOUS`, which is a different
    // rule about a different question. Banning the token would force that rule
    // to launder itself, which is worse than the mirror.
    //
    // What must never return is the PARTIAL RESTATEMENT of the omit decision:
    // requiredness clauses OR'd together as the condition for
    // REQUIRED_FIELD_NOT_MENTIONED.
    // ⚠️ #275 ALREADY CLOSED THE THREE-CLAUSE COPY ON `main`; this keeps it shut.
    const PARTIAL_COPY =
      /field\.required\s*\|\|\s*mapping\.required\s*\|\|\s*mapping\.unknownPolicy/;
    expect(
      PARTIAL_COPY.test(code),
      'validation/index.ts restates the requiredness disjunction — that is the ' +
        'ninth mirror returning. Call requiresClinicianInput instead.',
    ).toBe(false);
    expect(code, 'the validator no longer calls the shared predicate').toContain(
      'fieldDemandsInput(field, mapping)',
    );
    expect(
      code,
      'the validator no longer defers to the ladder, so it will block a designed blank again',
    ).toContain('DESIGNED_BLANK_REASONS');
  });

  it('⚠️ CLASS CLOSURE — every BLOCKING code has exactly one emission site', () => {
    // A second `add(CODE, 'blocking', …)` for the same code is a second place
    // the decision is made, which is the shape this whole arc exists to end.
    const code = readFileSync(SRC, 'utf8');
    const emissions = new Map<string, number>();
    for (const m of code.matchAll(/add\(\s*'([A-Z_]+)'\s*,\s*'blocking'/g)) {
      emissions.set(m[1]!, (emissions.get(m[1]!) ?? 0) + 1);
    }
    // NON-VACUITY: the scan must find the emissions at all.
    expect(emissions.size, 'no blocking emissions found — this arm is vacuous').toBeGreaterThan(3);
    const duplicated = [...emissions].filter(([, n]) => n > 1).map(([c, n]) => `${c} x${n}`);
    expect(
      duplicated,
      'a blocking code is emitted from more than one site; each is a separate ' +
        'reader of the same rule and they will drift',
    ).toEqual([]);
  });
});

describe('#258/#270 — the input predicate has ONE body, and the leaf stays a leaf', () => {
  const read = (rel: string) =>
    readFileSync(join(__dirname, '..', rel), 'utf8')
      .split('\n')
      .filter((l) => !l.trimStart().startsWith('//') && !l.trimStart().startsWith('*'))
      .join('\n');

  it('⚠️ `fieldDemandsInput` DELEGATES — it does not restate the five disjuncts', () => {
    // ⚠️ THE REFUTATION PASS FOUND THIS AS A FALSE CLAIM, NOT A FALSE BEHAVIOUR.
    // `unmentioned-policy.ts` said "the resolver imports this function; there is
    // no second copy to fall out of step" while `resolver/index.ts` imported it
    // ZERO times and called `ir.ts::fieldDemandsInput`, a byte-identical second
    // statement. Identical bodies meant the behaviour was right and the
    // invariant was not established.
    const ir = read('ir.ts');
    const body = ir.slice(ir.indexOf('export function fieldDemandsInput'));
    const decl = body.slice(0, body.indexOf('\n}'));
    expect(decl, 'fieldDemandsInput does not delegate').toContain(
      'return requiresClinicianInput(field, mapping)',
    );
    // and it must not carry the disjuncts itself
    for (const token of ["unknownPolicy === 'requires_input'", "blankPolicy === 'requires_input'"]) {
      expect(decl, `fieldDemandsInput restates \`${token}\``).not.toContain(token);
    }
    // NON-VACUITY: the one body still exists, in the module that owns it.
    expect(read('unmentioned-policy.ts')).toContain("blankPolicy === 'requires_input'");
  });

  it('⚠️ AND THE FIX DID NOT RE-CREATE THE BUNDLE DEFECT — no value import of `ir`', () => {
    // The obvious repair is to move the body to `ir.ts` and import it here.
    // That is FORBIDDEN and measured: `unmentioned-policy.ts` is client-imported
    // and a value import from `ir.ts` puts 320,991 bytes of zod into the client
    // bundle (429x), which this module's own header records. The delegation
    // therefore runs ir -> policy, never policy -> ir.
    const policy = read('unmentioned-policy.ts');
    const irImports = [...policy.matchAll(/^import\s+(type\s+)?\{[^}]*\}\s+from\s+'\.\/ir';/gm)];
    expect(irImports.length, 'no ./ir import at all — this arm is vacuous').toBeGreaterThan(0);
    for (const m of irImports) {
      expect(
        m[1],
        `a VALUE import from ./ir: ${m[0].slice(0, 70)} — that is the 429x bundle regression`,
      ).toBeTruthy();
    }
  });
});
