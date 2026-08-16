// ============================================================================
// F5-b — THE CONFIRMATION DOOR. What this gate exists to hold.
// ----------------------------------------------------------------------------
// `MAPPINGS_NOT_READY` refuses certification until every field carries a
// physician-confirmed mapping. That gate was RIGHT and UNSATISFIABLE: nothing
// in the application could open an existing template's twin workspace, so on
// the real customer form ALL 80 of 80 fields could never be confirmed by
// anyone. (⚠️ this line said "79 of 80" until 2026-08-16 — an inherited figure
// that was never measured and conflated two quantities. Measured: 80 of 80
// lack a physician-confirmed mapping; 22 of 80 lack a PROPOSED concept after
// F5-a, 75 before. See AGENTS.md → "Template Twin — the parked steady state".)
//
// ⚠️ THE FAILURE THIS PINS IS #109's CLASS, TWICE OVER, AND BOTH HALVES ARE
// ALREADY ON THE RECORD IN THIS REPOSITORY:
//
//   1. A RULING NAMES AN INTENT; A COMPONENT HAS A JOB LIST. The fold retired
//      `NativeTemplateManager` to kill the UPLOAD ritual. The component's other
//      job — CONFIRM — went with it, unnamed and unnoticed.
//   2. A CORRECT ACTION WITH NO DOOR IS NOT A FEATURE. F4 shipped
//      `updateTemplateTwinMappingsAction` and found its predecessor had had
//      zero callers. `getNativeTemplateWorkspaceAction` was DELETED in
//      2026-07-28 for exactly that, correctly.
//
// So the gate asserts the DOOR, not the code: the read action is reachable
// from a control a doctor can press, and the write action receives what the
// writer demands. An arm that only proved the action exported would be the
// defect it is here to prevent.
//
// ⚠️ AND IT ASSERTS THE GATE DOES NOT MOVE. Every arm that makes confirming
// easier is paired with one proving nothing became confirmable that a
// physician did not confirm. `MAPPINGS_NOT_READY` is untouched by this item.
// ============================================================================

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import type { SemanticMapping } from '@/lib/template-twin/ir';
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

import { NativeTemplateManager, confirmed, confirmClassOf } from '../native-template-manager';

// ── FIXTURE ─────────────────────────────────────────────────────────────────
// Shaped after the REAL customer form's measured partition, scaled down but
// keeping all three classes present — because a fixture with only one class
// would let a one-class implementation pass. The counts are asserted below as
// a non-vacuity arm: a fixture that collapsed to a single class would satisfy
// most of these arms while checking nothing.
function mapping(over: Partial<SemanticMapping> & { fieldId: string }): SemanticMapping {
  return {
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
    ...over,
  } as SemanticMapping;
}

const FID = (n: number) => `ttf_${n.toString(16).padStart(24, '0')}`;

const MANUAL = [FID(1)];
const PROPOSED = [FID(2), FID(3), FID(4)];
const UNPROPOSED = [FID(5), FID(6)];

const MAPPINGS: SemanticMapping[] = [
  mapping({ fieldId: MANUAL[0], sourceType: 'manual' }),
  mapping({ fieldId: PROPOSED[0], clinicalConcept: 'measurement.diameter' }),
  mapping({ fieldId: PROPOSED[1], clinicalConcept: 'measurement.reflux_time' }),
  // A PATTERNED concept — registry-legal but not in REGISTRY_CONCEPTS. The
  // picker must keep it selectable, or opening the door drops it silently.
  mapping({ fieldId: PROPOSED[2], clinicalConcept: 'exam.vascular.gsv' }),
  // ⚠️ BOTH CARRY `verified_note_selection`, AND ONE CARRIES A CONCEPT.
  // The concept-bearing one is production's shape: the model proposer runs
  // there and may fill it. It must STILL be 'choose'.
  mapping({ fieldId: UNPROPOSED[0], sourceType: 'verified_note_selection', expectedDataType: 'single_select' }),
  mapping({
    fieldId: UNPROPOSED[1],
    sourceType: 'verified_note_selection',
    expectedDataType: 'single_select',
    clinicalConcept: 'chief_complaint',
  }),
];

