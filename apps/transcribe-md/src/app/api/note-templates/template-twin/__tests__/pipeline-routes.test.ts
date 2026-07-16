import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  requireDoctorSession: vi.fn(),
  createDraft: vi.fn(),
  updateMappings: vi.fn(),
  runSyntheticTest: vi.fn(),
  certify: vi.fn(),
}));

vi.mock('next/server', () => {
  class FakeNextResponse {
    status: number;
    headers: Headers;
    private readonly payload: unknown;

    constructor(
      payload: unknown,
      init?: { status?: number; headers?: Record<string, string> },
    ) {
      this.payload = payload;
      this.status = init?.status ?? 200;
      this.headers = new Headers(init?.headers);
    }

    async json() {
      return this.payload;
    }

    static json(
      payload: unknown,
      init?: { status?: number; headers?: Record<string, string> },
    ) {
      return new FakeNextResponse(payload, init);
    }
  }
  return { NextResponse: FakeNextResponse };
});

vi.mock('@/lib/auth', () => ({
  AuthError: class AuthError extends Error {
    constructor(
      public readonly code: 'UNAUTHENTICATED' | 'FORBIDDEN',
      message: string,
    ) {
      super(message);
    }
  },
  requireDoctorSession: mocks.requireDoctorSession,
}));
vi.mock('@/lib/template-twin/request-security', () => ({
  isSameOriginTemplateTwinMutation: () => true,
  boundedMultipartFormData: (request: Request) => request.formData(),
  isMultipartFile: (value: unknown) => value instanceof File,
  TemplateTwinMultipartError: class TemplateTwinMultipartError extends Error {
    code = 'MULTIPART_INVALID';
  },
}));
vi.mock('@/lib/template-twin/create-draft', () => ({
  TemplateTwinDraftError: class TemplateTwinDraftError extends Error {
    code = 'PERSISTENCE_FAILED';
  },
  createTemplateTwinDraft: mocks.createDraft,
}));
vi.mock('@/lib/template-twin/certification-lifecycle', () => ({
  TemplateTwinLifecycleError: class TemplateTwinLifecycleError extends Error {
    code = 'CONFLICT';
  },
  updateTemplateTwinMappings: mocks.updateMappings,
  certifyAndActivateTemplateTwin: mocks.certify,
}));
vi.mock('@/lib/template-twin/synthetic-test', () => ({
  TemplateTwinSyntheticTestError: class TemplateTwinSyntheticTestError extends Error {
    code = 'CONFLICT';
  },
  runTemplateTwinSyntheticTest: mocks.runSyntheticTest,
}));
vi.mock('@/lib/template-twin/source-phi', () => ({
  TemplateTwinPhiRejectedError: class TemplateTwinPhiRejectedError extends Error {},
  TemplateTwinPhiScanUnavailableError: class TemplateTwinPhiScanUnavailableError extends Error {},
  TemplateTwinSourcePrivacyUnsupportedError: class TemplateTwinSourcePrivacyUnsupportedError extends Error {},
}));
vi.mock('@/lib/template-twin/storage', () => ({
  TemplateTwinArtifactTooLargeError: class TemplateTwinArtifactTooLargeError extends Error {},
  TemplateTwinArtifactIntegrityError: class TemplateTwinArtifactIntegrityError extends Error {},
  TemplateTwinStorageUnavailableError: class TemplateTwinStorageUnavailableError extends Error {},
}));
vi.mock('@/lib/note-template-docx', () => ({
  TemplateDocxError: class TemplateDocxError extends Error {
    code = 'XML_INVALID';
  },
}));

import { POST as upload } from '../upload/route';
import { POST as certify } from '../[id]/certify/route';
import { PATCH as updateMappings } from '../[id]/mappings/route';
import { POST as runSyntheticTest } from '../[id]/synthetic-test/route';
import { AuthError } from '@/lib/auth';
import { canonicalSha256 } from '@/lib/template-twin/canonical';

