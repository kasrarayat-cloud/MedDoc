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
    templateTwinSyntheticQaRun: { findFirst: vi.fn() },
    user: { findUnique: vi.fn() },
  },
}));
vi.mock('@/lib/template-twin/rollout', async (importOriginal) => {
  const actual =
    (await importOriginal()) as typeof import('@/lib/template-twin/rollout');
  return { ...actual, pinTemplateTwinRollout: rolloutMocks.pin };
});

import type { NoteTemplate } from '@prisma/client';
import prisma from '@meddoc/db';
import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from '@/lib/template-twin/staging-qa-fixtures';
import {
  assertTemplateTwinWorkerRuntimeAdmission,
  selectTemplate,
  MissingSystemDefaultTemplateError,
  PinnedTemplateUnavailableError,
  TemplateTwinWorkerRolloutError,
  resolveActiveTemplate,
  resolveActiveTemplateAdmission,
  resolveVisitTemplate,
} from '../resolve-active-template';
import { syntheticSourceAdmission } from '@/lib/template-twin/__tests__/source-admission-fixture';

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

function admittedTwin(
  overrides: Partial<NoteTemplate> = {},
  source: { sha256?: string; sizeBytes?: number } = {},
) {
  const row = tmpl({ templateKind: 'template_twin_docx', ...overrides });
  const sha256 = source.sha256 ?? 'c'.repeat(64);
  const sizeBytes = source.sizeBytes ?? 4096;
  return {
    ...row,
    templateTwinCompiledVersion: {
      sourceArtifact: syntheticSourceAdmission({
        practiceId: 'practice-1',
        lineageId: `lineage-${row.id}`,
        minimizedSha256: sha256,
        minimizedSizeBytes: sizeBytes,
      }),
    },
  };
}

const systemDefault = tmpl({
  id: 'sys',
  doctorId: null,
  isSystemDefault: true,
  name: 'System Default — SOAP',
});

beforeEach(() => {
  vi.clearAllMocks();
  delete process.env.TEMPLATE_TWIN_STAGING_QA_ENABLED;
  delete process.env.TEMPLATE_TWIN_RUNTIME_MODE;
  process.env.TEMPLATE_TWIN_KILL_SWITCH = 'false';
  rolloutMocks.pin.mockResolvedValue({
    practiceId: 'practice-1',
    globalGeneration: BigInt(1),
    practiceGeneration: BigInt(1),
  });
});

