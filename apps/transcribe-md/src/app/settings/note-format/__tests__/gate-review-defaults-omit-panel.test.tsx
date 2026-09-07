// ============================================================================
// GATE — REVIEW-DEFAULTS item 2, THE PANEL HALF: the omit door in the DOM.
// ----------------------------------------------------------------------------
// The engine half lives in
// `lib/template-twin/__tests__/gate-review-defaults-omit-door.test.ts` and
// proves the PREDICATE. This file proves the SURFACE actually calls it — a
// predicate nothing consults is the same as no predicate.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL, stated first:
//   · the control is offered on a field the resolver
//     would refuse to honour it on            -> the withheld-offer arm
//   · ticking it does not reach the writer    -> the payload arms
//   · unticking writes `undefined` or `'keep'`
//     instead of NULL                         -> the untick arm
//   · a CERTIFIED template becomes editable   -> the readOnly arm
//   · a certified template hides a choice that
//     is in force                             -> the readOnly-visible arm
//   · the doctor is not told the page is
//     unchanged                               -> the hint arm
//
// ⚠️ WHAT THIS FILE DOES *NOT* MEASURE:
//   · THE SERVER. `updateTemplateTwinMappingsAction` is mocked here. That the
//     writer PERSISTS `unmentionedPolicy` is `certification-lifecycle.ts:521`
//     and is pinned by gate-194's projection arm, not by this file.
//   · THE RESOLVER. Whether `omit` is honoured is the engine gate's property.
//   · ANY AUDIT ROW. Mapping edits ARE audited — production holds 93
//     `TEMPLATE_TWIN_MAPPING_UPDATED` rows, and my first note here said they
//     were not. What that row does NOT record is WHICH policy was chosen, so an
//     auditor sees the edit and not the decision. This change adds no new audit
//     action; the limit is named in the PR body.
// ============================================================================

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import type { SemanticMapping } from '@/lib/template-twin/ir';
import type { TemplateTwinWorkspace } from '@/lib/template-twin/client-types';
import { OMIT_CONTROL_HINT } from '@/lib/template-twin/unmentioned-policy';

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

const FID = (n: number) => `ttf_${n.toString(16).padStart(24, '0')}`;

/** Offerable: nothing marks it as requiring clinician input. */
const OFFERABLE = FID(1);
/** Not offerable: `mapping.blankPolicy === 'requires_input'`. */
const REQUIRED_BY_MAPPING = FID(2);
/** Not offerable: `field.required`. */
const REQUIRED_BY_FIELD = FID(3);
// ⚠️ THE FIVE BELOW ARE THE GUARDS THE FIRST CUT OF THIS FILE COULD NOT SEE.
// Every fixture in it was `sourceType: 'extraction'` with a concept and no
// practice default, so `grep -c "'manual'"` over this file was ZERO — and the
// panel offered the control on all five, where the resolver returns before the
// policy is ever read. A fixture monoculture is not weak coverage; it is a
// blind spot shaped exactly like the bug.
/** Not offerable: `mapping.sourceType === 'manual'` — filled by hand each visit. */
const MANUAL_SOURCE = FID(4);
/** Not offerable: `mapping.sourceType === 'verified_note_selection'`. */
const NOTE_SELECTION = FID(5);
/** Not offerable: no `clinicalConcept` — the row itself says "· no concept yet". */
const NO_CONCEPT = FID(6);
/** Not offerable: an `approved_practice_default` short-circuits ahead of the policy. */
const HAS_PRACTICE_DEFAULT = FID(7);
/** Not offerable: `field.detectionStatus === 'unsupported'`. */
const UNSUPPORTED_FIELD = FID(8);
/** Carries a proposed `conceptScope` — the #208 half of the merged surface. */
const SCOPED = FID(9);

