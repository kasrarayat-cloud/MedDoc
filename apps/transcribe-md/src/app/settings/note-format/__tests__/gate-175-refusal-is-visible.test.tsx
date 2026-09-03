// ============================================================================
// ruling 175(2)(b) — A REFUSAL THE DOCTOR CANNOT ACT ON IS NOT FAIL-CLOSED.
//
// ⚠️ WRITTEN "ruling 175" RATHER THAN THE USUAL "#175" ON PURPOSE. This file
// sits inside the templates surface that `gate-c1f-templates` watches for
// colour literals, and `#175` is three hex digits — the gate correctly refused
// it. Teaching the gate to tell a ruling number from a colour would be exactly
// the semantic judgement this arc spent nine rulings learning not to add, so
// the spelling moves instead. The gate is right; the citation is cheaper.
// ----------------------------------------------------------------------------
// ⚠️ THE COMPILER'S COMMENT CLAIMED THIS FOR A WHILE BEFORE IT WAS TRUE. It
// said a refused control is "visible to the doctor as a per-field finding". It
// was not: the compiler built the finding — the control's LABEL, the REASON,
// the XPath — all of it reached the browser, and the UI rendered a COUNT.
//
// A doctor was told "N elements can't be safely reproduced — simplify the
// template in Word and re-upload", with no way to learn WHICH control. One
// refusal disables certification for a 28- or 35-control form.
//
// ⚠️ AND IT CANNOT COME FROM THE FIELD LIST. A refused control is deliberately
// absent from `ir.fields` — that absence IS the refusal — so the findings are
// listed from `unsupported`. That is precisely why the count was all the old
// chrome could reach, and why "just render the fields" would have been wrong.
// ============================================================================
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import type { TemplateTwinWorkspace } from '@/lib/template-twin/client-types';

const h = vi.hoisted(() => ({
  open: vi.fn(),
  update: vi.fn(),
  upload: vi.fn(),
  certify: vi.fn(),
}));
vi.mock('@/actions/template-twin-mappings', () => ({
  openNativeTemplateWorkspaceAction: h.open,
  updateTemplateTwinMappingsAction: h.update,
}));
vi.mock('@/actions/template-twin-certify', () => ({
  uploadNativeTemplateAction: h.upload,
  certifyNativeTemplateAction: h.certify,
}));

import { NativeTemplateManager } from '../native-template-manager';

const REFUSALS = [
  {
    code: 'UNSUPPORTED_CONTROL_STRUCTURE',
    partName: 'word/document.xml',
    path: '/w:document[0]/w:body[0]/w:p[8]/w:sdt[0]',
    label: 'Anticoagulation',
    detail:
      'Unsupported control structure: the control declares more than one w:sdtContent. ' +
      'The text stays exactly as written; this control will not be filled automatically.',
    clinicallyMaterial: true,
    blocksCertification: true,
  },
  {
    code: 'UNSUPPORTED_CONTROL_STRUCTURE',
    partName: 'word/document.xml',
    path: '/w:document[0]/w:body[0]/w:p[12]/w:sdt[0]',
    label: null,
    detail: 'Unsupported control structure: a w:rPr block contains a w:sym.',
    clinicallyMaterial: true,
    blocksCertification: true,
  },
];

function workspace(unsupported: unknown[]): TemplateTwinWorkspace {
  return {
    template: {
      id: 'nt_1',
      lineageId: 'lin_1',
      version: 1,
      name: 'WM IOV',
      encounterType: 'ultrasound',
      status: 'draft',
      certificationStatus: 'unsupported',
    },
    source: {
      sha256: 'a'.repeat(64),
      sizeBytes: 1,
      mimeType:
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      compiledAtIso: '2026-09-03T00:00:00.000Z',
      compilerVersion: '1',
    },
    stats: { dropdowns: 0, tables: 0 } as TemplateTwinWorkspace['stats'],
    // ⚠️ ONE SURVIVING FIELD, deliberately: the refused controls are NOT here,
    // so an implementation that listed findings from `fields` would render
    // nothing and this arm would catch it.
    fields: [
      {
        definitionId: 'def_0',
        field: {
          fieldId: `ttf_${'0'.repeat(23)}1`,
          originalLabel: 'Impression',
          kind: 'content_control',
          detectionStatus: 'needs_confirmation',
        },
        mapping: {
          sourceType: 'extraction',
          clinicalConcept: null,
          expectedDataType: 'text',
          polarityBehavior: 'value_only',
          temporality: null,
          laterality: null,
          unitPolicy: null,
          approvedSynonyms: [],
          required: false,
          blankPolicy: 'blank',
          unknownPolicy: 'blank',
          practiceDefault: null,
          status: 'needs_confirmation',
          fieldId: `ttf_${'0'.repeat(23)}1`,
        },
      },
    ] as unknown as TemplateTwinWorkspace['fields'],
    unsupported: unsupported as TemplateTwinWorkspace['unsupported'],
    mappingsSha256: 'sha',
    latestSyntheticTest: null,
    canEdit: true,
  } as TemplateTwinWorkspace;
}

const LIST = [
  {
    noteTemplateId: 'nt_1',
    name: 'WM IOV',
    certificationStatus: 'unsupported',
    fieldCount: 1,
    version: 1,
  },
];

beforeEach(() => vi.clearAllMocks());

const FIELD_ID = `ttf_${'0'.repeat(23)}1`;

async function openWorkspace(unsupported: unknown[]) {
  h.open.mockResolvedValue({ ok: true, data: workspace(unsupported) });
  render(<NativeTemplateManager existing={LIST} showUpload />);
  fireEvent.click(await screen.findByTestId('twin-open-workspace-nt_1'));
  // wait for the workspace itself, so a missing findings block is a real
  // absence rather than a not-yet-rendered one.
  await screen.findByTestId(`twin-field-row-${FIELD_ID}`);
}

describe('ruling 175(2)(b) — each refused control names itself', () => {
  it('⚠️ THE LABEL AND THE REASON ARE RENDERED, not just a count', async () => {
    await openWorkspace(REFUSALS);
    const list = await screen.findByTestId('twin-unsupported-findings');
    const rows = screen.getAllByTestId('twin-unsupported-finding');
    expect(rows.length, 'one row per refused control').toBe(2);
    expect(list.textContent).toContain('Anticoagulation');
    expect(list.textContent).toContain('more than one w:sdtContent');
    expect(list.textContent).toContain('a w:rPr block contains a w:sym');
    // the actionable instruction, per control
    expect(list.textContent).toContain('Simplify this control in Word');
    // an unnamed control still gets a row rather than vanishing
    expect(list.textContent).toContain('Unnamed control');
  });

  it('⚠️ NON-VACUITY — with no refusals the block is absent entirely', async () => {
    // Without this, an implementation that always rendered the chrome would
    // satisfy the arm above, and a doctor with a clean template would be shown
    // a refusal list with nothing in it.
    await openWorkspace([]);
    expect(screen.queryByTestId('twin-unsupported-findings')).toBeNull();
  });

  it('a NON-blocking unsupported entry is not listed as a blocker', async () => {
    await openWorkspace([{ ...REFUSALS[0], blocksCertification: false }]);
    expect(screen.queryByTestId('twin-unsupported-findings')).toBeNull();
  });
});
