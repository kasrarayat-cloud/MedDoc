// ============================================================================
// RULING #313 O5 — THE BACKFILL DOOR'S GUARDS, PROVED WITHOUT A DATABASE.
// ----------------------------------------------------------------------------
// The act (`scripts/backfill-sole-paragraph-control.ts`) only reads and writes;
// every decision is `planSoleParagraphBackfill`. So each premise the act rests
// on is refused here by changing exactly that premise and nothing else.
//
// WHAT WOULD MAKE THIS FAIL: drop any guard -> its refusal arm plans a write;
// write a PARSED IR instead of the stored JSON -> the raw-default arm sees a
// second difference; hash the property -> the structure guard refuses the
// positive case.
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

import { canonicalSha256 } from '../canonical';
import {
  irWithoutSoleParagraphControl,
  parseSoleParagraphBackfillArgs,
  planSoleParagraphBackfill,
  type SoleParagraphBackfillInput,
} from '../sole-paragraph-backfill';
import {
  bullets,
  compiledForm,
  heading,
  mappingsFor,
  PMH,
  PMH_BODY,
  PMH_CONCEPTS,
} from './helpers-313';

const UUID = 'd2120cdd-74ae-43a3-85a3-1f185401e202';

describe('#313 backfill — arguments are REQUIRED, strict, and never defaulted', () => {
  const full = ['--compiled-version', UUID, '--expect-fields', '53', '--expect-groups', '7', '--expect-members', '24'];
  it('POSITIVE: all four present -> parsed; dry run unless --commit', () => {
    expect(parseSoleParagraphBackfillArgs(full)).toEqual({
      ok: true,
      args: { compiledVersionId: UUID, expectFields: 53, expectGroups: 7, expectMembers: 24, commit: false },
    });
    expect(parseSoleParagraphBackfillArgs([...full, '--commit'])).toMatchObject({ ok: true, args: { commit: true } });
  });
  it.each([
    ['--compiled-version'],
    ['--expect-fields'],
    ['--expect-groups'],
    ['--expect-members'],
  ])('missing %s refuses', (name) => {
    const at = full.indexOf(name);
    const argv = [...full.slice(0, at), ...full.slice(at + 2)];
    expect(parseSoleParagraphBackfillArgs(argv)).toMatchObject({ ok: false });
  });
  it('a non-uuid target, a non-integer count, or an unknown flag refuses', () => {
    expect(parseSoleParagraphBackfillArgs(full.map((a) => (a === UUID ? 'the-draft' : a)))).toMatchObject({ ok: false });
    expect(parseSoleParagraphBackfillArgs(full.map((a) => (a === '53' ? '53x' : a)))).toMatchObject({ ok: false });
    expect(parseSoleParagraphBackfillArgs([...full, '--force'])).toMatchObject({ ok: false });
  });
});

async function scenario() {
  const { source, ir } = await compiledForm([...PMH_BODY, heading('Plan'), ...bullets('Plan', 'plan', 2, 200)]);
  const mappings = mappingsFor(ir, { ...PMH_CONCEPTS, Plan: 'plan' });
  // The stored column: the SAME compile as the pre-#313 compiler wrote it,
  // JSON-round-tripped the way the jsonb column returns it.
  const storedIr = JSON.parse(JSON.stringify(irWithoutSoleParagraphControl(ir)));
  const input: SoleParagraphBackfillInput = {
    storedIr,
    recompiled: ir,
    mappings,
    certificationStatus: 'NEEDS_CONFIRMATION',
    hasCertificationRecord: false,
    templateStatus: 'draft',
    persistedFieldCount: ir.fields.length,
    columnStructureSha256: ir.structureSha256,
    columnStaticContentSha256: ir.staticContentSha256,
    artifactSha256: ir.source.sha256,
    bytesSha256: ir.source.sha256,
    fillManifestCount: 0,
    hasStoredSyntheticProof: false,
    expect: { fields: ir.fields.length, groups: 2, members: 5 },
  };
  return { source, ir, mappings, storedIr, input };
}

const failedNames = (plan: ReturnType<typeof planSoleParagraphBackfill>) =>
  plan.guards
    .filter(([, got, want]) => canonicalSha256(got) !== canonicalSha256(want))
    .map(([name]) => name);