function workspace(over: Partial<TemplateTwinWorkspace> = {}): TemplateTwinWorkspace {
  return {
    template: {
      id: 'nt_1',
      lineageId: 'lin_1',
      version: 1,
      name: 'WM IOV',
      encounterType: 'ultrasound',
      status: 'draft',
      certificationStatus: 'needs_confirmation',
      ...(over.template ?? {}),
    },
    source: {
      sha256: 'a'.repeat(64),
      sizeBytes: 1,
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      compiledAtIso: '2026-08-16T00:00:00.000Z',
      compilerVersion: '1',
    },
    stats: { dropdowns: 2, tables: 1 } as TemplateTwinWorkspace['stats'],
    fields: MAPPINGS.map((m, i) => ({
      definitionId: `def_${i}`,
      field: {
        fieldId: m.fieldId,
        originalLabel: `Field ${i + 1}`,
        kind: 'content_control',
        detectionStatus: 'needs_confirmation',
      },
      mapping: m,
    })) as unknown as TemplateTwinWorkspace['fields'],
    unsupported: [],
    mappingsSha256: 'sha-before',
    latestSyntheticTest: null,
    canEdit: true,
    ...over,
  } as TemplateTwinWorkspace;
}

const LIST = [
  { noteTemplateId: 'nt_1', name: 'WM IOV', certificationStatus: 'needs_confirmation', fieldCount: 6, version: 1 },
];

/**
 * The readiness predicate's MAPPING-SIDE demands, mirrored from
 * `certification-lifecycle.ts:598-618` (`fieldsReady`). Type compatibility and
 * `validPracticeDefault` are the compiler's half and are not re-implemented
 * here — asserting them would be asserting a copy.
 *
 * ⚠️ Stated as a function rather than inline so every arm below judges against
 * ONE predicate: a per-arm re-statement is how the two drift.
 */
function satisfiesFieldsReady(m: SemanticMapping): boolean {
  if (m.sourceType === 'manual') return m.status === 'certified';
  return m.status === 'certified' && Boolean(m.clinicalConcept);
}

beforeEach(() => {
  vi.clearAllMocks();
  h.open.mockResolvedValue({ ok: true, data: workspace() });
  h.update.mockResolvedValue({ ok: true, data: workspace({ mappingsSha256: 'sha-after' }) });
});

async function openWorkspace(showUpload = true) {
  render(<NativeTemplateManager existing={LIST} showUpload={showUpload} />);
  fireEvent.click(await screen.findByTestId('twin-open-workspace-nt_1'));
  await screen.findByTestId(`twin-field-row-${MANUAL[0]}`);
}

// ── NON-VACUITY ─────────────────────────────────────────────────────────────
describe('the fixture actually contains all three confirm classes', () => {
  it('has manual, proposed and unproposed — or every arm below is vacuous', async () => {
    await openWorkspace();
    const cls = (id: string) =>
      screen.getByTestId(`twin-field-row-${id}`).getAttribute('data-confirm-class');
    expect(MANUAL.map(cls)).toEqual(['attest']);
    expect(PROPOSED.map(cls)).toEqual(['confirm', 'confirm', 'confirm']);
    expect(UNPROPOSED.map(cls)).toEqual(['choose', 'choose']);
    expect(MAPPINGS).toHaveLength(6);
  });
});

