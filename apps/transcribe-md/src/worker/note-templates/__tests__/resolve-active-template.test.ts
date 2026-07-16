// ============================================================================
// resolveActiveTemplate — fallback-chain unit tests (Phase 0).
// ----------------------------------------------------------------------------
// Targets the PURE core `selectTemplate`. @meddoc/db is mocked so importing
// the module under test never constructs the real Prisma client (the pure
// resolver does no I/O; the async shell is exercised separately in Phase 1).
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const rolloutMocks = vi.hoisted(() => ({ pin: vi.fn() }));

vi.mock('@meddoc/db', () => ({
  default: {
    noteTemplate: { findMany: vi.fn(), findFirst: vi.fn() },
    user: { findUnique: vi.fn() },
  },
}));
vi.mock('@/lib/template-twin/rollout', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('@/lib/template-twin/rollout')
  >();
  return { ...actual, pinTemplateTwinRollout: rolloutMocks.pin };
});

import type { NoteTemplate } from '@prisma/client';
import prisma from '@meddoc/db';
import {
  selectTemplate,
  MissingSystemDefaultTemplateError,
  PinnedTemplateUnavailableError,
  TemplateTwinWorkerRolloutError,
  resolveActiveTemplate,
  resolveActiveTemplateAdmission,
  resolveVisitTemplate,
} from '../resolve-active-template';

/** Build a NoteTemplate row with sane Phase-0 defaults. */
function tmpl(overrides: Partial<NoteTemplate> = {}): NoteTemplate {
  return {
    id: 'tmpl',
    doctorId: null,
    name: 'T',
    encounterType: null,
    specialtyBaseline: null,
    sections: [],
    styleProfile: null,
    version: 1,
    status: 'active',
    isSystemDefault: false,
    createdAt: new Date('2026-06-03T00:00:00Z'),
    updatedAt: new Date('2026-06-03T00:00:00Z'),
    ...overrides,
  } as NoteTemplate;
}

const systemDefault = tmpl({
  id: 'sys',
  doctorId: null,
  isSystemDefault: true,
  name: 'System Default — SOAP',
});

beforeEach(() => {
  vi.clearAllMocks();
  process.env.TEMPLATE_TWIN_KILL_SWITCH = 'false';
  rolloutMocks.pin.mockResolvedValue({
    practiceId: 'practice-1',
    globalGeneration: BigInt(1),
    practiceGeneration: BigInt(1),
  });
});

describe('selectTemplate — fallback chain', () => {
  it('Phase-0 reality: returns the system default when the doctor has no custom template', () => {
    expect(
      selectTemplate([systemDefault], { doctorId: 'doc1', encounterType: 'cardiology' })
    ).toBe(systemDefault);
  });

  it('returns the system default when no encounter type is requested and there is no doctor template', () => {
    expect(selectTemplate([systemDefault], { doctorId: 'doc1' })).toBe(systemDefault);
  });

  it("returns the doctor's catch-all (encounterType null) over the system default", () => {
    const doctorDefault = tmpl({ id: 'dd', doctorId: 'doc1', encounterType: null });
    expect(
      selectTemplate([systemDefault, doctorDefault], { doctorId: 'doc1' })
    ).toBe(doctorDefault);
  });

  it("prefers the doctor's exact encounter-type match over the catch-all", () => {
    const doctorDefault = tmpl({ id: 'dd', doctorId: 'doc1', encounterType: null });
    const exact = tmpl({ id: 'ex', doctorId: 'doc1', encounterType: 'cardiology' });
    expect(
      selectTemplate([systemDefault, doctorDefault, exact], {
        doctorId: 'doc1',
        encounterType: 'cardiology',
      })
    ).toBe(exact);
  });

  it('falls back to the catch-all when no template matches the requested encounter type', () => {
    const doctorDefault = tmpl({ id: 'dd', doctorId: 'doc1', encounterType: null });
    const exact = tmpl({ id: 'ex', doctorId: 'doc1', encounterType: 'cardiology' });
    expect(
      selectTemplate([systemDefault, doctorDefault, exact], {
        doctorId: 'doc1',
        encounterType: 'dermatology',
      })
    ).toBe(doctorDefault);
  });

  it("ignores another doctor's templates", () => {
    const otherDoc = tmpl({ id: 'od', doctorId: 'doc2', encounterType: 'cardiology' });
    expect(
      selectTemplate([systemDefault, otherDoc], {
        doctorId: 'doc1',
        encounterType: 'cardiology',
      })
    ).toBe(systemDefault);
  });

  it('ignores non-active (draft) templates', () => {
    const draftCatchAll = tmpl({
      id: 'dr',
      doctorId: 'doc1',
      encounterType: null,
      status: 'draft',
    });
    expect(selectTemplate([systemDefault, draftCatchAll], { doctorId: 'doc1' })).toBe(
      systemDefault
    );
  });

  it('ignores a draft exact match and continues down the chain', () => {
    const draftExact = tmpl({
      id: 'dx',
      doctorId: 'doc1',
      encounterType: 'cardiology',
      status: 'draft',
    });
    const doctorDefault = tmpl({ id: 'dd', doctorId: 'doc1', encounterType: null });
    expect(
      selectTemplate([systemDefault, draftExact, doctorDefault], {
        doctorId: 'doc1',
        encounterType: 'cardiology',
      })
    ).toBe(doctorDefault);
  });

  it('throws MissingSystemDefaultTemplateError when no system default is present', () => {
    expect(() => selectTemplate([], { doctorId: 'doc1' })).toThrow(
      MissingSystemDefaultTemplateError
    );
    // A doctor draft with no active fallback + no system default also throws.
    const draft = tmpl({ id: 'dr', doctorId: 'doc1', status: 'draft' });
    expect(() => selectTemplate([draft], { doctorId: 'doc1' })).toThrow(
      MissingSystemDefaultTemplateError
    );
  });
});

