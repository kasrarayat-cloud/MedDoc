import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  refresh: vi.fn(),
  push: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: mocks.refresh, push: mocks.push }),
}));

vi.mock('sonner', () => ({
  toast: { success: mocks.toastSuccess, error: vi.fn() },
}));

import { TemplateTwinReview } from '../template-twin-review';
import {
  serializeTemplateTwinReview,
  type TemplateTwinReviewData,
  type TemplateTwinReviewField,
  type TemplateTwinReviewRow,
} from '../template-twin-review-data';

const FIELD_ID = `ttf_${'a'.repeat(24)}`;
const FACT_ID = `ttfact_${'b'.repeat(24)}`;

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function reviewField(
  overrides: Partial<TemplateTwinReviewField>,
): TemplateTwinReviewField {
  return {
    definitionId: 'definition-1',
    fieldId: FIELD_ID,
    displayOrder: 0,
    originalLabel: 'Synthetic symptom severity',
    fieldKind: 'single_select',
    criticality: 'number_unit',
    required: false,
    allowedOptions: [
      { ordinal: 0, displayText: 'Mild', value: 'Mild' },
      { ordinal: 1, displayText: 'Moderate', value: 'Moderate' },
      { ordinal: 2, displayText: 'Severe', value: 'Severe' },
    ],
    rowPrototype: false,
    status: 'verified',
    resolutionStatus: 'supported',
    value: 'Moderate',
    selectedOptionOrdinal: 1,
    reasonCode: 'exact_option_supported',
    clinicianReviewed: false,
    evidence: [
      {
        factId: FACT_ID,
        quote: 'The synthetic symptom is moderate today.',
        audioTimestampSeconds: 74,
        speaker: 'Clinician',
        evidenceAnchorIds: ['anchor-synthetic-1'],
      },
    ],
    validationIssues: [],
    ...overrides,
  };
}

function reviewData(): TemplateTwinReviewData {
  return {
    fillManifestId: 'fill-synthetic-1',
    manifestVersion: 1,
    manifestSha256: 'e'.repeat(64),
    templateName: 'Synthetic clinic template',
    templateVersion: 3,
    processingStatus: 'review_required',
    roundTripVerified: true,
    physicianReviewConfirmed: false,
    layoutWarningCodes: [],
    dataIntegrityError: false,
    counts: {
      filled: 2,
      needsReview: 2,
      notMentioned: 1,
      conflicts: 1,
      criticalUnresolved: 1,
    },
    fields: [
      reviewField({}),
      reviewField({
        definitionId: 'definition-2',
        fieldId: `ttf_${'c'.repeat(24)}`,
        displayOrder: 1,
        originalLabel: 'Synthetic allergy',
        fieldKind: 'narrative_text',
        criticality: 'allergy',
        allowedOptions: [],
        status: 'conflict',
        resolutionStatus: 'conflict',
        value: null,
        selectedOptionOrdinal: null,
        reasonCode: 'source_evidence_conflict',
        evidence: [
          {
            factId: `ttfact_${'d'.repeat(24)}`,
            quote: 'The synthetic sources disagree about the allergy.',
            audioTimestampSeconds: null,
            speaker: null,
            evidenceAnchorIds: ['anchor-synthetic-2'],
          },
        ],
      }),
      reviewField({
        definitionId: 'definition-3',
        fieldId: `ttf_${'e'.repeat(24)}`,
        displayOrder: 2,
        originalLabel: 'Synthetic laterality',
        fieldKind: 'single_select',
        criticality: 'laterality',
        allowedOptions: [
          { ordinal: 0, displayText: 'Left', value: 'Left' },
          { ordinal: 1, displayText: 'Right', value: 'Right' },
        ],
        status: 'not_mentioned',
        resolutionStatus: 'not_mentioned',
        value: null,
        selectedOptionOrdinal: null,
        reasonCode: 'fact_not_mentioned',
        evidence: [],
      }),
      reviewField({
        definitionId: 'definition-4',
        fieldId: `ttf_${'f'.repeat(24)}`,
        displayOrder: 3,
        originalLabel: 'Synthetic measurement',
        fieldKind: 'measurement',
        criticality: 'number_unit',
        allowedOptions: [],
        status: 'needs_review',
        resolutionStatus: 'needs_clinician_input',
        value: null,
        selectedOptionOrdinal: null,
        reasonCode: 'measurement_unit_missing',
        evidence: [],
      }),
    ],
  };
}

