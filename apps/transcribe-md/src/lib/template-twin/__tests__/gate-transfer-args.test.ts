// ============================================================================
// THE TRANSFER TOOL'S ARGUMENTS AND GUARDS — proved without a database.
// ----------------------------------------------------------------------------
// `transfer-certification-to-active.ts` is a RULED MUTATION: it writes certified
// dispositions onto a live compiled version and the write has no inverse. Its
// source, target and expected field count were FILE CONSTANTS, so the tool
// could only ever act on the one row-pair its author had read.
//
// Ruling 2 (2026-09-07) makes them REQUIRED ARGUMENTS, because the 53-control
// consult form re-issue is a second act of the same shape.
//
// ⚠️ THIS FILE EXISTS BECAUSE PARAMETERISATION IS NOT A REFACTOR. Turning a
// constant into an argument does not preserve behaviour — it creates states the
// constant made unreachable, and the interesting ones fail in the direction
// that looks like success:
//
//   · `--expect-fields 0` -> every count guard reads 0 === 0 against an empty
//     field set and PASSES. Ten green guards, nothing transferred.
//   · `--source X --target X` -> a self-transfer, where each "identical" guard
//     passes BECAUSE it is one row rather than because two agree.
//   · two NULL shas -> `null === null` is true, so two rows that record nothing
//     about their structure agree perfectly about it.
//
// ⚠️ AND IT PROVES BOTH DIRECTIONS, WHICH IS THE POINT OF THE FILE.
// `retire-branch.sh` passed 9 of 9 REFUSAL tests and still printed a false
// green, because refusals were never its broken half. So every refusal arm here
// is paired with a POSITIVE CONTROL: the same input with the one bad thing
// fixed must PASS. A refusal that fires for the wrong reason and a refusal that
// fires for the right one are indistinguishable without it.
// ============================================================================
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it, vi } from 'vitest';

// ⚠️ HOISTED, AND THE ORDER MATTERS. `fromPersistedMapping` lives in
// `certification-lifecycle`, which transitively pulls `next-auth` and fails to
// resolve under this environment. `gate-217-concept-scope-persists` — the gate
// for the very symbol this file now depends on — solves it the same way, and
// copying its shape is deliberate: two gates over one function should not
// diverge in how they reach it.
vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { fromPersistedMapping } from '../certification-lifecycle';
import {
  buildTransferGuards,
  countFailedGuards,
  parseTransferArgs,
  selectTransferFieldIds,
  type TransferSide,
} from '../transfer-args';

/** Replace one flag's value in an argv, so each arm differs in exactly one place. */
function withArg(argv: string[], flag: string, value: string): string[] {
  const out = [...argv];
  const i = out.indexOf(flag);
  out[i + 1] = value;
  return out;
}

const OK = [
  '--source',
  'src-1',
  '--target',
  'tgt-1',
  '--expect-fields',
  '53',
  '--target-status',
  'draft',
  '--transfer-source-types',
  'extraction',
  '--expect-transfer',
  '43',
];

/** A pair of sides that agrees on everything, so a single mutation is the cause. */
function goodPair(n = 3): { source: TransferSide; target: TransferSide } {
  const ids = Array.from({ length: n }, (_, i) => `f${i}`);
  return {
    source: {
      fields: ids.map((fieldId) => ({ fieldId, mappingStatus: 'CERTIFIED' })),
      structureSha256: 'struct-aaa',
      staticContentSha256: 'static-bbb',
      templateStatus: 'inactive',
      doctorId: 'doc-1',
      practiceId: 'prac-1',
    },
    target: {
      fields: ids.map((fieldId) => ({
        fieldId,
        mappingStatus: 'NEEDS_CONFIRMATION',
      })),
      structureSha256: 'struct-aaa',
      staticContentSha256: 'static-bbb',
      templateStatus: 'active',
      doctorId: 'doc-1',
      practiceId: 'prac-1',
    },
  };
}

