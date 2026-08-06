// ============================================================================
// E/M PARITY at the PRINT/EXPORT surface (#315 obs#2).
// ----------------------------------------------------------------------------
// loadVisitExportData feeds EVERY artifact (PDF, DOCX, all EHR clipboard
// formats) via `em`. It must project the AUTHORITATIVE displayed level onto
// em.code so the printed/exported claim equals what the doctor reviewed —
// never the raw L7b suggestion. prisma is mocked; the projection is REAL.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ findUnique: vi.fn() }));
// T5: the loader's read is practice-scoped, so it uses findFirst (findUnique
// cannot carry a non-unique predicate). Same mock, same rows.
vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { findFirst: mocks.findUnique, findUnique: mocks.findUnique } },
}));
vi.mock('@meddoc/shared/specialties', async (importOriginal) => ({
  // findSpecialty stays stubbed — it only supplies a display label here.
  ...(await importOriginal<typeof import('@meddoc/shared/specialties')>()),
  findSpecialty: (s: string) => ({ label: s, id: s }),
}));

import { loadVisitExportData } from '../visit-export-server';
import { projectDisplayedEmCode, projectEmForDisplay } from '../visit-export';
import { emAppliesToSpecialty } from '@meddoc/shared/specialties';

const DOCTOR = 'doc1';
// The loader takes a PRACTICE now, not an author — see visit-export-server.ts.
const PRACTICE = 'prac1';
const EM = {
  code: '99213', // the raw L7b suggestion
  description: 'Established, low',
  reasoning: { problems: [], data: '', risk: '' },
  evidence_quote: '',
};

function row(over: Record<string, unknown> = {}) {
  return {
    id: 'v1',
    userId: DOCTOR,
    patientName: 'P',
    specialty: 'primary-care',
    chiefComplaint: null,
    status: 'SIGNED',
    createdAt: new Date('2026-06-13T09:00:00Z'),
    signedAt: new Date('2026-06-13T10:00:00Z'),
    soapFinal: '## Plan\nx',
    signedSoap: '## Plan\nx',
    icdCodes: null,
    cptCodes: { em: EM },
    rxDrafts: null,
    referrals: null,
    patientSummary: null,
    headerFields: [],
    formOnly: false,
    formTitle: null,
    formSignature: null,
    user: { name: 'Dr', email: 'd@t.dev' },
    ...over,
  };
}

beforeEach(() => vi.clearAllMocks());

describe('loadVisitExportData — printed E/M code === confirmed displayed level', () => {
  it('SIGNED visit prints the FROZEN signedCode, not the raw L7b suggestion (the obs#2 bug)', async () => {
    mocks.findUnique.mockResolvedValue(
      row({ cptCodes: { em: { ...EM, code: '99213', signedCode: '99214' } } })
    );
    const data = await loadVisitExportData('v1', PRACTICE);
    expect(data?.em?.code).toBe('99214'); // confirmed, not 99213
  });

  it('SIGNED visit with an override but NO signedCode (pre-fix) falls back to the override level', async () => {
    mocks.findUnique.mockResolvedValue(
      row({ cptCodes: { em: { ...EM, code: '99213', override: { code: '99215' } } } })
    );
    const data = await loadVisitExportData('v1', PRACTICE);
    expect(data?.em?.code).toBe('99215');
  });

  it('SIGNED visit, signedCode present, wins even over a stale override', async () => {
    mocks.findUnique.mockResolvedValue(
      row({ cptCodes: { em: { ...EM, signedCode: '99214', override: { code: '99212' } } } })
    );
    const data = await loadVisitExportData('v1', PRACTICE);
    expect(data?.em?.code).toBe('99214');
  });

  it('UNSIGNED draft export projects override ?? raw (respects the doctor override)', async () => {
    mocks.findUnique.mockResolvedValue(
      row({ status: 'READY', signedSoap: null, cptCodes: { em: { ...EM, override: { code: '99215' } } } })
    );
    const data = await loadVisitExportData('v1', PRACTICE);
    expect(data?.em?.code).toBe('99215');
  });

  it('UNSIGNED, no override → raw code (unchanged behavior)', async () => {
    mocks.findUnique.mockResolvedValue(row({ status: 'READY', signedSoap: null }));
    const data = await loadVisitExportData('v1', PRACTICE);
    expect(data?.em?.code).toBe('99213');
  });

  it('a visit with no em block exports em=null (no crash)', async () => {
    mocks.findUnique.mockResolvedValue(row({ cptCodes: { procedures: [] } }));
    const data = await loadVisitExportData('v1', PRACTICE);
    expect(data?.em).toBeNull();
  });
});

