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
vi.mock('@meddoc/db', () => ({ default: { transcribeVisit: { findUnique: mocks.findUnique } } }));
vi.mock('@meddoc/shared/specialties', () => ({
  findSpecialty: (s: string) => ({ label: s, id: s }),
}));

import { loadVisitExportData } from '../visit-export-server';

const DOCTOR = 'doc1';
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
    const data = await loadVisitExportData('v1', DOCTOR);
    expect(data?.em?.code).toBe('99214'); // confirmed, not 99213
  });

  it('SIGNED visit with an override but NO signedCode (pre-fix) falls back to the override level', async () => {
    mocks.findUnique.mockResolvedValue(
      row({ cptCodes: { em: { ...EM, code: '99213', override: { code: '99215' } } } })
    );
    const data = await loadVisitExportData('v1', DOCTOR);
    expect(data?.em?.code).toBe('99215');
  });

  it('SIGNED visit, signedCode present, wins even over a stale override', async () => {
    mocks.findUnique.mockResolvedValue(
      row({ cptCodes: { em: { ...EM, signedCode: '99214', override: { code: '99212' } } } })
    );
    const data = await loadVisitExportData('v1', DOCTOR);
    expect(data?.em?.code).toBe('99214');
  });

  it('UNSIGNED draft export projects override ?? raw (respects the doctor override)', async () => {
    mocks.findUnique.mockResolvedValue(
      row({ status: 'READY', signedSoap: null, cptCodes: { em: { ...EM, override: { code: '99215' } } } })
    );
    const data = await loadVisitExportData('v1', DOCTOR);
    expect(data?.em?.code).toBe('99215');
  });

  it('UNSIGNED, no override → raw code (unchanged behavior)', async () => {
    mocks.findUnique.mockResolvedValue(row({ status: 'READY', signedSoap: null }));
    const data = await loadVisitExportData('v1', DOCTOR);
    expect(data?.em?.code).toBe('99213');
  });

  it('a visit with no em block exports em=null (no crash)', async () => {
    mocks.findUnique.mockResolvedValue(row({ cptCodes: { procedures: [] } }));
    const data = await loadVisitExportData('v1', DOCTOR);
    expect(data?.em).toBeNull();
  });
});