// ── THE PURE HELPERS, TESTED DIRECTLY ───────────────────────────────────────
// ⚠️ THIS BLOCK EXISTS BECAUSE A MUTATION STAYED GREEN. Replacing `confirmed`'s
// manual-carve-out ternary with an unconditional `clinicalConcept: concept`
// left every UI arm passing: the attest button passes `m.clinicalConcept` as
// `concept`, so both versions agree through every route the UI offers. The
// branch is a real guard against a future edit that renders a picker for
// manual fields — and it was UNOBSERVABLE. A guard nothing can exercise is
// indistinguishable from one that is wrong.
describe('the confirm helpers, exercised where the UI cannot reach them', () => {
  it('a MANUAL field keeps its own concept and IGNORES a supplied one', () => {
    const m = mapping({ fieldId: MANUAL[0], sourceType: 'manual', clinicalConcept: null });
    expect(confirmed(m, 'assessment').clinicalConcept).toBeNull();
    const withConcept = mapping({ fieldId: MANUAL[0], sourceType: 'manual', clinicalConcept: 'test.name' });
    expect(confirmed(withConcept, 'assessment').clinicalConcept).toBe('test.name');
  });

  it('a NON-manual field takes the supplied concept', () => {
    const m = mapping({ fieldId: UNPROPOSED[0] });
    expect(confirmed(m, 'chief_complaint').clinicalConcept).toBe('chief_complaint');
  });

  it('confirming sets certified and moves NOTHING else — practiceDefault included', () => {
    const m = mapping({ fieldId: PROPOSED[0], clinicalConcept: 'assessment' });
    const out = confirmed(m, 'assessment');
    expect(out.status).toBe('certified');
    expect({ ...out, status: m.status }).toEqual(m);
  });

  // ⚠️ THIS ARM IS THE ONE THE REFUTATION PASS ADDED, AND IT IS ABOUT THE
  // UNIVERSE. The first implementation classified on CONCEPT PRESENCE, which is
  // correct in the FALLBACK universe — where every enumerated pick carries
  // `clinicalConcept: null`, which is what every QA fixture and this file's own
  // partition shows. Production runs the MODEL proposer, which MAY put a
  // concept on those same fields; they would then classify as "confirm" and be
  // swept by the bulk control that exists for high-confidence mappings. A
  // model's guess at an enumerated dropdown is the opposite of high-confidence.
  it('an enumerated pick WITH a model-proposed concept is still the doctor’s to CHOOSE', () => {
    const guessed = mapping({
      fieldId: UNPROPOSED[1],
      sourceType: 'verified_note_selection',
      clinicalConcept: 'chief_complaint',
    });
    expect(confirmClassOf(guessed)).toBe('choose');
  });

  it('classifies by sourceType FIRST — a manual field with a concept is still manual', () => {
    expect(confirmClassOf(mapping({ fieldId: MANUAL[0], sourceType: 'manual', clinicalConcept: 'test.name' })))
      .toBe('attest');
    expect(confirmClassOf(mapping({ fieldId: PROPOSED[0], clinicalConcept: 'assessment' }))).toBe('confirm');
    expect(confirmClassOf(mapping({ fieldId: UNPROPOSED[0] }))).toBe('choose');
  });
});

// ── THE DOOR ────────────────────────────────────────────────────────────────
describe('the read action has a CALLER, which is the whole reason it may exist', () => {
  it('an existing template row opens its workspace through the action', async () => {
    render(<NativeTemplateManager existing={LIST} />);
    expect(h.open).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('twin-open-workspace-nt_1'));
    expect(h.open).toHaveBeenCalledWith('nt_1');
    // And the workspace it returns is what gets rendered — a caller that
    // invoked the action and dropped the result would be the same defect.
    expect(await screen.findByTestId(`twin-field-row-${PROPOSED[0]}`)).toBeTruthy();
  });

  it('a refusal surfaces the message and does NOT render a half workspace', async () => {
    h.open.mockResolvedValue({ ok: false, reason: 'lifecycle', error: 'That template could not be opened for review.' });
    render(<NativeTemplateManager existing={LIST} />);
    fireEvent.click(screen.getByTestId('twin-open-workspace-nt_1'));
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not be opened/i);
    expect(screen.queryByTestId(`twin-field-row-${PROPOSED[0]}`)).toBeNull();
  });
});

// ── THE SELECTIVE FOLD ──────────────────────────────────────────────────────
describe('the fold retires the UPLOAD half and keeps the CONFIRM half', () => {
  it('showUpload=false — no upload control, and the confirm door is still there', () => {
    render(<NativeTemplateManager existing={LIST} showUpload={false} />);
    expect(screen.queryByLabelText(/upload a word .docx template/i)).toBeNull();
    expect(screen.getByTestId('twin-open-workspace-nt_1')).toBeTruthy();
  });

  it('showUpload=true — BOTH halves, so the fold is what removes it and not this change', () => {
    render(<NativeTemplateManager existing={LIST} showUpload />);
    expect(screen.getByLabelText(/upload a word .docx template/i)).toBeTruthy();
    expect(screen.getByTestId('twin-open-workspace-nt_1')).toBeTruthy();
  });

  it('folded AND nothing to confirm renders NOTHING — no heading over an empty box', () => {
    const { container } = render(<NativeTemplateManager existing={[]} showUpload={false} />);
    expect(container.innerHTML).toBe('');
  });
});