describe('resolveVisitTemplate — immutable retry provenance', () => {
  it('reuses the exact pinned version even after it becomes inactive', async () => {
    const pinned = tmpl({
      id: 'twin-v1',
      doctorId: 'doc1',
      version: 1,
      status: 'inactive',
    });
    vi.mocked(prisma.noteTemplate.findFirst).mockResolvedValueOnce(pinned);

    await expect(
      resolveVisitTemplate({
        doctorId: 'doc1',
        encounterType: 'cardiology',
        pinnedTemplateId: 'twin-v1',
        pinnedTemplateVersion: 1,
      })
    ).resolves.toBe(pinned);
    expect(prisma.noteTemplate.findFirst).toHaveBeenCalledWith({
      where: {
        id: 'twin-v1',
        version: 1,
        OR: [{ doctorId: 'doc1' }, { isSystemDefault: true }],
      },
    });
  });

  it('rejects a pinned Template Twin when the practice rollout flag is off', async () => {
    process.env.TEMPLATE_TWIN_KILL_SWITCH = 'false';
    const pinned = tmpl({
      id: 'twin-disabled',
      doctorId: 'doc1',
      templateKind: 'template_twin_docx',
    });
    vi.mocked(prisma.noteTemplate.findFirst).mockResolvedValueOnce(pinned);
    vi.mocked(prisma.user.findUnique).mockResolvedValueOnce({
      role: 'DOCTOR',
      isActive: true,
      practice: { templateTwinEnabled: false },
    } as never);

    await expect(
      resolveVisitTemplate({
        doctorId: 'doc1',
        pinnedTemplateId: pinned.id,
        pinnedTemplateVersion: pinned.version,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinWorkerRolloutError);
  });

  it('excludes an active Template Twin from first-pass selection while rollout is disabled', async () => {
    process.env.TEMPLATE_TWIN_KILL_SWITCH = 'false';
    const twin = tmpl({
      id: 'twin-disabled-active',
      doctorId: 'doc1',
      encounterType: 'cardiology',
      templateKind: 'template_twin_docx',
    });
    vi.mocked(prisma.noteTemplate.findMany).mockResolvedValueOnce([
      systemDefault,
      twin,
    ]);
    vi.mocked(prisma.user.findUnique).mockResolvedValueOnce({
      role: 'DOCTOR',
      isActive: true,
      practice: { templateTwinEnabled: false },
    } as never);

    await expect(
      resolveActiveTemplate({ doctorId: 'doc1', encounterType: 'cardiology' }),
    ).resolves.toBe(systemDefault);
  });

  it('uses persisted global and lineage admission before selecting an active Twin', async () => {
    const twin = tmpl({
      id: 'twin-enabled-active',
      doctorId: 'doc1',
      encounterType: 'cardiology',
      templateKind: 'template_twin_docx',
    });
    vi.mocked(prisma.noteTemplate.findMany).mockResolvedValueOnce([
      systemDefault,
      twin,
    ]);
    vi.mocked(prisma.user.findUnique).mockResolvedValueOnce({
      role: 'DOCTOR',
      isActive: true,
      practiceId: 'practice-1',
      practice: { templateTwinEnabled: true },
    } as never);

    await expect(
      resolveActiveTemplate({ doctorId: 'doc1', encounterType: 'cardiology' }),
    ).resolves.toBe(twin);
    expect(rolloutMocks.pin).toHaveBeenCalledWith({
      practiceId: 'practice-1',
    });
  });

  it('returns the exact persisted rollout token with a worker Twin selection', async () => {
    const twin = tmpl({
      id: 'twin-admission-token',
      doctorId: 'doc1',
      encounterType: 'cardiology',
      templateKind: 'template_twin_docx',
    });
    const token = {
      practiceId: 'practice-1',
      globalGeneration: BigInt(17),
      practiceGeneration: BigInt(23),
    };
    vi.mocked(prisma.noteTemplate.findMany).mockResolvedValueOnce([
      systemDefault,
      twin,
    ]);
    vi.mocked(prisma.user.findUnique).mockResolvedValueOnce({
      role: 'DOCTOR',
      isActive: true,
      practiceId: 'practice-1',
      practice: { templateTwinEnabled: true },
    } as never);
    rolloutMocks.pin.mockResolvedValueOnce(token);

    await expect(
      resolveActiveTemplateAdmission({
        doctorId: 'doc1',
        encounterType: 'cardiology',
      }),
    ).resolves.toEqual({
      template: twin,
      templateTwinRolloutToken: token,
    });
  });

  it('falls back to the structured default when persisted admission fails closed', async () => {
    const twin = tmpl({
      id: 'twin-db-disabled-active',
      doctorId: 'doc1',
      encounterType: 'cardiology',
      templateKind: 'template_twin_docx',
    });
    vi.mocked(prisma.noteTemplate.findMany).mockResolvedValueOnce([
      systemDefault,
      twin,
    ]);
    vi.mocked(prisma.user.findUnique).mockResolvedValueOnce({
      role: 'DOCTOR',
      isActive: true,
      practiceId: 'practice-1',
      practice: { templateTwinEnabled: true },
    } as never);
    rolloutMocks.pin.mockRejectedValueOnce(
      new Error('synthetic persisted global disable'),
    );

    await expect(
      resolveActiveTemplate({ doctorId: 'doc1', encounterType: 'cardiology' }),
    ).resolves.toBe(systemDefault);
  });

  it('keeps legacy structured templates eligible while Template Twin rollout is disabled', async () => {
    process.env.TEMPLATE_TWIN_KILL_SWITCH = 'false';
    const structured = tmpl({
      id: 'structured-active',
      doctorId: 'doc1',
      encounterType: null,
      templateKind: 'structured',
    });
    const twin = tmpl({
      id: 'twin-disabled-active',
      doctorId: 'doc1',
      encounterType: 'cardiology',
      templateKind: 'template_twin_docx',
    });
    vi.mocked(prisma.noteTemplate.findMany).mockResolvedValueOnce([
      systemDefault,
      structured,
      twin,
    ]);
    vi.mocked(prisma.user.findUnique).mockResolvedValueOnce({
      role: 'DOCTOR',
      isActive: true,
      practice: { templateTwinEnabled: false },
    } as never);

    await expect(
      resolveActiveTemplate({ doctorId: 'doc1', encounterType: 'cardiology' }),
    ).resolves.toBe(structured);
  });

  it('fails closed when a pin is partial or unavailable', async () => {
    await expect(
      resolveVisitTemplate({
        doctorId: 'doc1',
        pinnedTemplateId: 'twin-v1',
        pinnedTemplateVersion: null,
      })
    ).rejects.toBeInstanceOf(PinnedTemplateUnavailableError);

    vi.mocked(prisma.noteTemplate.findFirst).mockResolvedValueOnce(null);
    await expect(
      resolveVisitTemplate({
        doctorId: 'doc1',
        pinnedTemplateId: 'twin-v1',
        pinnedTemplateVersion: 1,
      })
    ).rejects.toBeInstanceOf(PinnedTemplateUnavailableError);
  });
});