function mapping(over: Partial<SemanticMapping> & { fieldId: string }): SemanticMapping {
  return {
    sourceType: 'extraction',
    clinicalConcept: 'ros.cardiovascular',
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

const MAPPINGS: SemanticMapping[] = [
  mapping({ fieldId: OFFERABLE }),
  mapping({ fieldId: REQUIRED_BY_MAPPING, blankPolicy: 'requires_input' }),
  mapping({ fieldId: REQUIRED_BY_FIELD }),
  mapping({ fieldId: MANUAL_SOURCE, sourceType: 'manual', clinicalConcept: null }),
  mapping({ fieldId: NOTE_SELECTION, sourceType: 'verified_note_selection' }),
  mapping({ fieldId: NO_CONCEPT, clinicalConcept: null }),
  mapping({ fieldId: HAS_PRACTICE_DEFAULT, practiceDefault: 'The patient consents.' }),
  mapping({ fieldId: UNSUPPORTED_FIELD }),
  // ⚠️ THE #208 SURFACE. A scaffolded clause covering several symptoms carries a
  // `conceptScope` the model may PROPOSE, and the whole point of rendering it is
  // that `planAutoConfirm` must not certify it unread.
  mapping({
    fieldId: SCOPED,
    conceptScope: ['ros.cardiovascular', 'ros.respiratory', 'ros.gi'],
  } as Partial<SemanticMapping> & { fieldId: string }),
];

/** Every field that must NOT carry the control, with the guard that withholds it. */
const REFUSED: ReadonlyArray<readonly [string, string]> = [
  [REQUIRED_BY_MAPPING, 'mapping.blankPolicy = requires_input'],
  [REQUIRED_BY_FIELD, 'field.required'],
  [MANUAL_SOURCE, 'sourceType = manual'],
  [NOTE_SELECTION, 'sourceType = verified_note_selection'],
  [NO_CONCEPT, 'clinicalConcept = null'],
  [HAS_PRACTICE_DEFAULT, 'practiceDefault is set'],
  [UNSUPPORTED_FIELD, 'field.detectionStatus = unsupported'],
];

// ⚠️ THE FIELD HALF IS REAL HERE, NOT A PARTIAL CAST. `canOmitWhenUnmentioned`
// reads `field.required` and `field.unknownPolicy`; a fixture that omitted them
// would make every field look offerable and the withheld-offer arm vacuous.
const FIELD_OVERRIDES: Record<string, { required: boolean; detectionStatus: string }> = {
  [OFFERABLE]: { required: false, detectionStatus: 'needs_confirmation' },
  [REQUIRED_BY_MAPPING]: { required: false, detectionStatus: 'needs_confirmation' },
  [REQUIRED_BY_FIELD]: { required: true, detectionStatus: 'needs_confirmation' },
  [MANUAL_SOURCE]: { required: false, detectionStatus: 'needs_confirmation' },
  [NOTE_SELECTION]: { required: false, detectionStatus: 'needs_confirmation' },
  [NO_CONCEPT]: { required: false, detectionStatus: 'needs_confirmation' },
  [HAS_PRACTICE_DEFAULT]: { required: false, detectionStatus: 'needs_confirmation' },
  [UNSUPPORTED_FIELD]: { required: false, detectionStatus: 'unsupported' },
  [SCOPED]: { required: false, detectionStatus: 'needs_confirmation' },
};

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
    stats: { dropdowns: 0, tables: 0 } as TemplateTwinWorkspace['stats'],
    fields: (over.fields ??
      MAPPINGS.map((m, i) => ({
        definitionId: `def_${i}`,
        field: {
          fieldId: m.fieldId,
          originalLabel: `Field ${i + 1}`,
          kind: 'narrative_text',
          detectionStatus: FIELD_OVERRIDES[m.fieldId]!.detectionStatus,
          scaffolded: true,
          scaffoldText: 'The patient consents to a telehealth consultation.',
          required: FIELD_OVERRIDES[m.fieldId]!.required,
          unknownPolicy: 'blank',
        },
        mapping: m,
      }))) as unknown as TemplateTwinWorkspace['fields'],
    unsupported: [],
    mappingsSha256: 'sha-before',
    latestSyntheticTest: null,
    canEdit: true,
    ...over,
  } as TemplateTwinWorkspace;
}

const LIST = [
  { noteTemplateId: 'nt_1', name: 'WM IOV', certificationStatus: 'needs_confirmation', fieldCount: 3, version: 1 },
];

beforeEach(() => {
  vi.clearAllMocks();
  h.open.mockResolvedValue({ ok: true, data: workspace() });
  h.update.mockResolvedValue({ ok: true, data: workspace({ mappingsSha256: 'sha-after' }) });
});

async function openWorkspace(ws?: TemplateTwinWorkspace) {
  if (ws) h.open.mockResolvedValue({ ok: true, data: ws });
  render(<NativeTemplateManager existing={LIST} showUpload={false} />);
  fireEvent.click(await screen.findByTestId('twin-open-workspace-nt_1'));
  await screen.findByTestId(`twin-field-row-${OFFERABLE}`);
}

function sentMappings(): SemanticMapping[] {
  return (h.update.mock.calls[0] as [string, string, SemanticMapping[]])[2];
}