describe('parseTransferArgs — the happy path, first', () => {
  // ⚠️ THE POSITIVE CONTROL COMES FIRST DELIBERATELY. If this arm ever fails,
  // every refusal below is refusing something that was already broken, and the
  // suite would still be green on all of them.
  it('accepts the six required arguments and defaults to DRY RUN', () => {
    const r = parseTransferArgs(OK);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.args).toEqual({
      source: 'src-1',
      target: 'tgt-1',
      expectFields: 53,
      targetStatus: 'draft',
      transferSourceTypes: new Set(['extraction']),
      expectTransfer: 43,
      commit: false,
    });
  });

  it('takes --commit, in any position', () => {
    for (const argv of [
      [...OK, '--commit'],
      ['--commit', ...OK],
      [...OK.slice(0, 4), '--commit', ...OK.slice(4)],
    ]) {
      const r = parseTransferArgs(argv);
      expect(r.ok).toBe(true);
      if (r.ok) expect(r.args.commit).toBe(true);
    }
  });
});

const ALL_FLAGS = [
  '--source',
  '--target',
  '--expect-fields',
  '--target-status',
  '--transfer-source-types',
  '--expect-transfer',
];

describe('parseTransferArgs — refusals, each with its own positive control', () => {
  for (const flag of ALL_FLAGS) {
    it(`REFUSES when ${flag} is missing, and accepts the same argv with it`, () => {
      const without: string[] = [];
      for (let i = 0; i < OK.length; i += 2) {
        if (OK[i] !== flag) without.push(OK[i]!, OK[i + 1]!);
      }
      const bad = parseTransferArgs(without);
      expect(bad.ok).toBe(false);
      if (!bad.ok) {
        // ⚠️ THE ASSERTION IS ON THE `missing required argument(s):` LINE ALONE,
        // NOT ON THE WHOLE REASON — and that correction came from an adversarial
        // pass, which showed all six of these arms passing while the refusal
        // named the WRONG flag. `reason` embeds USAGE, and USAGE lists every
        // flag, so `reason.toContain('--expect-transfer')` was satisfied by the
        // usage line no matter what the parser actually complained about.
        // A test whose haystack contains every possible needle cannot fail.
        const line = bad.reason
          .split('\n')
          .find((l) => l.startsWith('missing required argument(s):'));
        expect(line, `no "missing required" line in: ${bad.reason}`).toBeDefined();

        // ⚠️ PARSED INTO A SET, NOT SUBSTRING-MATCHED — AND THE FIRST DRAFT OF
        // THIS ARM GOT IT WRONG. `--target` is a PREFIX of `--target-status`, so
        // "must not name --target" red-flagged a refusal that correctly named
        // only `--target-status`. A substring test over a flag vocabulary where
        // one name contains another answers a question nobody asked.
        const named = line!
          .replace('missing required argument(s):', '')
          .split(',')
          .map((x) => x.trim().replace(/\.$/, ''))
          .filter(Boolean);
        expect(named, `refusal named ${named.join('|')}, expected exactly ${flag}`).toEqual([flag]);
      }

      // the control: the ONLY difference is the restored flag
      expect(parseTransferArgs(OK).ok).toBe(true);
    });
  }

  it('REFUSES a flag whose value is another flag, naming the RIGHT flag', () => {
    const r = parseTransferArgs(['--source', ...OK.slice(2)]);
    expect(r.ok).toBe(false);
    // ⚠️ The failure mode being excluded: binding source='--target' and then
    // reporting "missing --target" — a refusal that sends the reader to fix an
    // argument that is not the broken one.
    if (!r.ok) {
      expect(r.reason).toContain('--source needs a value');
      expect(r.reason).not.toContain('missing required');
    }
  });

  it('REFUSES --expect-fields 0 — the guards would pass VACUOUSLY', () => {
    const r = parseTransferArgs(withArg(OK, '--expect-fields', '0'));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain('VACUOUSLY');

    // ⚠️ THE CONTROL THAT MAKES THIS ARM MEAN SOMETHING: prove the vacuous pass
    // is REAL, not hypothetical. An empty field set with expectFields=0 passes
    // every count guard — which is exactly why the parse refuses before here.
    const empty: TransferSide = {
      fields: [],
      structureSha256: 's',
      staticContentSha256: 't',
      templateStatus: 'active',
      doctorId: 'd',
      practiceId: 'p',
    };
    const vacuous = buildTransferGuards(empty, { ...empty }, 0);
    const countGuards = vacuous.slice(0, 4);
    expect(countFailedGuards(countGuards)).toBe(0); // <- the hazard, demonstrated
  });

  it('REFUSES source === target — a guard measuring itself', () => {
    const r = parseTransferArgs(
      withArg(withArg(OK, '--source', 'same'), '--target', 'same'),
    );
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain('same compiled version');

    // control: one character apart, and it parses
    expect(
      parseTransferArgs(
        withArg(withArg(OK, '--source', 'same'), '--target', 'sameX'),
      ).ok,
    ).toBe(true);
  });

  it('REFUSES a leniently-parsed count — parseInt would have accepted these', () => {
    for (const v of ['53x', '5.9', ' 53', '5 3', '0x35', '', '-1', '1e2']) {
      const r = parseTransferArgs(withArg(OK, '--expect-fields', v));
      expect(r.ok, `--expect-fields '${v}' must be refused`).toBe(false);
    }
    // ⚠️ AND THE CONTROL PROVES THE REFUSALS ARE ABOUT THE VALUE, NOT THE ARM:
    // the same argv with a clean integer parses.
    const good = parseTransferArgs(OK);
    expect(good.ok).toBe(true);
    if (good.ok) expect(good.args.expectFields).toBe(53);
  });

  it('applies the SAME strictness to --expect-transfer, which gates the partition', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE PASS SHOWED THE OTHER ONE PROVING HALF THE
    // CLAIM. `--expect-fields`'s strict parse was covered and
    // `--expect-transfer`'s was not — so it could be reduced to `parseInt` and
    // the suite stayed green. It is the one that matters more: it decides how
    // many CERTIFIED dispositions move.
    for (const v of ['43x', '4.9', ' 43', '1e1', '0x2b', '', '-1']) {
      const r = parseTransferArgs(withArg(OK, '--expect-transfer', v));
      expect(r.ok, `--expect-transfer '${v}' must be refused`).toBe(false);
    }
    const good = parseTransferArgs(withArg(OK, '--expect-transfer', '43'));
    expect(good.ok).toBe(true);
    if (good.ok) expect(good.args.expectTransfer).toBe(43);
  });

  it('REFUSES an unrecognised argument rather than ignoring it', () => {
    const r = parseTransferArgs([...OK, '--dry-run']);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("unrecognised argument '--dry-run'");
  });

  // ⚠️ EVERY FLAG, NOT TWO OF SIX. The pass found only `--target` and
  // `--transfer-source-types` covered — so deleting the duplicate check on
  // `--source`, the argument that names the CERTIFIED version, left the suite
  // green while the second value silently won.
  for (const flag of ALL_FLAGS) {
    it(`REFUSES a repeated ${flag} — the second value would silently win`, () => {
      const r = parseTransferArgs([...OK, flag, flag === '--expect-fields' ? '99' : 'x']);
      expect(r.ok).toBe(false);
      if (!r.ok) {
        expect(r.reason).toContain('more than once');
        expect(r.reason).toContain(flag);
      }
    });
  }

  it('REFUSES an empty argv, which is how the OLD constants-based call now arrives', () => {
    // ⚠️ THIS IS THE MIGRATION ARM. The previous invocation was
    // `… transfer-certification-to-active.ts --commit` and it acted on two
    // hardcoded ids. That exact command must now REFUSE rather than act on a
    // stale target — a silently-defaulted id is the whole hazard.
    const r = parseTransferArgs(['--commit']);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain('missing required argument(s)');
  });
});