const HASH = 'a'.repeat(64);
const EMPTY_FIELD_INTENTS_SHA256 = canonicalSha256([]);
const FIELD_ID = `ttf_${'b'.repeat(24)}`;
const SESSION = {
  templateTwinRolloutToken: {
    practiceId: 'practice-synthetic-1',
    globalGeneration: BigInt(2),
    practiceGeneration: BigInt(4),
  },
  user: {
    id: 'doctor-synthetic-1',
    email: 'doctor@synthetic.test',
    practiceId: 'practice-synthetic-1',
  },
};
const ACTOR = {
  userId: SESSION.user.id,
  userEmail: SESSION.user.email,
  practiceId: SESSION.user.practiceId,
  rolloutToken: SESSION.templateTwinRolloutToken,
};
const WORKSPACE = {
  template: { id: 'template-synthetic-1' },
  mappingsSha256: HASH,
};

function jsonRequest(body: unknown): Request {
  return {
    headers: new Headers(),
    json: async () => body,
  } as unknown as Request;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireDoctorSession.mockResolvedValue(SESSION);
  mocks.createDraft.mockResolvedValue({
    noteTemplateId: 'template-synthetic-1',
  });
  mocks.updateMappings.mockResolvedValue(WORKSPACE);
  mocks.runSyntheticTest.mockResolvedValue(WORKSPACE);
  mocks.certify.mockResolvedValue({
    ...WORKSPACE,
    template: { id: 'template-synthetic-1', status: 'active' },
  });
});