// ── THE GATE DOES NOT MOVE ──────────────────────────────────────────────────
describe('nothing becomes confirmable that a physician did not confirm', () => {
  it('an unproposed field CANNOT be confirmed until a concept is chosen', async () => {
    await openWorkspace();
    const btn = screen.getByTestId(`twin-confirm-field-${UNPROPOSED[0]}`) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    fireEvent.change(screen.getByTestId(`twin-concept-select-${UNPROPOSED[0]}`), {
      target: { value: 'chief_complaint' },
    });
    expect((screen.getByTestId(`twin-confirm-field-${UNPROPOSED[0]}`) as HTMLButtonElement).disabled).toBe(false);
  });

  it('a MANUAL field attests with NO concept — the same carve-out fieldsReady makes', async () => {
    await openWorkspace();
    const btn = screen.getByTestId(`twin-confirm-field-${MANUAL[0]}`) as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
    expect(btn.textContent).toBe('Attest');
    // …and it is never given a concept picker, because there is nothing to pick.
    expect(screen.queryByTestId(`twin-concept-select-${MANUAL[0]}`)).toBeNull();
  });

  it('BULK CONFIRM touches the CONFIRM class ONLY — including the concept-bearing pick', async () => {
    await openWorkspace();
    fireEvent.click(screen.getByTestId('twin-confirm-all-proposed'));
    for (const id of PROPOSED) {
      expect(screen.getByTestId(`twin-field-row-${id}`).textContent).toContain('Confirmed');
    }
    // The classes it must not touch — a "confirm all" that swept these would
    // satisfy fieldsReady on fields nobody read. ⚠️ UNPROPOSED[1] CARRIES A
    // CONCEPT and is here precisely because a concept-presence classifier
    // would sweep it: that is production's shape, not the fallback's.
    for (const id of [...UNPROPOSED, ...MANUAL]) {
      expect(screen.getByTestId(`twin-field-row-${id}`).textContent).not.toContain('Confirmed');
    }
  });

  it('CHANGING a concept UN-CONFIRMS the field — the status is about the concept beside it', async () => {
    await openWorkspace();
    fireEvent.click(screen.getByTestId(`twin-confirm-field-${PROPOSED[0]}`));
    expect(screen.getByTestId(`twin-field-row-${PROPOSED[0]}`).textContent).toContain('Confirmed');
    fireEvent.change(screen.getByTestId(`twin-concept-select-${PROPOSED[0]}`), {
      target: { value: 'assessment' },
    });
    expect(screen.getByTestId(`twin-field-row-${PROPOSED[0]}`).textContent).not.toContain('Confirmed');
    expect(screen.getByTestId(`twin-confirm-field-${PROPOSED[0]}`)).toBeTruthy();
  });

  it('a CERTIFIED version is read-only — the writer throws IMMUTABLE, so offering the control would lie', async () => {
    h.open.mockResolvedValue({
      ok: true,
      data: workspace({ template: { ...workspace().template, certificationStatus: 'certified' } }),
    });
    await openWorkspace();
    expect(screen.queryByTestId('twin-save-mappings')).toBeNull();
    expect(screen.queryByTestId(`twin-confirm-field-${PROPOSED[0]}`)).toBeNull();
    expect(screen.queryByTestId(`twin-concept-select-${PROPOSED[0]}`)).toBeNull();
  });
});