describe('buildTransferGuards — the original ten still refuse what they refused', () => {
  it('passes on a well-formed pair (the positive control for every arm below)', () => {
    const { source, target } = goodPair(3);
    expect(countFailedGuards(buildTransferGuards(source, target, 3))).toBe(0);
  });

  it('fails when the expected count disagrees with reality', () => {
    const { source, target } = goodPair(3);
    expect(
      countFailedGuards(buildTransferGuards(source, target, 4)),
    ).toBeGreaterThan(0);
  });

  it('fails when the target already carries CERTIFIED mappings', () => {
    const { source, target } = goodPair(3);
    target.fields[0]!.mappingStatus = 'CERTIFIED';
    expect(
      countFailedGuards(buildTransferGuards(source, target, 3)),
    ).toBeGreaterThan(0);
  });

  it('fails when the fieldId sets differ', () => {
    const { source, target } = goodPair(3);
    target.fields[1]!.fieldId = 'other';
    expect(
      countFailedGuards(buildTransferGuards(source, target, 3)),
    ).toBeGreaterThan(0);
  });

  it('fails when the target template is not ACTIVE', () => {
    const { source, target } = goodPair(3);
    target.templateStatus = 'inactive';
    expect(
      countFailedGuards(buildTransferGuards(source, target, 3)),
    ).toBeGreaterThan(0);
  });

  for (const key of [
    'structureSha256',
    'staticContentSha256',
    'doctorId',
    'practiceId',
  ] as const) {
    it(`fails when ${key} DIFFERS between the two versions`, () => {
      const { source, target } = goodPair(3);
      target[key] = 'something-else';
      expect(
        countFailedGuards(buildTransferGuards(source, target, 3)),
      ).toBeGreaterThan(0);
    });
  }
});