describe('#313 backfill — the plan', () => {
  it('POSITIVE: every guard holds; the new IR is the stored JSON plus ONLY the property', async () => {
    const { ir, storedIr, input } = await scenario();
    const plan = planSoleParagraphBackfill(input);
    expect(failedNames(plan)).toEqual([]);
    expect(plan.failed).toBe(0);
    expect(plan.flaggedFieldIds).toHaveLength(5);
    expect(plan.groups.map((g) => g.memberFieldIds.length)).toEqual([3, 2]);
    expect(canonicalSha256(plan.next)).toBe(canonicalSha256(ir));
    expect(canonicalSha256(irWithoutSoleParagraphControl(plan.next))).toBe(canonicalSha256(storedIr));
    // ⚠️ NOTHING OUTSIDE `fields[*].soleParagraphControl` MOVED.
    const next = plan.next as typeof storedIr;
    expect(next.structureSha256).toBe(storedIr.structureSha256);
    expect(next.staticContentSha256).toBe(storedIr.staticContentSha256);
  });

  const REFUSALS: ReadonlyArray<[string, (input: SoleParagraphBackfillInput) => SoleParagraphBackfillInput, string]> = [
    ['a CERTIFIED version', (i) => ({ ...i, certificationStatus: 'CERTIFIED' }), 'certificationStatus is not CERTIFIED'],
    ['a certification record', (i) => ({ ...i, hasCertificationRecord: true }), 'no certification record exists'],
    ['a template that is not a draft', (i) => ({ ...i, templateStatus: 'active' }), 'note template status'],
    ['fill manifests stored against it (#247)', (i) => ({ ...i, fillManifestCount: 1 }), 'fill manifests stored against this version (#247 window)'],
    // #313 round one: a proof taken under the old IR would not re-verify.
    ['a stored synthetic proof', (i) => ({ ...i, hasStoredSyntheticProof: true }), 'no stored synthetic proof (it would not re-verify under the new IR)'],
    ['bytes that are not the artifact', (i) => ({ ...i, bytesSha256: 'f'.repeat(64) }), 'bytes sha256 == artifact sha256'],
    ['a moved structure column', (i) => ({ ...i, columnStructureSha256: 'e'.repeat(64) }), 'structureSha256 (recompiled == column)'],
    ['a moved static column', (i) => ({ ...i, columnStaticContentSha256: 'e'.repeat(64) }), 'staticContentSha256 (recompiled == column)'],
    ['a declared field count that disagrees', (i) => ({ ...i, expect: { ...i.expect, fields: i.expect.fields + 1 } }), 'stored IR field count'],
    ['persisted field rows that disagree', (i) => ({ ...i, persistedFieldCount: i.persistedFieldCount - 1 }), 'persisted field rows'],
    ['a declared group count that disagrees', (i) => ({ ...i, expect: { ...i.expect, groups: 3 } }), 'bullet groups under the current mappings'],
    ['a declared member count that disagrees', (i) => ({ ...i, expect: { ...i.expect, members: 6 } }), 'bullet group members under the current mappings'],
  ];

  it.each(REFUSALS)('refuses %s — and writes nothing', async (_name, change, guard) => {
    const { input } = await scenario();
    const plan = planSoleParagraphBackfill(change(input));
    // A declared field count is compared against BOTH the stored IR and the
    // persisted rows, so moving it fails both — correctly.
    const expected =
      guard === 'stored IR field count' ? ['stored IR field count', 'persisted field rows'] : [guard];
    expect(failedNames(plan)).toEqual(expected);
    expect(plan.next).toBeNull();
  });

  it('refuses a stored IR that ALREADY carries the property (no double act)', async () => {
    const { ir, input } = await scenario();
    const plan = planSoleParagraphBackfill({ ...input, storedIr: JSON.parse(JSON.stringify(ir)) });
    expect(failedNames(plan)).toEqual(['stored IR carries no soleParagraphControl yet']);
    expect(plan.next).toBeNull();
  });

  it('refuses ANY drift between the stored IR and the recompile', async () => {
    const { input, storedIr } = await scenario();
    const drifted = structuredClone(storedIr);
    drifted.fields[1].originalLabel = `${drifted.fields[1].originalLabel} (edited)`;
    const plan = planSoleParagraphBackfill({ ...input, storedIr: drifted });
    expect(failedNames(plan)).toEqual(['stored IR == recompiled IR except soleParagraphControl']);
    expect(plan.next).toBeNull();
  });

  it('refuses a reordered field list even when every field is present', async () => {
    const { input, storedIr } = await scenario();
    const reordered = structuredClone(storedIr);
    [reordered.fields[1], reordered.fields[2]] = [reordered.fields[2], reordered.fields[1]];
    const plan = planSoleParagraphBackfill({ ...input, storedIr: reordered });
    expect(failedNames(plan)).toContain('same fieldIds in the same order');
    expect(plan.next).toBeNull();
  });

  it('⚠️ the stored JSON is compared RAW — a missing schema default is drift, not noise', async () => {
    // `rowLaterality` has a zod DEFAULT: a parsed copy would silently re-add it
    // and a write of the parsed copy would change the stored bytes beyond the
    // one property the ruling authorises.
    const { input, storedIr } = await scenario();
    const legacy = structuredClone(storedIr);
    delete legacy.fields[0].rendererBinding.rowLaterality;
    const plan = planSoleParagraphBackfill({ ...input, storedIr: legacy });
    expect(failedNames(plan)).toEqual(['stored IR == recompiled IR except soleParagraphControl']);
  });

  it('the group count follows the CURRENT mappings — a divergent member refuses its group', async () => {
    const { ir, input } = await scenario();
    const members = ir.fields.filter((f) => f.rendererBinding.alias === PMH);
    const mappings = input.mappings.map((m) =>
      m.fieldId === members[2]!.fieldId ? { ...m, polarityBehavior: 'explicit_denial_allowed' as const } : m,
    );
    const plan = planSoleParagraphBackfill({ ...input, mappings, expect: { ...input.expect, groups: 1, members: 2 } });
    expect(failedNames(plan)).toEqual([]);
    expect(plan.groups).toHaveLength(1);
  });
});

describe('#313 backfill — importing the script never runs the act', () => {
  it('no database call on import', async () => {
    const findUnique = vi.fn();
    vi.doMock('@meddoc/db', () => ({
      default: { templateTwinCompiledVersion: { findUnique }, $disconnect: vi.fn() },
    }));
    vi.doMock('../twin-audit', () => ({ logTwinAudit: vi.fn() }));
    await import('../../../../scripts/backfill-sole-paragraph-control');
    expect(findUnique).not.toHaveBeenCalled();
    vi.doUnmock('@meddoc/db');
    vi.doUnmock('../twin-audit');
  });
});