describe('selectTemplate — fallback chain', () => {
  it('rejects a pinned Twin before providers in rollback compatibility mode', () => {
    expect(() =>
      assertTemplateTwinWorkerRuntimeAdmission('template_twin_docx', {
        TEMPLATE_TWIN_RUNTIME_MODE: 'rollback-compat-v2',
      }),
    ).toThrow(TemplateTwinWorkerRolloutError);
    expect(() =>
      assertTemplateTwinWorkerRuntimeAdmission('structured', {
        TEMPLATE_TWIN_RUNTIME_MODE: 'rollback-compat-v2',
      }),
    ).not.toThrow();
  });

  it('Phase-0 reality: returns the system default when the doctor has no custom template', () => {
    expect(
      selectTemplate([systemDefault], {
        doctorId: 'doc1',
        encounterType: 'cardiology',
      }),
    ).toBe(systemDefault);
  });

  it('returns the system default when no encounter type is requested and there is no doctor template', () => {
    expect(selectTemplate([systemDefault], { doctorId: 'doc1' })).toBe(
      systemDefault,
    );
  });

  it("returns the doctor's catch-all (encounterType null) over the system default", () => {
    const doctorDefault = tmpl({
      id: 'dd',
      doctorId: 'doc1',
      encounterType: null,
    });
    expect(
      selectTemplate([systemDefault, doctorDefault], { doctorId: 'doc1' }),
    ).toBe(doctorDefault);
  });

  it("prefers the doctor's exact encounter-type match over the catch-all", () => {
    const doctorDefault = tmpl({
      id: 'dd',
      doctorId: 'doc1',
      encounterType: null,
    });
    const exact = tmpl({
      id: 'ex',
      doctorId: 'doc1',
      encounterType: 'cardiology',
    });
    expect(
      selectTemplate([systemDefault, doctorDefault, exact], {
        doctorId: 'doc1',
        encounterType: 'cardiology',
      }),
    ).toBe(exact);
  });

  it('falls back to the catch-all when no template matches the requested encounter type', () => {
    const doctorDefault = tmpl({
      id: 'dd',
      doctorId: 'doc1',
      encounterType: null,
    });
    const exact = tmpl({
      id: 'ex',
      doctorId: 'doc1',
      encounterType: 'cardiology',
    });
    expect(
      selectTemplate([systemDefault, doctorDefault, exact], {
        doctorId: 'doc1',
        encounterType: 'dermatology',
      }),
    ).toBe(doctorDefault);
  });

  it("ignores another doctor's templates", () => {
    const otherDoc = tmpl({
      id: 'od',
      doctorId: 'doc2',
      encounterType: 'cardiology',
    });
    expect(
      selectTemplate([systemDefault, otherDoc], {
        doctorId: 'doc1',
        encounterType: 'cardiology',
      }),
    ).toBe(systemDefault);
  });

  it('ignores non-active (draft) templates', () => {
    const draftCatchAll = tmpl({
      id: 'dr',
      doctorId: 'doc1',
      encounterType: null,
      status: 'draft',
    });
    expect(
      selectTemplate([systemDefault, draftCatchAll], { doctorId: 'doc1' }),
    ).toBe(systemDefault);
  });

  it('ignores a draft exact match and continues down the chain', () => {
    const draftExact = tmpl({
      id: 'dx',
      doctorId: 'doc1',
      encounterType: 'cardiology',
      status: 'draft',
    });
    const doctorDefault = tmpl({
      id: 'dd',
      doctorId: 'doc1',
      encounterType: null,
    });
    expect(
      selectTemplate([systemDefault, draftExact, doctorDefault], {
        doctorId: 'doc1',
        encounterType: 'cardiology',
      }),
    ).toBe(doctorDefault);
  });

  it('throws MissingSystemDefaultTemplateError when no system default is present', () => {
    expect(() => selectTemplate([], { doctorId: 'doc1' })).toThrow(
      MissingSystemDefaultTemplateError,
    );
    // A doctor draft with no active fallback + no system default also throws.
    const draft = tmpl({ id: 'dr', doctorId: 'doc1', status: 'draft' });
    expect(() => selectTemplate([draft], { doctorId: 'doc1' })).toThrow(
      MissingSystemDefaultTemplateError,
    );
  });

  it('does not treat a user-facing staging-like name or scope as provenance', () => {
    const ordinary = tmpl({
      id: 'ordinary-lookalike',
      doctorId: 'doc1',
      name: 'Template Twin Synthetic QA',
      encounterType: 'template-twin-synthetic-qa',
    });
    expect(
      selectTemplate([systemDefault, ordinary], {
        doctorId: 'doc1',
        encounterType: 'template-twin-synthetic-qa',
      }),
    ).toBe(ordinary);
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
      }),
    ).resolves.toBe(pinned);
    expect(prisma.noteTemplate.findFirst).toHaveBeenCalledWith({
      where: {
        id: 'twin-v1',
        version: 1,
        OR: [{ doctorId: 'doc1' }, { isSystemDefault: true }],
      },
      include: {
        templateTwinCompiledVersion: {
          select: {
            sourceArtifact: {
              select: expect.objectContaining({
                sha256: true,
                sizeBytes: true,
                quarantineArtifact: expect.any(Object),
              }),
            },
          },
        },
      },
    });
  });

  it('excludes an exact staging source from ordinary active resolution even after rename', async () => {
    const renamedStaging = admittedTwin(
      {
        id: 'renamed-staging',
        doctorId: 'doc1',
        name: 'Ordinary looking name',
        encounterType: 'cardiology',
      },
      {
        sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
        sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
      },
    );
    vi.mocked(prisma.noteTemplate.findMany).mockResolvedValueOnce([
      systemDefault,
      renamedStaging,
    ] as never);

    await expect(
      resolveActiveTemplate({ doctorId: 'doc1', encounterType: 'cardiology' }),
    ).resolves.toBe(systemDefault);
    expect(prisma.user.findUnique).not.toHaveBeenCalled();
  });

  it('requires a matching durable run for a pinned exact staging source', async () => {
    process.env.TEMPLATE_TWIN_STAGING_QA_ENABLED = 'true';
    const pinnedStaging = admittedTwin(
      {
        id: 'staging-pinned',
        doctorId: 'doc1',
      },
      {
        sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
        sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
      },
    );
    vi.mocked(prisma.noteTemplate.findFirst).mockResolvedValue(
      pinnedStaging as never,
    );
    vi.mocked(
      prisma.templateTwinSyntheticQaRun.findFirst,
    ).mockResolvedValueOnce(null);

    await expect(
      resolveVisitTemplate({
        visitId: 'visit-without-run',
        doctorId: 'doc1',
        pinnedTemplateId: pinnedStaging.id,
        pinnedTemplateVersion: pinnedStaging.version,
      }),
    ).rejects.toBeInstanceOf(PinnedTemplateUnavailableError);

    vi.mocked(
      prisma.templateTwinSyntheticQaRun.findFirst,
    ).mockResolvedValueOnce({
      id: 'run-1',
    } as never);
    vi.mocked(prisma.user.findUnique).mockResolvedValueOnce({
      role: 'DOCTOR',
      isActive: true,
      practiceId: 'practice-1',
      practice: { templateTwinEnabled: true },
    } as never);
    await expect(
      resolveVisitTemplate({
        visitId: 'visit-with-run',
        doctorId: 'doc1',
        pinnedTemplateId: pinnedStaging.id,
        pinnedTemplateVersion: pinnedStaging.version,
      }),
    ).resolves.toBe(pinnedStaging);
  });

  it('rejects a pinned Template Twin when the practice rollout flag is off', async () => {
    process.env.TEMPLATE_TWIN_KILL_SWITCH = 'false';
    const pinned = admittedTwin({
      id: 'twin-disabled',
      doctorId: 'doc1',
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
    const twin = admittedTwin({
      id: 'twin-disabled-active',
      doctorId: 'doc1',
      encounterType: 'cardiology',
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

  it('excludes every generic active Template Twin when synthetic-only staging is requested', async () => {
    process.env.TEMPLATE_TWIN_STAGING_QA_ENABLED = 'true';
    const twin = admittedTwin({
      id: 'twin-staging-bypass-active',
      doctorId: 'doc1',
      encounterType: 'cardiology',
    });
    vi.mocked(prisma.noteTemplate.findMany).mockResolvedValueOnce([
      systemDefault,
      twin,
    ]);

    await expect(
      resolveActiveTemplate({ doctorId: 'doc1', encounterType: 'cardiology' }),
    ).resolves.toBe(systemDefault);
    expect(prisma.user.findUnique).not.toHaveBeenCalled();
    expect(rolloutMocks.pin).not.toHaveBeenCalled();
  });

  it('rejects a pinned non-fixture Template Twin when synthetic-only staging is requested', async () => {
    process.env.TEMPLATE_TWIN_STAGING_QA_ENABLED = 'true';
    const pinned = admittedTwin({
      id: 'twin-staging-bypass-pinned',
      doctorId: 'doc1',
    });
    vi.mocked(prisma.noteTemplate.findFirst).mockResolvedValueOnce(pinned);

    await expect(
      resolveVisitTemplate({
        visitId: 'visit-staging-bypass',
        doctorId: 'doc1',
        pinnedTemplateId: pinned.id,
        pinnedTemplateVersion: pinned.version,
      }),
    ).rejects.toBeInstanceOf(PinnedTemplateUnavailableError);
    expect(prisma.user.findUnique).not.toHaveBeenCalled();
    expect(rolloutMocks.pin).not.toHaveBeenCalled();
  });

  it('uses persisted global and lineage admission before selecting an active Twin', async () => {
    const twin = admittedTwin({
      id: 'twin-enabled-active',
      doctorId: 'doc1',
      encounterType: 'cardiology',
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

  it('excludes a legacy active Twin without current source admission', async () => {
    const admitted = admittedTwin({
      id: 'twin-legacy-active',
      doctorId: 'doc1',
      encounterType: 'cardiology',
    });
    const legacy = {
      ...admitted,
      templateTwinCompiledVersion: {
        ...admitted.templateTwinCompiledVersion,
        sourceArtifact: {
          ...admitted.templateTwinCompiledVersion.sourceArtifact,
          quarantineArtifact: null,
        },
      },
    };
    vi.mocked(prisma.noteTemplate.findMany).mockResolvedValueOnce([
      systemDefault,
      legacy,
    ] as never);

    await expect(
      resolveActiveTemplate({ doctorId: 'doc1', encounterType: 'cardiology' }),
    ).resolves.toBe(systemDefault);
    expect(prisma.user.findUnique).not.toHaveBeenCalled();
    expect(rolloutMocks.pin).not.toHaveBeenCalled();
  });

  it('excludes an active kind-drifted template that retains compiled lineage', async () => {
    const compiled = admittedTwin({
      id: 'kind-drift-active',
      doctorId: 'doc1',
      encounterType: 'cardiology',
    });
    const kindDrifted = { ...compiled, templateKind: 'structured' };
    vi.mocked(prisma.noteTemplate.findMany).mockResolvedValueOnce([
      systemDefault,
      kindDrifted,
    ] as never);

    await expect(
      resolveActiveTemplate({ doctorId: 'doc1', encounterType: 'cardiology' }),
    ).resolves.toBe(systemDefault);
    expect(prisma.user.findUnique).not.toHaveBeenCalled();
    expect(rolloutMocks.pin).not.toHaveBeenCalled();
  });

  it('rejects a pinned legacy Twin without current source admission', async () => {
    const admitted = admittedTwin({
      id: 'twin-legacy-pinned',
      doctorId: 'doc1',
      encounterType: 'cardiology',
    });
    const legacy = {
      ...admitted,
      templateTwinCompiledVersion: {
        ...admitted.templateTwinCompiledVersion,
        sourceArtifact: {
          ...admitted.templateTwinCompiledVersion.sourceArtifact,
          quarantineArtifact: null,
        },
      },
    };
    vi.mocked(prisma.noteTemplate.findFirst).mockResolvedValueOnce(
      legacy as never,
    );

    await expect(
      resolveVisitTemplate({
        doctorId: 'doc1',
        pinnedTemplateId: legacy.id,
        pinnedTemplateVersion: legacy.version,
      }),
    ).rejects.toBeInstanceOf(PinnedTemplateUnavailableError);
    expect(prisma.user.findUnique).not.toHaveBeenCalled();
    expect(rolloutMocks.pin).not.toHaveBeenCalled();
  });

  it('rejects a pinned kind-drifted template that retains compiled lineage', async () => {
    const compiled = admittedTwin({
      id: 'kind-drift-pinned',
      doctorId: 'doc1',
    });
    const kindDrifted = { ...compiled, templateKind: 'structured' };
    vi.mocked(prisma.noteTemplate.findFirst).mockResolvedValueOnce(
      kindDrifted as never,
    );

    await expect(
      resolveVisitTemplate({
        doctorId: 'doc1',
        pinnedTemplateId: kindDrifted.id,
        pinnedTemplateVersion: kindDrifted.version,
      }),
    ).rejects.toBeInstanceOf(PinnedTemplateUnavailableError);
    expect(prisma.user.findUnique).not.toHaveBeenCalled();
    expect(rolloutMocks.pin).not.toHaveBeenCalled();
  });

  it('returns the exact persisted rollout token with a worker Twin selection', async () => {
    const twin = admittedTwin({
      id: 'twin-admission-token',
      doctorId: 'doc1',
      encounterType: 'cardiology',
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
    const twin = admittedTwin({
      id: 'twin-db-disabled-active',
      doctorId: 'doc1',
      encounterType: 'cardiology',
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
    const twin = admittedTwin({
      id: 'twin-disabled-active',
      doctorId: 'doc1',
      encounterType: 'cardiology',
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

  it('server-filters active and pinned Twin rows in rollback compatibility mode', async () => {
    process.env.TEMPLATE_TWIN_RUNTIME_MODE = 'rollback-compat-v2';
    const structured = tmpl({
      id: 'structured-bridge-active',
      doctorId: 'doc1',
      encounterType: null,
      templateKind: 'structured',
    });
    vi.mocked(prisma.noteTemplate.findMany).mockResolvedValueOnce([
      systemDefault,
      structured,
    ]);

    await expect(
      resolveActiveTemplate({ doctorId: 'doc1', encounterType: 'cardiology' }),
    ).resolves.toBe(structured);
    expect(prisma.noteTemplate.findMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          templateKind: { not: 'template_twin_docx' },
        }),
      }),
    );
    expect(prisma.user.findUnique).not.toHaveBeenCalled();
    expect(rolloutMocks.pin).not.toHaveBeenCalled();

    vi.mocked(prisma.noteTemplate.findFirst).mockResolvedValueOnce(null);
    await expect(
      resolveVisitTemplate({
        doctorId: 'doc1',
        pinnedTemplateId: 'twin-v1',
        pinnedTemplateVersion: 1,
      }),
    ).rejects.toBeInstanceOf(PinnedTemplateUnavailableError);
    expect(prisma.noteTemplate.findFirst).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          templateKind: { not: 'template_twin_docx' },
        }),
      }),
    );
  });

  it('fails closed when a pin is partial or unavailable', async () => {
    await expect(
      resolveVisitTemplate({
        doctorId: 'doc1',
        pinnedTemplateId: 'twin-v1',
        pinnedTemplateVersion: null,
      }),
    ).rejects.toBeInstanceOf(PinnedTemplateUnavailableError);

    vi.mocked(prisma.noteTemplate.findFirst).mockResolvedValueOnce(null);
    await expect(
      resolveVisitTemplate({
        doctorId: 'doc1',
        pinnedTemplateId: 'twin-v1',
        pinnedTemplateVersion: 1,
      }),
    ).rejects.toBeInstanceOf(PinnedTemplateUnavailableError);
  });
});