function successfulCorrectionFetch() {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      ok: true,
      result: { certificationUrl: null },
    }),
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function onlyField(
  overrides: Partial<TemplateTwinReviewField>,
): TemplateTwinReviewData {
  const data = reviewData();
  data.fields = [reviewField(overrides)];
  data.counts = {
    filled: data.fields[0]?.value === null ? 0 : 1,
    needsReview: 1,
    notMentioned: 0,
    conflicts: 0,
    criticalUnresolved: 0,
  };
  return data;
}

describe('TemplateTwinReview', () => {
  it('shows review counts and prioritizes critical conflicts', () => {
    render(<TemplateTwinReview data={reviewData()} visitId="visit-synthetic-1" />);

    expect(screen.getByText('Fields filled')).toBeInTheDocument();
    expect(screen.getByText('Need review')).toBeInTheDocument();
    expect(screen.getAllByText('Not mentioned').length).toBeGreaterThan(0);
    expect(screen.getByText('Conflicts')).toBeInTheDocument();
    expect(
      screen.getByText('1 critical field requires clinician review before signing.'),
    ).toBeInTheDocument();

    const fieldList = screen.getByRole('list', { name: 'Template fields' });
    const fieldButtons = within(fieldList).getAllByRole('button');
    expect(fieldButtons[0]).toHaveTextContent('Synthetic allergy');
    expect(screen.getByText('Why this needs review')).toBeInTheDocument();
    expect(
      screen.getByText('The encounter contains conflicting evidence for this field.'),
    ).toBeInTheDocument();
  });

  it('shows exact dropdown options, supporting quote, and audio timestamp', () => {
    render(<TemplateTwinReview data={reviewData()} visitId="visit-synthetic-1" />);

    fireEvent.click(screen.getByRole('button', { name: /Synthetic symptom severity/ }));

    expect(screen.getByText('Moderate · selected')).toBeInTheDocument();
    expect(screen.getByText('Mild')).toBeInTheDocument();
    expect(screen.getByText('Severe')).toBeInTheDocument();
    expect(
      screen.getByText('“The synthetic symptom is moderate today.”'),
    ).toBeInTheDocument();
    expect(screen.getByText('Audio 1:14')).toBeInTheDocument();
  });

  it('surfaces deterministic Word layout-risk warnings before signing', () => {
    const data = reviewData();
    data.layoutWarningCodes = ['LAYOUT_OVERFLOW_REVIEW_RECOMMENDED'];
    render(<TemplateTwinReview data={data} visitId="visit-synthetic-1" />);

    expect(
      screen.getByText(/Word layout review is required/),
    ).toBeInTheDocument();
  });

  it('filters the list to fields that need attention', () => {
    render(<TemplateTwinReview data={reviewData()} visitId="visit-synthetic-1" />);

    fireEvent.click(screen.getByRole('checkbox', { name: /Needs attention/ }));

    expect(screen.queryByText('Synthetic symptom severity')).not.toBeInTheDocument();
    expect(screen.queryByText('Synthetic laterality')).not.toBeInTheDocument();
    const filteredList = screen.getByRole('list', { name: 'Template fields' });
    expect(within(filteredList).getByText('Synthetic allergy')).toBeInTheDocument();
    expect(within(filteredList).getByText('Synthetic measurement')).toBeInTheDocument();
  });

  it('requires an explicit whole-document acknowledgement for the exact manifest', async () => {
    const data = onlyField({ status: 'verified', validationIssues: [] });
    data.counts.needsReview = 0;
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<TemplateTwinReview data={data} visitId="visit-synthetic-1" />);

    fireEvent.click(
      screen.getByRole('button', { name: 'I reviewed every Template Twin field' }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/visits/visit-synthetic-1/template-twin/review',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          expectedManifestVersion: 1,
          expectedManifestSha256: 'e'.repeat(64),
        }),
      }),
    );
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      'Original Template DOCX review confirmed',
    );
    expect(mocks.refresh).toHaveBeenCalledTimes(1);
  });

  it('submits an exact dropdown correction with optimistic version and evidence IDs', async () => {
    const fetchMock = successfulCorrectionFetch();
    render(<TemplateTwinReview data={reviewData()} visitId="visit-synthetic-1" />);
    fireEvent.click(screen.getByRole('button', { name: /Synthetic symptom severity/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Correct this field' }));
    fireEvent.change(screen.getByLabelText('Exact dropdown option'), {
      target: { value: 'Severe' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save and verify correction' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(request.body))).toEqual({
      expectedManifestVersion: 1,
      fieldId: FIELD_ID,
      value: 'Severe',
      sourceFactIds: [FACT_ID],
      reasonCode: 'selected_exact_option',
      createMappingRule: false,
    });
    expect(mocks.refresh).toHaveBeenCalledTimes(1);
  });

  it('uses exact option checkboxes for multi-select corrections', async () => {
    const fetchMock = successfulCorrectionFetch();
    const data = onlyField({
      fieldKind: 'multi_select',
      value: null,
      evidence: [],
      selectedOptionOrdinal: null,
      status: 'needs_review',
    });
    render(<TemplateTwinReview data={data} visitId="visit-synthetic-1" />);
    fireEvent.click(screen.getByRole('button', { name: 'Correct this field' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Mild' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Severe' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save and verify correction' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(request.body)).value).toEqual(['Mild', 'Severe']);
  });

  it.each([
    ['narrative_text', 'Corrected value'],
    ['date', 'Date'],
    ['number', 'Finite number'],
    ['measurement', 'Number and stated unit'],
    ['checkbox', 'Checkbox state'],
  ] as const)('renders the constrained %s correction control', (fieldKind, label) => {
    const data = onlyField({
      fieldKind,
      rowPrototype: false,
      allowedOptions: [],
      value: null,
      evidence: [],
      selectedOptionOrdinal: null,
      status: 'needs_review',
    });
    render(<TemplateTwinReview data={data} visitId="visit-synthetic-1" />);
    fireEvent.click(screen.getByRole('button', { name: 'Correct this field' }));
    expect(screen.getByLabelText(label)).toBeInTheDocument();
  });

  it('submits repeating numeric table rows as explicit value records', async () => {
    const fetchMock = successfulCorrectionFetch();
    const data = onlyField({
      fieldKind: 'number',
      rowPrototype: true,
      allowedOptions: [],
      value: [{ value: '11', sourceFactId: null }],
      evidence: [],
      selectedOptionOrdinal: null,
      status: 'needs_review',
    });
    render(<TemplateTwinReview data={data} visitId="visit-synthetic-1" />);
    fireEvent.click(screen.getByRole('button', { name: 'Correct this field' }));
    fireEvent.change(screen.getByLabelText('Repeating table row values'), {
      target: { value: '12\n13.5' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save and verify correction' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(request.body)).value).toEqual([
      { value: '12' },
      { value: '13.5' },
    ]);
  });
});

describe('serializeTemplateTwinReview', () => {
  function row(fillManifest: unknown): TemplateTwinReviewRow {
    return {
      id: 'fill-synthetic-1',
      status: 'REVIEW_REQUIRED',
      manifestVersion: 1,
      manifestSha256: 'e'.repeat(64),
      fillManifest,
      filledCount: 1,
      needsReviewCount: 0,
      notMentionedCount: 0,
      conflictCount: 0,
      criticalUnresolvedCount: 0,
      roundTripVerified: true,
      reviewedAt: null,
      reviewedManifestVersion: null,
      reviewedManifestSha256: null,
      compiledVersion: {
        noteTemplate: { name: 'Synthetic clinic template' },
        fields: [
          {
            id: 'definition-1',
            fieldId: FIELD_ID,
            displayOrder: 0,
            originalLabel: 'Synthetic symptom severity',
            fieldKind: 'single_select',
            allowedOptions: [
              { ordinal: 0, displayText: 'Mild', value: 'Mild' },
              { ordinal: 1, displayText: 'Moderate', value: 'Moderate' },
            ],
            rendererBinding: {
              partName: 'word/document.xml',
              bindingType: 'content_control',
              path: '/document/body/sdt[0]',
              canonicalPath: '/document/body/sdt[0]',
              ordinal: 0,
              sdtId: '1',
              tag: 'synthetic_severity',
              alias: null,
              legacyName: null,
              tableIndex: null,
              rowIndex: null,
              cellIndex: null,
              repeatAncestorPath: null,
              canonicalRepeatAncestorPath: null,
              sourceControlSha256: 'c'.repeat(64),
              sourceBindingIdentitySha256: 'c'.repeat(64),
              certifiedBindingSha256: 'c'.repeat(64),
              originalContentSha256: 'd'.repeat(64),
            },
            criticality: 'number_unit',
            required: false,
          },
        ],
      },
    };
  }

  it('joins only referenced evidence into the client review DTO', () => {
    const serialized = serializeTemplateTwinReview(
      row({
        manifestVersion: 1,
        soapVersion: 4,
        soapSha256: 'a'.repeat(64),
        compiledVersionId: 'compiled-synthetic-1',
        noteTemplateId: 'template-synthetic-1',
        noteTemplateVersion: 3,
        compilerVersion: 'template-docx-compiler/1.0.0',
        resolverVersion: 'template-field-resolver/1.0.0',
        resolverModelVersion: null,
        rendererVersion: 'template-docx-renderer/1.0.0',
        facts: [
          {
            factId: FACT_ID,
            concept: 'symptom.severity',
            value: 'Moderate',
            polarity: 'affirmed',
            temporality: 'current',
            experiencer: 'patient',
            laterality: 'not_applicable',
            number: null,
            unit: null,
            speaker: 'Clinician',
            sourceTranscriptOffsets: { start: 0, end: 43 },
            audioTimestampSeconds: 74,
            evidenceAnchorIds: ['anchor-synthetic-1'],
            evidenceQuote: 'The synthetic symptom is moderate today.',
            quality: { asr: 'high', evidence: 'direct' },
          },
        ],
        fields: [
          {
            fieldId: FIELD_ID,
            status: 'supported',
            value: 'Moderate',
            sourceFactIds: [FACT_ID],
            evidenceAnchorIds: ['anchor-synthetic-1'],
            selectedOptionOrdinal: 1,
            reasonCode: 'exact_option_supported',
            clinicianReviewed: false,
          },
        ],
        validation: {
          valid: true,
          issues: [],
          checkedAt: '2026-07-15T12:00:00.000Z',
          validatorVersion: 'template-field-validator/1.0.0',
        },
        counts: {
          filled: 1,
          needsReview: 0,
          notMentioned: 0,
          conflicts: 0,
          criticalUnresolved: 0,
        },
      }),
    );

    expect(serialized?.templateVersion).toBe(3);
    expect(serialized?.manifestSha256).toBe('e'.repeat(64));
    expect(serialized?.fields[0]?.evidence).toEqual([
      expect.objectContaining({
        quote: 'The synthetic symptom is moderate today.',
        audioTimestampSeconds: 74,
      }),
    ]);
    expect(serialized?.fields[0]?.allowedOptions).toHaveLength(2);
  });

  it('surfaces an invalid manifest as a critical integrity state', () => {
    const serialized = serializeTemplateTwinReview(row({ malformed: true }));

    expect(serialized).toMatchObject({
      dataIntegrityError: true,
      roundTripVerified: false,
      counts: { needsReview: 1, criticalUnresolved: 1 },
      fields: [],
    });
  });

});