describe('projectDisplayedEmCode — the one projection all surfaces share', () => {
  const base = { code: '99213', description: '', reasoning: { problems: [], data: '', risk: '' }, evidence_quote: '' };
  // Third arg = emApplies. An office visit; the imaging case is its own block.
  const APPLIES = true;
  it('signed → frozen signedCode wins', () => {
    expect(projectDisplayedEmCode({ ...base, signedCode: '99214', override: { code: '99212' } }, true, APPLIES)).toBe('99214');
  });
  it('signed, no signedCode → override', () => {
    expect(projectDisplayedEmCode({ ...base, override: { code: '99215' } }, true, APPLIES)).toBe('99215');
  });
  it('signed, neither → raw', () => {
    expect(projectDisplayedEmCode(base, true, APPLIES)).toBe('99213');
  });
  it('unsigned → override ?? raw (signedCode ignored while unsigned)', () => {
    expect(projectDisplayedEmCode({ ...base, signedCode: '99214', override: { code: '99215' } }, false, APPLIES)).toBe('99215');
    expect(projectDisplayedEmCode(base, false, APPLIES)).toBe('99213');
  });
  it('null em → null', () => {
    expect(projectDisplayedEmCode(null, true, APPLIES)).toBeNull();
  });
});

describe('THE EXPORT-LAYER GUARD — an imaging report projects no office level', () => {
  // The gap this closes: compute and store were guarded, export was not. A row
  // that had ALREADY acquired an `em` blob printed an office code into its PDF,
  // DOCX and every EHR clipboard format. One unsigned production row did exactly
  // that — a doctor-set override of 99212 whose EHR line read "99212 —
  // undefined" — because the level surface had been wrongly exposed on imaging
  // visits by the specialty-label bug.
  //
  // Asserted with the blob PRESENT and populated every way it can be. "No E/M on
  // imaging" must not depend on the row being clean; the whole point is that it
  // holds when the row is dirty.
  const dirty = {
    code: '99213',
    description: 'Office visit, established patient',
    reasoning: { problems: [], data: '', risk: '' },
    evidence_quote: '',
    override: { code: '99212' },
    signedCode: '99214',
  };

  it('returns null for every combination the blob can hold', () => {
    for (const isSigned of [true, false]) {
      expect(projectDisplayedEmCode(dirty, isSigned, false)).toBeNull();
      expect(projectDisplayedEmCode({ ...dirty, override: undefined }, isSigned, false)).toBeNull();
      expect(projectDisplayedEmCode({ ...dirty, signedCode: undefined }, isSigned, false)).toBeNull();
      expect(projectDisplayedEmCode({ ...dirty, code: '99215' }, isSigned, false)).toBeNull();
    }
  });

  it('projectEmForDisplay returns NULL, not a code-less blob', () => {
    // The renderers branch on `if (data.em)`, so an object with no code would
    // print a "Billing" heading over nothing. Absent means absent.
    expect(projectEmForDisplay(dirty, false, false)).toBeNull();
    expect(projectEmForDisplay(dirty, true, false)).toBeNull();
  });

  it('and still projects normally when E/M DOES apply — the negative control', () => {
    // Without this, the block above would pass on a projection that returned
    // null unconditionally.
    expect(projectDisplayedEmCode(dirty, false, true)).toBe('99212');
    expect(projectDisplayedEmCode(dirty, true, true)).toBe('99214');
    expect(projectEmForDisplay(dirty, false, true)?.code).toBe('99212');
  });

  it('emAppliesToSpecialty is the switch, and it takes the ID', () => {
    // Pinned here because the projection's guard is only as good as what the
    // caller passes it, and the original bug was a label reaching an id
    // comparator. The label does NOT round-trip: findSpecialty('Ultrasound').id
    // is 'unspecified', silently.
    process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = 'true';
    expect(emAppliesToSpecialty('ultrasound')).toBe(false);
    expect(emAppliesToSpecialty('primary-care')).toBe(true);
    expect(emAppliesToSpecialty(null)).toBe(true);
    // A LABEL is not an id, and this is what made the original bug silent.
    expect(emAppliesToSpecialty('Ultrasound')).toBe(true);
    delete process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
    // Flag off → the ultrasound path is inert, as everywhere else.
    expect(emAppliesToSpecialty('ultrasound')).toBe(true);
  });
});