describe('buildTransferGuards — the four ADDED guards, and the hole they close', () => {
  // ⚠️ EACH ARM DEMONSTRATES THE HOLE BEFORE ASSERTING IT IS CLOSED. Showing
  // that the equality guard passes on two nulls is what makes the presence
  // guard a fix rather than a decoration — without it, a reader cannot tell
  // whether the added guard is load-bearing or ceremonial.
  for (const key of [
    'structureSha256',
    'staticContentSha256',
    'doctorId',
    'practiceId',
  ] as const) {
    it(`REFUSES two NULL ${key}s, which the equality guard alone accepts`, () => {
      const { source, target } = goodPair(3);
      source[key] = null;
      target[key] = null;

      const guards = buildTransferGuards(source, target, 3);

      // ⚠️ STEP 1 NAMES *THIS KEY'S* GUARD, AND THE FIRST DRAFT DID NOT. It
      // searched with `n.includes('identical') || n.startsWith('same')`, which
      // resolves to "fieldId sets identical" — the one guard the very next
      // filter explicitly excluded, and never the column under test. So
      // `expect(equality).toBeDefined()` was a tautology, and the arm proved the
      // hole was real for a key it had not looked at. An adversarial pass found
      // it. Both steps now address the guard BY NAME rather than by counting.
      const NAME_OF = {
        structureSha256: 'structureSha256 identical',
        staticContentSha256: 'staticContentSha256 identical',
        doctorId: 'same owning doctor',
        practiceId: 'same practice',
      } as const;
      const PRESENT_OF = {
        structureSha256: 'structureSha256 PRESENT on both (not two nulls agreeing)',
        staticContentSha256: 'staticContentSha256 PRESENT on both (not two nulls agreeing)',
        doctorId: 'owning doctor PRESENT on both (not two nulls agreeing)',
        practiceId: 'practice PRESENT on both (not two nulls agreeing)',
      } as const;

      // 1. THE HOLE IS REAL: with both sides null, THIS key's equality guard
      //    reads `null === null` -> true, so alone it accepts two rows that
      //    record nothing about the property.
      const equality = guards.find(([n]) => n === NAME_OF[key]);
      expect(equality, `no guard named ${NAME_OF[key]}`).toBeDefined();
      expect(equality![1], `${NAME_OF[key]} should read true on two nulls`).toBe(true);
      expect(countFailedGuards([equality!])).toBe(0);

      // 2. AND THE ADDED GUARD CLOSES IT — this key's, not just any of the four.
      const presence = guards.filter(([n]) => n.includes('PRESENT'));
      expect(presence.length).toBe(4);
      const mine = guards.find(([n]) => n === PRESENT_OF[key]);
      expect(mine, `no PRESENT guard named ${PRESENT_OF[key]}`).toBeDefined();
      expect(countFailedGuards([mine!])).toBe(1);
    });
  }

  it('REFUSES an EMPTY-STRING sha, not only a null', () => {
    // '' === '' is true and '' is falsy — two different ways to be absent, and
    // a presence check written as a truthiness test would catch only the second.
    const { source, target } = goodPair(3);
    source.structureSha256 = '';
    target.structureSha256 = '';
    expect(
      countFailedGuards(buildTransferGuards(source, target, 3)),
    ).toBeGreaterThan(0);
  });

  it('does NOT fail a pair that carries real values — the net is wider, not looser', () => {
    // ⚠️ THE REGRESSION CONTROL FOR THE ADDED GUARDS. Four new ways to refuse is
    // only an improvement if nothing legitimate now refuses; a guard that fires
    // on good input is a worse defect than the one it was added to close.
    const { source, target } = goodPair(35);
    const guards = buildTransferGuards(source, target, 35);
    expect(guards.length).toBe(14); // 10 original + 4 added
    expect(countFailedGuards(guards)).toBe(0);
  });
});