describe('Template Twin route orchestration', () => {
  it.each(['STAFF', 'ADMIN'] as const)(
    'rejects a fresh %s role across upload, mapping, synthetic test, and certification',
    async (role) => {
      mocks.requireDoctorSession.mockRejectedValue(
        new AuthError(
          'FORBIDDEN',
          `Synthetic ${role} is not authorized for Template Twin.`,
        ),
      );
      const params = {
        params: Promise.resolve({ id: 'template-synthetic-1' }),
      };

      const responses = await Promise.all([
        upload({ headers: new Headers() } as unknown as Request),
        updateMappings(jsonRequest({}), params),
        runSyntheticTest(jsonRequest({}), params),
        certify(jsonRequest({}), params),
      ]);

      expect(responses.map((item) => item.status)).toEqual([403, 403, 403, 403]);
      expect(mocks.createDraft).not.toHaveBeenCalled();
      expect(mocks.updateMappings).not.toHaveBeenCalled();
      expect(mocks.runSyntheticTest).not.toHaveBeenCalled();
      expect(mocks.certify).not.toHaveBeenCalled();
    },
  );

  it('preserves actor, template, mapping hash, and acknowledgements through the full flow', async () => {
    const form = new FormData();
    form.set(
      'file',
      new File([Buffer.from('PK\u0003\u0004synthetic-docx')], 'synthetic-template.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      }),
    );
    form.set('templateName', 'Synthetic musculoskeletal intake');
    form.set('encounterScope', 'Musculoskeletal initial visit');
    form.set('versionDescription', 'Initial synthetic QA version');
    const uploadResponse = await upload({
      headers: new Headers(),
      formData: async () => form,
    } as unknown as Request);
    expect(uploadResponse.status).toBe(201);
    expect(await uploadResponse.json()).toEqual({
      ok: true,
      certificationUrl:
        '/settings/note-format/template-synthetic-1/certify',
    });
    expect(mocks.createDraft).toHaveBeenCalledWith({
      source: expect.any(Uint8Array),
      actor: ACTOR,
      identity: {
        name: 'Synthetic musculoskeletal intake',
        encounterType: 'Musculoskeletal initial visit',
        versionDescription: 'Initial synthetic QA version',
      },
    });

    const mapping = {
      fieldId: FIELD_ID,
      clinicalConcept: 'chief_complaint',
      expectedDataType: 'text',
      polarityBehavior: 'value_only',
      temporality: 'any',
      laterality: 'not_applicable',
      unitPolicy: 'not_applicable',
      approvedSynonyms: [],
      required: true,
      blankPolicy: 'requires_input',
      unknownPolicy: 'requires_input',
      practiceDefault: null,
      status: 'certified',
    };
    const mappingsResponse = await updateMappings(
      jsonRequest({
        expectedMappingsSha256: HASH,
        expectedFieldIntentsSha256: EMPTY_FIELD_INTENTS_SHA256,
        mappings: [mapping],
        fieldIntents: [],
      }),
      { params: Promise.resolve({ id: 'template-synthetic-1' }) },
    );
    expect(mappingsResponse.status).toBe(200);
    expect(mocks.updateMappings).toHaveBeenCalledWith({
      noteTemplateId: 'template-synthetic-1',
      actor: ACTOR,
      expectedMappingsSha256: HASH,
      expectedFieldIntentsSha256: EMPTY_FIELD_INTENTS_SHA256,
      mappings: [mapping],
      fieldIntents: [],
    });

    const syntheticResponse = await runSyntheticTest(
      jsonRequest({
        expectedMappingsSha256: HASH,
        expectedFieldIntentsSha256: EMPTY_FIELD_INTENTS_SHA256,
        encounterText: 'Synthetic encounter evidence only.',
      }),
      { params: Promise.resolve({ id: 'template-synthetic-1' }) },
    );
    expect(syntheticResponse.status).toBe(200);
    expect(mocks.runSyntheticTest).toHaveBeenCalledWith({
      noteTemplateId: 'template-synthetic-1',
      actor: ACTOR,
      expectedMappingsSha256: HASH,
      expectedFieldIntentsSha256: EMPTY_FIELD_INTENTS_SHA256,
      encounterText: 'Synthetic encounter evidence only.',
    });

    const certifyResponse = await certify(
      jsonRequest({
        expectedMappingsSha256: HASH,
        expectedFieldIntentsSha256: EMPTY_FIELD_INTENTS_SHA256,
        expectedSyntheticTestProvenanceSha256: HASH,
        acknowledgeStructure: true,
        acknowledgeSyntheticOutput: true,
      }),
      { params: Promise.resolve({ id: 'template-synthetic-1' }) },
    );
    expect(certifyResponse.status).toBe(200);
    expect(mocks.certify).toHaveBeenCalledWith({
      noteTemplateId: 'template-synthetic-1',
      actor: ACTOR,
      expectedMappingsSha256: HASH,
      expectedFieldIntentsSha256: EMPTY_FIELD_INTENTS_SHA256,
      expectedSyntheticTestProvenanceSha256: HASH,
      optionalFieldWaivers: [],
    });

    expect(mocks.createDraft.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.updateMappings.mock.invocationCallOrder[0]!,
    );
    expect(mocks.updateMappings.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.runSyntheticTest.mock.invocationCallOrder[0]!,
    );
    expect(mocks.runSyntheticTest.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.certify.mock.invocationCallOrder[0]!,
    );
  });

  it('rejects an upload without physician-readable identity and scope', async () => {
    const form = new FormData();
    form.set(
      'file',
      new File([Buffer.from('PK\u0003\u0004synthetic-docx')], 'synthetic-template.docx', {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      }),
    );

    const response = await upload({
      headers: new Headers(),
      formData: async () => form,
    } as unknown as Request);

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({
      ok: false,
      error: 'Name the template, choose its visit scope, and describe this version.',
    });
    expect(mocks.createDraft).not.toHaveBeenCalled();
  });

  it('rejects certification without the exact synthetic-test provenance acknowledgement', async () => {
    const response = await certify(
      jsonRequest({
        expectedMappingsSha256: HASH,
        expectedFieldIntentsSha256: EMPTY_FIELD_INTENTS_SHA256,
        acknowledgeStructure: true,
        acknowledgeSyntheticOutput: true,
      }),
      { params: Promise.resolve({ id: 'template-synthetic-1' }) },
    );

    expect(response.status).toBe(400);
    expect(mocks.certify).not.toHaveBeenCalled();
  });
});