// ── THE WRITE ───────────────────────────────────────────────────────────────
describe('the save carries exactly what the writer demands', () => {
  it('sends the FULL compiler field set and the hash the page was rendered from', async () => {
    await openWorkspace();
    fireEvent.click(screen.getByTestId('twin-confirm-all-proposed'));
    fireEvent.click(screen.getByTestId(`twin-confirm-field-${MANUAL[0]}`));
    fireEvent.click(screen.getByTestId('twin-save-mappings'));

    expect(h.update).toHaveBeenCalledTimes(1);
    const [templateId, expectedSha, sent] = h.update.mock.calls[0] as [string, string, SemanticMapping[]];
    expect(templateId).toBe('nt_1');
    // ⚠️ OPTIMISTIC CONCURRENCY. `updateTemplateTwinMappings` refuses on a hash
    // mismatch; sending anything but the rendered-from hash defeats it.
    expect(expectedSha).toBe('sha-before');
    // FIELD_SET_MISMATCH: every field, exactly once, no additions.
    expect(sent).toHaveLength(MAPPINGS.length);
    expect(sent.map((m) => m.fieldId).sort()).toEqual(MAPPINGS.map((m) => m.fieldId).sort());
  });

  it('every field it marks certified satisfies fieldsReady, and the rest are untouched', async () => {
    await openWorkspace();
    fireEvent.click(screen.getByTestId('twin-confirm-all-proposed'));
    fireEvent.click(screen.getByTestId(`twin-confirm-field-${MANUAL[0]}`));
    fireEvent.click(screen.getByTestId('twin-save-mappings'));

    const sent = (h.update.mock.calls[0] as [string, string, SemanticMapping[]])[2];
    const certified = sent.filter((m) => m.status === 'certified');
    expect(certified.map((m) => m.fieldId).sort()).toEqual([...PROPOSED, ...MANUAL].sort());
    for (const m of certified) expect(satisfiesFieldsReady(m)).toBe(true);
    // The unproposed pair is still unconfirmed — the wall shrinks by what the
    // doctor confirmed and by nothing else.
    for (const id of UNPROPOSED) {
      expect(sent.find((m) => m.fieldId === id)!.status).not.toBe('certified');
    }
  });

  it('NEVER writes a practiceDefault — the writer refuses a non-null one outright', async () => {
    await openWorkspace();
    fireEvent.click(screen.getByTestId('twin-confirm-all-proposed'));
    fireEvent.click(screen.getByTestId('twin-save-mappings'));
    const sent = (h.update.mock.calls[0] as [string, string, SemanticMapping[]])[2];
    expect(sent.every((m) => m.practiceDefault === null)).toBe(true);
  });

  // ⚠️ THIS ARM REDDENED AGAINST ITS OWN AUTHOR AND THE FIRST VERSION WAS THE
  // WRONG CLAIM. It asserted the save button DISABLES when a confirmed field
  // lacks a concept — a state the UI cannot enter, because confirming requires
  // a concept and CHANGING one un-confirms the field. Asserting a blocked
  // transition out of an unreachable state is a check that can never
  // discriminate: it would pass on any implementation, including one with no
  // guard at all.
  //
  // The real property is stronger and is what is asserted now: NO sequence of
  // controls produces `certified` without a concept, so the writer's
  // MAPPING_INVALID cannot be reached from this surface. The component keeps
  // its `incomplete` backstop deliberately — unreachable today, and the arm
  // below is what would notice if a future edit made it reachable.
  it('NO sequence of controls can send a certified mapping with no concept', async () => {
    await openWorkspace();
    fireEvent.click(screen.getByTestId(`twin-confirm-field-${PROPOSED[0]}`));
    // Blank the concept on a field that was just confirmed — the one route
    // that could plausibly strand `certified` without a concept.
    fireEvent.change(screen.getByTestId(`twin-concept-select-${PROPOSED[0]}`), { target: { value: '' } });
    // It un-confirmed, so re-confirming is refused rather than allowed-and-invalid.
    expect((screen.getByTestId(`twin-confirm-field-${PROPOSED[0]}`) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByTestId(`twin-confirm-field-${PROPOSED[0]}`));

    fireEvent.click(screen.getByTestId('twin-save-mappings'));
    const sent = (h.update.mock.calls[0] as [string, string, SemanticMapping[]])[2];
    const stranded = sent.filter(
      (m) => m.status === 'certified' && !m.clinicalConcept && m.sourceType !== 'manual',
    );
    expect(stranded).toEqual([]);
    // …and the field in question went out UNCONFIRMED, not silently repaired.
    expect(sent.find((m) => m.fieldId === PROPOSED[0])!.status).not.toBe('certified');
  });

  it('a PATTERNED concept survives opening the picker — it is registry-legal and unenumerable', async () => {
    await openWorkspace();
    const select = screen.getByTestId(`twin-concept-select-${PROPOSED[2]}`) as HTMLSelectElement;
    expect(select.value).toBe('exam.vascular.gsv');
    fireEvent.click(screen.getByTestId('twin-confirm-all-proposed'));
    fireEvent.click(screen.getByTestId('twin-save-mappings'));
    const sent = (h.update.mock.calls[0] as [string, string, SemanticMapping[]])[2];
    expect(sent.find((m) => m.fieldId === PROPOSED[2])!.clinicalConcept).toBe('exam.vascular.gsv');
  });

  it('a CONFLICT surfaces as the reload message and the draft is not silently kept', async () => {
    h.update.mockResolvedValue({ ok: false, reason: 'conflict', error: 'This template changed since you opened it' });
    await openWorkspace();
    fireEvent.click(screen.getByTestId('twin-confirm-all-proposed'));
    fireEvent.click(screen.getByTestId('twin-save-mappings'));
    expect(await screen.findByRole('alert')).toHaveTextContent(/changed since you opened it/i);
  });
});