describe('the SELECTION — "transfer the 43, re-propose the ten"', () => {
  /** A source shaped like the real certified 53: 43 extraction + 10 manual. */
  function certified53(): TransferSide {
    const fields = [
      ...Array.from({ length: 43 }, (_, i) => ({
        fieldId: `e${i}`,
        mappingStatus: 'CERTIFIED',
        sourceType: 'extraction',
      })),
      ...Array.from({ length: 10 }, (_, i) => ({
        fieldId: `m${i}`,
        mappingStatus: 'CERTIFIED',
        sourceType: 'manual',
      })),
    ];
    return {
      fields,
      structureSha256: 'struct',
      staticContentSha256: 'static',
      templateStatus: 'active',
      doctorId: 'doc',
      practiceId: 'prac',
    };
  }

  it('selects exactly the 43 extraction rows, measured against the real partition', () => {
    const src = certified53();
    expect(src.fields.length).toBe(53);
    expect(selectTransferFieldIds(src, new Set(['extraction']))).toHaveLength(
      43,
    );
    expect(selectTransferFieldIds(src, new Set(['manual']))).toHaveLength(10);
  });

  it("'all' selects every field — the GI act's mode, still expressible", () => {
    expect(selectTransferFieldIds(certified53(), null)).toHaveLength(53);
  });

  it('selects on the SOURCE, never the target — the target rows are the fresh proposals', () => {
    // ⚠️ THE FAILURE THIS EXCLUDES: selecting on the target picks whatever the
    // new registry happened to propose, which is a set nobody ever certified.
    // Here the target's types are deliberately the INVERSE of the source's.
    const src = certified53();
    const picked = selectTransferFieldIds(src, new Set(['extraction']));
    expect(picked.every((id) => id.startsWith('e'))).toBe(true);
    expect(picked.some((id) => id.startsWith('m'))).toBe(false);
  });

  it('a field with a NULL sourceType is never selected', () => {
    const src = certified53();
    src.fields[0]!.sourceType = null;
    expect(selectTransferFieldIds(src, new Set(['extraction']))).toHaveLength(
      42,
    );
  });

  it('the selection guard FIRES when the live partition is not what was declared', () => {
    const src = certified53();
    const tgt = { ...certified53(), templateStatus: 'draft' };
    const opts = {
      targetStatus: 'draft',
      transferSourceTypes: new Set(['extraction']),
      expectTransfer: 43,
    };
    // control: the declared 43 matches the shape, so the selection guard passes
    const sel = (g: Array<[string, unknown, unknown]>) =>
      g.filter(([n]) => n === 'fields selected for transfer');
    expect(
      countFailedGuards(sel(buildTransferGuards(src, tgt, 53, opts))),
    ).toBe(0);

    // and it reds when one row moves across the partition
    src.fields[0]!.sourceType = 'manual';
    expect(
      countFailedGuards(sel(buildTransferGuards(src, tgt, 53, opts))),
    ).toBe(1);
  });

  it('emits NO selection guard when no count was declared — never one that measures itself', () => {
    const src = certified53();
    const guards = buildTransferGuards(src, { ...certified53() }, 53);
    expect(
      guards.filter(([n]) => n === 'fields selected for transfer'),
    ).toHaveLength(0);
  });
});

