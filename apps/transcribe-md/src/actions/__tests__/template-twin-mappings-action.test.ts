// ============================================================================
// THE MAPPINGS DOOR — and the arm that would have caught its absence.
//
// ⚠️ `updateTemplateTwinMappings` SHIPPED WITH NO CALLER. Correct, tested, and
// unreachable: the only reference anywhere in the repository was a test
// grepping its source text. So `MAPPINGS_NOT_READY` refused all 80 of 80 fields not
// because the gate was strict but because NOTHING COULD EVER CONFIRM THEM —
// the gate was right and unsatisfiable.
//
// That is RC-2's shape one layer up ("correct, working code with no door"), and
// the first test below is the one that would have said so. It is a REACHABILITY
// assertion, not a behaviour assertion, and it is deliberately blunt.
// ============================================================================
import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const h = vi.hoisted(() => {
  // ⚠️ THE ERROR CLASS IS DEFINED IN THE MOCK, NOT IMPORTED FROM THE REAL
  // MODULE. Spreading the actual `certification-lifecycle` into the factory
  // drags prisma and the whole twin runtime into a test about ONE action's
  // control flow — which is what made the first version of this file fail to
  // load at all. The action only ever does `instanceof`, so a faithful stub is
  // the honest dependency.
  class LifecycleError extends Error {
    readonly code: string;
    constructor(code: string, message: string) {
      super(message);
      this.name = 'TemplateTwinLifecycleError';
      this.code = code;
    }
  }
  return {
    requireSession: vi.fn(),
    update: vi.fn(),
    read: vi.fn(),
    enabled: vi.fn(() => true),
    LifecycleError,
  };
});

vi.mock('@/lib/auth', () => ({ requireSession: h.requireSession }));
vi.mock('@/config/template-native-docx', () => ({ templateNativeDocxEnabled: h.enabled }));
vi.mock('@/lib/template-twin/certification-lifecycle', () => ({
  updateTemplateTwinMappings: h.update,
  TemplateTwinLifecycleError: h.LifecycleError,
}));
vi.mock('@/lib/template-twin/workspace-read', () => ({ readTemplateTwinWorkspace: h.read }));

import {
  updateTemplateTwinMappingsAction,
  openNativeTemplateWorkspaceAction,
} from '@/actions/template-twin-mappings';

const SHA = 'a'.repeat(64);
const MAPPINGS = [] as never[];

beforeEach(() => {
  vi.clearAllMocks();
  h.enabled.mockReturnValue(true);
  h.requireSession.mockResolvedValue({
    user: { id: 'doc_1', email: 'd@example.invalid', practiceId: 'prac_1' },
  });
  h.update.mockResolvedValue(undefined);
  h.read.mockResolvedValue({ template: { id: 'tmpl_1' }, fields: [] });
});

const SRC = path.resolve(__dirname, '../..');
function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    const p = path.join(dir, e);
    if (e === 'node_modules' || e === '__tests__') continue;
    if (statSync(p).isDirectory()) sourceFiles(p, out);
    else if (p.endsWith('.ts') || p.endsWith('.tsx')) out.push(p);
  }
  return out;
}