// ── NON-VACUITY ─────────────────────────────────────────────────────────────
describe('the fixture contains BOTH an offerable and a refused field', () => {
  it('or every withheld-offer arm below passes for the wrong reason', async () => {
    await openWorkspace();
    expect(screen.queryByTestId(`twin-omit-toggle-${OFFERABLE}`)).not.toBeNull();
    for (const [fieldId, guard] of REFUSED) {
      expect(
        screen.queryByTestId(`twin-omit-toggle-${fieldId}`),
        `offered despite ${guard}`,
      ).toBeNull();
    }
  });
});

describe('item 2 — the panel offers omit exactly where the resolver honours it', () => {
  it('⚠️ THE OFFER IS WITHHELD where the field requires clinician input', async () => {
    await openWorkspace();
    for (const [fieldId, guard] of REFUSED) {
      // Every refused field still RENDERS — it is the control that is absent,
      // not the row. A missing row would pass this arm for an unrelated reason.
      expect(
        screen.queryByTestId(`twin-field-row-${fieldId}`),
        `row missing for ${guard} — this arm would pass vacuously`,
      ).not.toBeNull();
      expect(
        screen.queryByTestId(`twin-omit-toggle-${fieldId}`),
        `offered despite ${guard}`,
      ).toBeNull();
    }
  });

  it('⚠️ THE DOCTOR IS TOLD THE PAGE DOES NOT CHANGE', async () => {
    await openWorkspace();
    expect(screen.getAllByText(OMIT_CONTROL_HINT).length).toBeGreaterThan(0);
  });
});

describe('item 2 — ticking it reaches the writer', () => {
  it('ticking writes `omit` for THAT field and leaves every other mapping alone', async () => {
    await openWorkspace();
    fireEvent.click(screen.getByTestId(`twin-omit-toggle-${OFFERABLE}`));
    fireEvent.click(screen.getByTestId('twin-save-mappings'));

    const sent = sentMappings();
    // FIELD_SET_MISMATCH: every field, exactly once, no additions.
    expect(sent).toHaveLength(MAPPINGS.length);
    expect(sent.find((m) => m.fieldId === OFFERABLE)?.unmentionedPolicy).toBe('omit');
    for (const [other] of REFUSED) {
      expect(sent.find((m) => m.fieldId === other)?.unmentionedPolicy ?? null).toBeNull();
    }
  });

  it('⚠️ UNTICKING WRITES NULL — not `undefined`, and never `keep`', async () => {
    await openWorkspace(
      workspace({
        fields: MAPPINGS.map((m, i) => ({
          definitionId: `def_${i}`,
          field: {
            fieldId: m.fieldId,
            originalLabel: `Field ${i + 1}`,
            kind: 'narrative_text',
            detectionStatus: 'needs_confirmation',
            scaffolded: true,
            required: FIELD_OVERRIDES[m.fieldId]!.required,
            unknownPolicy: 'blank',
          },
          mapping:
            m.fieldId === OFFERABLE ? { ...m, unmentionedPolicy: 'omit' as const } : m,
        })) as unknown as TemplateTwinWorkspace['fields'],
      }),
    );

    const box = screen.getByTestId(`twin-omit-toggle-${OFFERABLE}`) as HTMLInputElement;
    // It renders the STORED state — otherwise unticking is untestable and the
    // doctor cannot see what is in force.
    expect(box.checked).toBe(true);

    fireEvent.click(box);
    fireEvent.click(screen.getByTestId('twin-save-mappings'));

    const sent = sentMappings();
    const target = sent.find((m) => m.fieldId === OFFERABLE)!;
    // ⚠️ `toBeNull` and not `toBeFalsy`: `undefined` is elided from the mapping
    // hash by `mapping-hash.ts`, so an undefined here would silently fail to
    // move the attestation that gate-194 arm (11) requires to move.
    expect(target.unmentionedPolicy).toBeNull();
    expect(target.unmentionedPolicy).not.toBe('keep');
  });
});