describe('--target-status — guard 10 KEPT as a premise, parameterised as a value', () => {
  it('accepts draft, which is what the ruled order actually presents', () => {
    // ⚠️ THE REGRESSION THIS PINS: guard 10 read `status === 'active'` as a
    // literal, and #263 transfers BEFORE certify-and-activate. A freshly
    // ingested template is `draft` (create-draft.ts:436), so the literal
    // refused the very act it was being parameterised for.
    const { source, target } = goodPair(3);
    target.templateStatus = 'draft';
    expect(
      countFailedGuards(
        buildTransferGuards(source, target, 3, { targetStatus: 'draft' }),
      ),
    ).toBe(0);
  });

  it('still REFUSES a target in the wrong state — the premise is asserted, not dropped', () => {
    const { source, target } = goodPair(3);
    target.templateStatus = 'active';
    expect(
      countFailedGuards(
        buildTransferGuards(source, target, 3, { targetStatus: 'draft' }),
      ),
    ).toBeGreaterThan(0);
  });

  it('REFUSES a status outside the closed set — a typo is not a premise', () => {
    const r = parseTransferArgs(withArg(OK, '--target-status', 'activ'));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain('not one of');
    expect(parseTransferArgs(withArg(OK, '--target-status', 'active')).ok).toBe(
      true,
    );
  });

  it('defaults to active when no option object is passed — the pre-existing callers', () => {
    const { source, target } = goodPair(3);
    expect(countFailedGuards(buildTransferGuards(source, target, 3))).toBe(0);
  });
});

describe('--expect-transfer — the selector without a declared count is an unguarded query', () => {
  it('REFUSES 0', () => {
    const r = parseTransferArgs(withArg(OK, '--expect-transfer', '0'));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain('absence of one');
  });

  it('REFUSES a count larger than the field count', () => {
    const r = parseTransferArgs(withArg(OK, '--expect-transfer', '54'));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain('exceeds');
    // control: equal is legal — that is the "transfer everything" act
    expect(parseTransferArgs(withArg(OK, '--expect-transfer', '53')).ok).toBe(
      true,
    );
  });

  it('REFUSES a --transfer-source-types that names nothing', () => {
    for (const v of ['', ',', ' , ']) {
      expect(
        parseTransferArgs(withArg(OK, '--transfer-source-types', v)).ok,
      ).toBe(false);
    }
    expect(
      parseTransferArgs(withArg(OK, '--transfer-source-types', 'all')).ok,
    ).toBe(true);
  });

  it('takes a comma-separated list, trimming spaces', () => {
    const r = parseTransferArgs(
      withArg(OK, '--transfer-source-types', 'extraction, manual'),
    );
    expect(r.ok).toBe(true);
    if (r.ok)
      expect(r.args.transferSourceTypes).toEqual(
        new Set(['extraction', 'manual']),
      );
  });
});