describe('⚠️ the confirm-a-mapping writer HAS A CALLER', () => {
  it('updateTemplateTwinMappings is reachable from application code', () => {
    // The defect this pins is ABSENCE, so the assertion is about the callers,
    // not about behaviour. Tests are excluded from the walk on purpose: a test
    // referencing the symbol is exactly what made it LOOK reachable while
    // nothing could invoke it.
    const callers = sourceFiles(SRC)
      .filter((f) => !f.endsWith('certification-lifecycle.ts'))
      .filter((f) => /updateTemplateTwinMappings\s*\(/.test(readFileSync(f, 'utf8')))
      .map((f) => path.relative(SRC, f));
    expect(
      callers,
      'nothing in the application calls updateTemplateTwinMappings. MAPPINGS_NOT_READY ' +
        'then refuses every field forever — a correct gate made unsatisfiable by a ' +
        'missing door, which is the exact defect this action exists to close.',
    ).not.toEqual([]);
  });
});

describe('updateTemplateTwinMappingsAction', () => {
  it('passes the SESSION actor through — never a caller-supplied identity', async () => {
    await updateTemplateTwinMappingsAction('tmpl_1', SHA, MAPPINGS);
    expect(h.update).toHaveBeenCalledTimes(1);
    const arg = h.update.mock.calls[0]![0] as { actor: { userId: string; practiceId: string } };
    expect(arg.actor).toMatchObject({ userId: 'doc_1', practiceId: 'prac_1' });
  });

  it('carries the expected hash — optimistic concurrency is not invented here', async () => {
    await updateTemplateTwinMappingsAction('tmpl_1', SHA, MAPPINGS);
    expect(h.update.mock.calls[0]![0]).toMatchObject({ expectedMappingsSha256: SHA });
  });

  it('a CONFLICT is reported as conflict, never as a generic failure', async () => {
    h.update.mockRejectedValueOnce(new h.LifecycleError('CONFLICT', 'moved'));
    const out = await updateTemplateTwinMappingsAction('tmpl_1', SHA, MAPPINGS);
    if (out.ok) throw new Error('expected a refusal');
    expect(out.reason).toBe('conflict');
    expect(out.error).toMatch(/reload/i);
  });

  it('a CERTIFIED template refuses as IMMUTABLE — certification is not re-openable', async () => {
    h.update.mockRejectedValueOnce(new h.LifecycleError('IMMUTABLE', 'certified'));
    const out = await updateTemplateTwinMappingsAction('tmpl_1', SHA, MAPPINGS);
    if (out.ok) throw new Error('expected a refusal');
    expect(out.reason).toBe('lifecycle');
    expect(out.error).toMatch(/already certified/i);
  });

  it('⚠️ AN UNEXPECTED THROW NEVER LEAKS ITS MESSAGE — labels are confidential', async () => {
    // A mapping payload carries the doctor's own field labels (SPEC §4.3a(e)),
    // and a Zod issue path quotes them. The raw message must not reach the UI.
    const secret = 'REFERRING PHYSICIAN: Dr Confidential';
    h.update.mockRejectedValueOnce(new Error(secret));
    const out = await updateTemplateTwinMappingsAction('tmpl_1', SHA, MAPPINGS);
    if (out.ok) throw new Error('expected a refusal');
    expect(out.reason).toBe('unexpected');
    expect(out.error).not.toContain('Confidential');
    expect(out.error).not.toContain(secret);
  });

  it('a WRITE THAT SUCCEEDS but reads back nothing is NOT reported as success', async () => {
    // Otherwise the UI renders an empty workspace over confirmed mappings and
    // the doctor believes their work is gone.
    h.read.mockResolvedValueOnce(null);
    const out = await updateTemplateTwinMappingsAction('tmpl_1', SHA, MAPPINGS);
    expect(out.ok).toBe(false);
  });

  it('the flag gates the ACTION, not just the UI', async () => {
    h.enabled.mockReturnValue(false);
    const out = await updateTemplateTwinMappingsAction('tmpl_1', SHA, MAPPINGS);
    if (out.ok) throw new Error('expected a refusal');
    expect(out.reason).toBe('disabled');
    expect(h.update).not.toHaveBeenCalled();
  });
});

// ============================================================================
// F5-b — THE READ HALF OF THE DOOR.
//
// ⚠️ THESE ARMS EXIST BECAUSE A MUTATION PROOF FOUND THE UI GATE BLIND HERE.
// `gate-f5b-the-confirmation-door-exists.test.tsx` MOCKS this action, so it
// asserts the door is reachable and says NOTHING about what happens inside it:
// a mutation replacing `doctorId: session.user.id` with the caller-supplied id
// left all 17 of its arms green. The UI gate watches the DOOR; this watches the
// LOCK. Neither substitutes for the other.
// ============================================================================
describe('⚠️ the workspace READER has a caller — the reason it may exist at all', () => {
  it('openNativeTemplateWorkspaceAction is reachable from application code', () => {
    // `getNativeTemplateWorkspaceAction` was DELETED on 2026-07-28 for having
    // zero callers, correctly: a server action is an HTTP endpoint, so an
    // unused exported one is attack surface no test covers. Re-adding a reader
    // is only defensible while this arm is green.
    const callers = sourceFiles(SRC)
      .filter((f) => !f.endsWith('template-twin-mappings.ts'))
      .filter((f) => /openNativeTemplateWorkspaceAction\s*\(/.test(readFileSync(f, 'utf8')))
      .map((f) => path.relative(SRC, f));
    expect(
      callers,
      'nothing in the application calls openNativeTemplateWorkspaceAction. An exported ' +
        'server action with no caller is an unreviewed HTTP endpoint — the exact reason ' +
        'its predecessor was deleted.',
    ).not.toEqual([]);
  });
});

describe('openNativeTemplateWorkspaceAction', () => {
  it('scopes the read to the SESSION, never to the caller-supplied id', async () => {
    await openNativeTemplateWorkspaceAction('tmpl_1');
    expect(h.read).toHaveBeenCalledTimes(1);
    expect(h.read.mock.calls[0]![0]).toEqual({
      noteTemplateId: 'tmpl_1',
      doctorId: 'doc_1',
      practiceId: 'prac_1',
    });
  });

  it('another doctor’s template is INDISTINGUISHABLE from one that does not exist', async () => {
    // `readTemplateTwinWorkspace` filters on doctorId, so someone else's
    // template reads as absent. The refusal must not tell the two apart —
    // otherwise the id space is enumerable by reading which message came back.
    h.read.mockResolvedValueOnce(null);
    const out = await openNativeTemplateWorkspaceAction('tmpl_someone_else');
    if (out.ok) throw new Error('expected a refusal');
    expect(out.error).toBe('That template could not be opened for review.');
    expect(out.error).not.toMatch(/permission|denied|another|owner|exists/i);
  });

  it('the flag gates the READER too, and it refuses BEFORE touching the database', async () => {
    h.enabled.mockReturnValue(false);
    const out = await openNativeTemplateWorkspaceAction('tmpl_1');
    if (out.ok) throw new Error('expected a refusal');
    expect(out.reason).toBe('disabled');
    expect(h.read).not.toHaveBeenCalled();
  });

  it('is READ-ONLY — opening a workspace never writes', async () => {
    await openNativeTemplateWorkspaceAction('tmpl_1');
    expect(h.update).not.toHaveBeenCalled();
  });
});