describe('item 2 — a certified version is immutable, and says so', () => {
  const certified = () =>
    workspace({
      template: { ...workspace().template, certificationStatus: 'certified' },
      fields: MAPPINGS.map((m, i) => ({
        definitionId: `def_${i}`,
        field: {
          fieldId: m.fieldId,
          originalLabel: `Field ${i + 1}`,
          kind: 'narrative_text',
          detectionStatus: 'certified',
          scaffolded: true,
          required: FIELD_OVERRIDES[m.fieldId]!.required,
          unknownPolicy: 'blank',
        },
        mapping: m.fieldId === OFFERABLE ? { ...m, unmentionedPolicy: 'omit' as const } : m,
      })) as unknown as TemplateTwinWorkspace['fields'],
    });

  it('⚠️ NO EDITABLE CONTROL on a certified template — the writer refuses IMMUTABLE', async () => {
    await openWorkspace(certified());
    expect(screen.queryByTestId(`twin-omit-toggle-${OFFERABLE}`)).toBeNull();
  });

  it('⚠️ BUT THE CHOICE IN FORCE STAYS VISIBLE — a silent state is unreadable', async () => {
    await openWorkspace(certified());
    expect(screen.queryByTestId(`twin-omit-readonly-${OFFERABLE}`)).not.toBeNull();
    // And NOT on a field that never carried the policy.
    expect(screen.queryByTestId(`twin-omit-readonly-${REQUIRED_BY_MAPPING}`)).toBeNull();
  });
});