describe('THE PAYLOAD IS PROJECTED, NEVER HAND-ROLLED — the column-drop class', () => {
  // ⚠️ THIS BLOCK EXISTS BECAUSE THE REFUTATION PASS FOUND A BLOCKING DEFECT
  // THAT EVERY OTHER ARM IN THIS FILE MISSED. The transfer script hand-rolled
  // its DB-row -> SemanticMapping projection as a 14-key object literal. The
  // model has SIXTEEN columns. The two it omitted were `unmentionedPolicy` and
  // `conceptScope` — and `updateTemplateTwinMappings` NULLS both when the
  // payload leaves them out:
  //
  //     unmentionedPolicy: mapping.unmentionedPolicy ?? null    (certification-lifecycle.ts:540)
  //     conceptScope:      … : Prisma.DbNull                    (certification-lifecycle.ts:547)
  //
  // So a "transfer" would have ERASED every ruled `omit` (#192/#194) and every
  // scaffolded `conceptScope` (#217), silently, behind a full set of green
  // guards. `conceptScope`'s own comment records that the ABSENCE of its writer
  // left four readers dead in production — this is the same loss, arriving
  // through the tool built to preserve.
  //
  // ⚠️ THE LIST WAS NOT THE DEFECT. HAVING ONE WAS. A 16th column added
  // tomorrow is dropped by the identical mechanism and nothing says so. So
  // these arms pin the SHARED PROJECTION rather than a column list — widening a
  // list by hand closes an instance; deriving from the one reader closes the
  // class.

  // ⚠️ THE VALUES ARE `gate-217`'s, NOT INVENTED. `SemanticMappingSchema` is
  // strict — fieldId matches /^ttf_[a-f0-9]{24}$/ and every policy is an enum —
  // so a fixture guessed from the column names parses as a wall of ZodErrors
  // and tests nothing. Borrowing the shipped gate's fixture also means these
  // arms and #217's cannot disagree about what a valid row looks like.
  const FIELD_ID = `ttf_${'a'.repeat(24)}`;

  /** A row carrying BOTH of the columns the hand-rolled literal dropped. */
  const ROW = {
    sourceType: 'extraction',
    clinicalConcept: 'ros.gastrointestinal.heartburn',
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: 'current',
    laterality: 'optional',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unmentionedPolicy: 'omit',
    conceptScope: ['ros.gastrointestinal.heartburn', 'ros.gastrointestinal.dysphagia'],
    unknownPolicy: 'blank',
    practiceDefault: null,
    mappingStatus: 'CERTIFIED',
  };

  it('the shared projection PRESERVES unmentionedPolicy and conceptScope', () => {
    const projected = fromPersistedMapping(FIELD_ID, ROW) as unknown as Record<string, unknown>;
    expect(projected.unmentionedPolicy).toBe('omit');
    expect(projected.conceptScope).toEqual([
      'ros.gastrointestinal.heartburn',
      'ros.gastrointestinal.dysphagia',
    ]);
  });

  it('DEMONSTRATES the defect: the hand-rolled 14-key literal drops exactly those two', () => {
    // ⚠️ Reproduced verbatim, so the arm shows the hazard rather than asserting
    // it is conceivable. This is the shape the script carried.
    const handRolled = {
      fieldId: FIELD_ID,
      sourceType: ROW.sourceType,
      clinicalConcept: ROW.clinicalConcept,
      expectedDataType: ROW.expectedDataType,
      polarityBehavior: ROW.polarityBehavior,
      temporality: ROW.temporality,
      laterality: ROW.laterality,
      unitPolicy: ROW.unitPolicy,
      approvedSynonyms: ROW.approvedSynonyms,
      required: ROW.required,
      blankPolicy: ROW.blankPolicy,
      unknownPolicy: ROW.unknownPolicy,
      practiceDefault: ROW.practiceDefault,
      status: 'certified',
    } as Record<string, unknown>;

    expect(handRolled.unmentionedPolicy).toBeUndefined(); // <- the ruled `omit`, gone
    expect(handRolled.conceptScope).toBeUndefined(); // <- the #217 scaffold, gone
  });

  it('the projection round-trips UNSUPPORTED, which a status map flattened away', () => {
    // ⚠️ The script's own `statusOf` helper mapped anything not CERTIFIED and not
    // RECOGNIZED to 'needs_confirmation' — so an UNSUPPORTED row came back as
    // needing confirmation, which is a different clinical state and a different
    // count.
    //
    // ⚠️ LATENT, NOT LIVE — AND THE CORRECTION IS RECORDED BECAUSE THE FIRST
    // WRITE-UP OVERSTATED IT. The lens said `create-draft.ts` "writes
    // UNSUPPORTED routinely"; a verifier disputed the reachability, and
    // production settles it: 238 mappings, ALL `CERTIFIED`, zero `UNSUPPORTED`.
    // The enum arm exists (`create-draft.ts:93-104`) and the column admits the
    // value, so the divergence is armed rather than firing.
    //
    // The fix does not depend on that either way, which is the point of fixing
    // the CLASS: `fromPersistedMapping` is the right reader whether or not this
    // particular row shape is reachable today.
    const projected = fromPersistedMapping(FIELD_ID, {
      ...ROW,
      mappingStatus: 'UNSUPPORTED',
    }) as unknown as Record<string, unknown>;
    expect(projected.status).toBe('unsupported');
  });

  it('OMITS the two keys when the row genuinely has none — absence stays absence', () => {
    // ⚠️ THE OTHER DIRECTION, AND IT IS NOT SYMMETRIC. `canonicalSha256` hashes
    // `[]` and `null` as VALUES, so reading an absent column back as one would
    // move the attestation sha of every pre-existing mapping and de-certify
    // every template at once. Omission is what makes a pre-column row hash
    // exactly as it did before the column existed.
    const projected = fromPersistedMapping(FIELD_ID, {
      ...ROW,
      unmentionedPolicy: null,
      conceptScope: null,
    }) as unknown as Record<string, unknown>;
    expect('unmentionedPolicy' in projected).toBe(false);
    expect('conceptScope' in projected).toBe(false);
  });
})