// ============================================================================
// WITHDRAWING THE OFFER WITHDRAWS THE VALUE — the save a doctor could not leave.
// ----------------------------------------------------------------------------
// ⚠️ FOUND BY A PEER SESSION'S INDEPENDENT PASS. Tick "expected blank", set the
// concept picker back to "— choose a concept —", Save: the checkbox disappears
// (the offer is gated on `canOmitWhenUnmentioned`, which a null concept makes
// false) but `unmentionedPolicy` stayed `'omit'` and was still SENT. The writer
// refused the whole batch with an opaque MAPPING_INVALID, and the only control
// that could clear it was hidden by the same now-false predicate causing the
// refusal. A dead end with no exit and no explanation.
//
// One normalisation in `setMapping` closes three findings: this trap, a ticked
// omit surviving a concept re-map, and two clicks persisting an omit the
// resolver refuses.
// ============================================================================
describe('item 2 — a withdrawn offer withdraws the stored value', () => {
  // ⚠️ FOUND BY A PEER SESSION'S INDEPENDENT PASS, AND IT WAS A DEAD END WITH NO
  // EXIT. Tick "expected blank", set the concept picker back to "— choose a
  // concept —", Save: the checkbox disappears (the offer is gated on
  // `canOmitWhenUnmentioned`, which a null concept makes false) but the stored
  // `unmentionedPolicy` stayed `'omit'` and was still SENT. The writer refused
  // the WHOLE batch with an opaque MAPPING_INVALID, nothing named the field, and
  // the only control that could clear it was hidden by the same now-false
  // predicate causing the refusal.
  //
  // One normalisation in `setMapping` closes three findings: this trap, a ticked
  // omit surviving a concept RE-MAP, and two clicks persisting an omit the
  // resolver refuses with the control hidden.
  it('clearing the concept on an omitted field does NOT send an omit', async () => {
    await openWorkspace();

    fireEvent.click(screen.getByTestId(`twin-omit-toggle-${OFFERABLE}`));
    expect(
      (screen.getByTestId(`twin-omit-toggle-${OFFERABLE}`) as HTMLInputElement).checked,
      'the fixture is not actually offerable — this arm would prove nothing',
    ).toBe(true);

    fireEvent.change(screen.getByTestId(`twin-concept-select-${OFFERABLE}`), {
      target: { value: '' },
    });
    expect(
      screen.queryByTestId(`twin-omit-toggle-${OFFERABLE}`),
      'the offer should be withdrawn once the concept is gone',
    ).toBeNull();

    fireEvent.click(screen.getByTestId('twin-save-mappings'));
    const sent = sentMappings();
    const row = sent.find((m) => m.fieldId === OFFERABLE)!;
    expect(row.clinicalConcept ?? null).toBeNull();
    expect(
      row.unmentionedPolicy ?? null,
      'the offer was withdrawn but the VALUE was still sent — the writer refuses ' +
        'the whole batch and the control that would clear it is hidden',
    ).toBeNull();
  });

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠️ ROUND FIVE — A -> B, THE CASE THE ARM ABOVE DOES NOT COVER.
  //
  // The arm above closes A -> null: the offer disappears, so the normalisation
  // fires. It does NOT close a re-map to another OFFERABLE concept, where
  // `canOmitWhenUnmentioned` stays TRUE and nothing clears. Three places
  // asserted that case was closed — the `setMapping` comment, this file's own
  // header, and the commit message — and it was not.
  //
  // ⚠️ THE HARM IS THAT THE JUDGEMENT SURVIVES ITS SUBJECT. "Do not ask me
  // about this" was said about concept A. After the re-map it is in force
  // against concept B, which the doctor never ruled on — and the same edit
  // drops the row to `needs_confirmation`, so the CONCEPT must be re-confirmed
  // while the OMIT is not re-asked.
  // ══════════════════════════════════════════════════════════════════════════
  it('⚠️ RE-MAPPING the concept A -> B does NOT carry the omit across', async () => {
    await openWorkspace();

    fireEvent.click(screen.getByTestId(`twin-omit-toggle-${OFFERABLE}`));
    const box = () => screen.queryByTestId(`twin-omit-toggle-${OFFERABLE}`) as HTMLInputElement | null;
    expect(box()?.checked, 'the fixture is not offerable — this arm would prove nothing').toBe(true);

    // A DIFFERENT, still-offerable concept — NOT '— choose a concept —'.
    const select = screen.getByTestId(`twin-concept-select-${OFFERABLE}`) as HTMLSelectElement;
    const other = [...select.options]
      .map((o) => o.value)
      .find((v) => v !== '' && v !== 'ros.cardiovascular');
    expect(other, 'the registry offers only one concept — cannot drive a re-map').toBeDefined();

    fireEvent.change(select, { target: { value: other } });

    // ⚠️ THE OFFER IS STILL AVAILABLE — that is exactly why the A -> null
    // normalisation cannot see this case, and why the checkbox must come back
    // UNTICKED rather than disappear.
    expect(box(), 'the offer should still be available on an offerable concept').not.toBeNull();
    expect(
      box()?.checked,
      'the omit survived a concept re-map — a judgement made about one concept ' +
        'is now in force against another the doctor never ruled on',
    ).toBe(false);

    fireEvent.click(screen.getByTestId('twin-save-mappings'));
    const row = sentMappings().find((m) => m.fieldId === OFFERABLE)!;
    expect(row.clinicalConcept).toBe(other);
    expect(
      row.unmentionedPolicy ?? null,
      'the payload carried the omit onto the NEW concept',
    ).toBeNull();
  });

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠️ ROUND FIVE — THE #208 HALF OF THE UNION HAD **ZERO ARMS**.
  //
  // The whole `conceptScope` block deleted clean and every suite stayed green,
  // while the merge that brought it in silently moved it below the omit
  // control. Its own comment states the claim it was built to keep: the
  // proposal must be VISIBLE, because `planAutoConfirm` would otherwise certify
  // it unread — "silently accepted", which the ruling forbids. A surface whose
  // entire purpose is to be READ, with nothing asserting it renders, is the
  // same false green as a guard nobody drives.
  // ══════════════════════════════════════════════════════════════════════════
  it('⚠️ A PROPOSED conceptScope IS RENDERED — deleting the block must not stay green', async () => {
    await openWorkspace();
    const el = screen.queryByTestId(`twin-concept-scope-${SCOPED}`);
    expect(el, 'the proposed conceptScope is invisible — planAutoConfirm would certify it unread').not.toBeNull();
  });

  it('⚠️ …AND IT NAMES EVERY CONCEPT, not just how many', async () => {
    await openWorkspace();
    const text = screen.getByTestId(`twin-concept-scope-${SCOPED}`).textContent ?? '';
    // What a clause claims to cover decides which dictated findings can
    // contradict the template's own sentence. A count the doctor cannot expand
    // is not something they can disagree with.
    for (const c of ['ros.cardiovascular', 'ros.respiratory', 'ros.gi']) {
      expect(text, `the scope omits ${c}`).toContain(c);
    }
  });

  it('⚠️ THE COUNT AND THE LIST AGREE — a block that miscounts is worse than none', async () => {
    await openWorkspace();
    const text = screen.getByTestId(`twin-concept-scope-${SCOPED}`).textContent ?? '';
    const claimed = Number(/covers (\d+)/.exec(text)?.[1]);
    const listed = text.slice(text.indexOf(':') + 1).split(',').filter((p) => p.trim()).length;
    expect(claimed, 'the rendered count is not a number').not.toBeNaN();
    expect(listed, 'the count and the enumerated list disagree').toBe(claimed);
    expect(claimed).toBe(3);
  });

  it('NON-VACUITY — a field with NO conceptScope renders no scope line', async () => {
    // Without this the three arms above pass on a block that always renders.
    await openWorkspace();
    expect(screen.queryByTestId(`twin-concept-scope-${OFFERABLE}`)).toBeNull();
  });
});