describe('and the SCRIPT is held to it — a structural arm, labelled as one', () => {
  // ⚠️ HONEST ABOUT WHAT IT PROVES. The arms above prove the shared projection
  // is correct; they cannot prove the SCRIPT uses it, because the script needs a
  // database to run. This reads the source instead. That is weaker than
  // execution and it is the strongest thing available here — so it is named a
  // structural arm rather than dressed as a behavioural one.
  //
  // It exists because the defect it guards is a RE-INTRODUCTION, not a typo: the
  // natural way to write this payload is an object literal, and an object
  // literal is exactly what dropped two clinical columns the first time.
  const SCRIPT = readFileSync(
    resolve(__dirname, '../../../../scripts/transfer-certification-to-active.ts'),
    'utf8',
  );

  it('imports the canonical projection', () => {
    expect(SCRIPT).toContain('fromPersistedMapping');
  });

  it('builds NO hand-rolled mapping literal — the tell is a bare `expectedDataType:`', () => {
    // Every hand-rolled projection has to name `expectedDataType`; the shared
    // one names it once, inside `certification-lifecycle`. So a surviving occurrence
    // here means somebody started writing the literal again.
    const occurrences = SCRIPT.split('\n').filter((l) =>
      /^\s*expectedDataType:/.test(l),
    ).length;
    expect(occurrences, 'a hand-rolled mapping literal has reappeared in the script').toBe(0);
  });

  it('the positive control: this arm CAN fail', () => {
    // ⚠️ A grep arm that cannot fail is decoration. Prove the predicate reds on
    // the shape it is looking for, using a string this file owns.
    const planted = 'const x = {\n  expectedDataType: "text",\n};';
    const occurrences = planted.split('\n').filter((l) =>
      /^\s*expectedDataType:/.test(l),
    ).length;
    expect(occurrences).toBe(1);
  });
})
