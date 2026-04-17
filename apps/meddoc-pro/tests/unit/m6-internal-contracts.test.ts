// ============================================================================
// M6 — Internal API contract schemas (packages/types)
// ----------------------------------------------------------------------------
// Locks the request/response shape for the 5 new CRM loop-closing
// endpoints. These schemas are the drift boundary between apps/scribe
// (push modules) and apps/meddoc-pro (routes) — any breaking change
// must update both sides via a failing test.
// ============================================================================

import { describe, it, expect } from 'vitest';
import {
  CreateTasksRequestSchema,
  CreateTasksResponseSchema,
  CreateBillingEventRequestSchema,
  CreateBillingEventResponseSchema,
  AppendMedicationsRequestSchema,
  AppendMedicationsResponseSchema,
  UpdateProblemListRequestSchema,
  UpdateProblemListResponseSchema,
  CreateReferralsRequestSchema,
  CreateReferralsResponseSchema,
  type CreateTasksRequest,
  type CreateBillingEventRequest,
  type AppendMedicationsRequest,
  type UpdateProblemListRequest,
  type CreateReferralsRequest,
} from '@meddoc/types';

describe('M6 CreateTasksRequest', () => {
  const base: CreateTasksRequest = {
    sourceVisitId: 'v1',
    sourceScribeOutputId: 'o1',
    assignedUserId: 'u1',
    createdByUserId: 'u1',
    tasks: [
      { title: 'Schedule follow-up in 3 months.', sourceItemIndex: 0 },
      {
        title: 'Order lipid panel',
        description: 'From plan.diagnostics',
        dueAt: new Date().toISOString(),
        sourceItemIndex: 1,
      },
    ],
  };

  it('accepts a valid request', () => {
    expect(CreateTasksRequestSchema.safeParse(base).success).toBe(true);
  });

  it('requires at least one task', () => {
    expect(
      CreateTasksRequestSchema.safeParse({ ...base, tasks: [] }).success
    ).toBe(false);
  });

  it('caps tasks at 50 to protect the endpoint from runaway pushes', () => {
    const big = Array.from({ length: 51 }, (_, i) => ({
      title: `t${i}`,
      sourceItemIndex: i,
    }));
    expect(
      CreateTasksRequestSchema.safeParse({ ...base, tasks: big }).success
    ).toBe(false);
  });

  it('response carries taskIds array matching input length', () => {
    const ok = CreateTasksResponseSchema.safeParse({
      taskIds: ['t1', 't2'],
    });
    expect(ok.success).toBe(true);
  });
});

describe('M6 CreateBillingEventRequest', () => {
  const base: CreateBillingEventRequest = {
    sourceVisitId: 'v1',
    sourceScribeOutputId: 'o1',
    clinicianUserId: 'u1',
    coding: {
      confidence: 'medium',
      icd10: [
        {
          code: 'I10',
          description: 'Essential hypertension.',
          evidence_quote: 'BP 148 over 92',
          confidence: 'high',
        },
      ],
      cpt: [
        {
          code: '99213',
          description: 'Established, low complexity.',
          evidence_quote: 'checking in on your blood pressure',
          confidence: 'medium',
        },
      ],
      ambiguities: [],
    },
  };

  it('accepts a valid coding payload', () => {
    expect(CreateBillingEventRequestSchema.safeParse(base).success).toBe(true);
  });

  it('rejects a coding payload with an evidence_quote missing', () => {
    const bad = {
      ...base,
      coding: { ...base.coding, icd10: [{ ...base.coding.icd10[0], evidence_quote: '' }] },
    };
    expect(CreateBillingEventRequestSchema.safeParse(bad).success).toBe(false);
  });

  it('response shape carries billingEventId string', () => {
    expect(CreateBillingEventResponseSchema.safeParse({ billingEventId: 'b1' }).success).toBe(
      true
    );
  });
});

describe('M6 AppendMedicationsRequest', () => {
  const base: AppendMedicationsRequest = {
    sourceVisitId: 'v1',
    sourceScribeOutputId: 'o1',
    clinicianUserId: 'u1',
    prescriptions: [
      {
        drug: 'Lisinopril',
        dose: '20 mg',
        route: 'PO',
        frequency: 'once daily',
        duration: 'ongoing',
        quantity: '#30 tablets',
        refills: 3,
        sig: 'Take 1 tablet by mouth daily.',
        is_controlled: false,
        clinician_requested: true,
        evidence_quote: 'Increase lisinopril to 20 milligrams daily.',
        warnings: [],
        confidence: 'high',
      },
    ],
  };

  it('accepts a valid prescriptions array', () => {
    expect(AppendMedicationsRequestSchema.safeParse(base).success).toBe(true);
  });

  it('caps prescriptions at 50', () => {
    const big = Array.from({ length: 51 }, () => base.prescriptions[0]);
    expect(
      AppendMedicationsRequestSchema.safeParse({ ...base, prescriptions: big }).success
    ).toBe(false);
  });

  it('response shape carries medicationIds + dedupedCount', () => {
    expect(
      AppendMedicationsResponseSchema.safeParse({
        medicationIds: ['m1', 'm2'],
        dedupedCount: 1,
      }).success
    ).toBe(true);
  });
});

describe('M6 UpdateProblemListRequest', () => {
  const base: UpdateProblemListRequest = {
    sourceVisitId: 'v1',
    sourceScribeOutputId: 'o1',
    problemLines: [
      'HTN (I10) — from Scribe visit v1 on 2026-04-17',
      'DM2 (E11.9) — from Scribe visit v1 on 2026-04-17',
    ],
  };

  it('accepts a valid problem-list patch', () => {
    expect(UpdateProblemListRequestSchema.safeParse(base).success).toBe(true);
  });

  it('rejects empty problem lines', () => {
    expect(
      UpdateProblemListRequestSchema.safeParse({ ...base, problemLines: [''] }).success
    ).toBe(false);
  });

  it('caps problem lines at 50 and at 400 chars per line', () => {
    const tooMany = Array.from({ length: 51 }, () => 'x');
    expect(
      UpdateProblemListRequestSchema.safeParse({ ...base, problemLines: tooMany }).success
    ).toBe(false);
    const tooLong = ['x'.repeat(401)];
    expect(
      UpdateProblemListRequestSchema.safeParse({ ...base, problemLines: tooLong }).success
    ).toBe(false);
  });

  it('response shape carries appendedCount + totalSize', () => {
    expect(
      UpdateProblemListResponseSchema.safeParse({ appendedCount: 2, totalSize: 10 }).success
    ).toBe(true);
  });
});

describe('M6 CreateReferralsRequest', () => {
  const base: CreateReferralsRequest = {
    sourceVisitId: 'v1',
    sourceScribeOutputId: 'o1',
    patientId: 'p1',
    clinicianUserId: 'u1',
    letters: [
      {
        specialty: 'Cardiology',
        urgency: 'routine',
        clinical_summary: 'Pt with established HTN on lisinopril, stable.',
        reason_for_referral: 'Echo to evaluate for LVH given long-standing HTN.',
        relevant_history: 'HTN dx 2022; lisinopril 20 mg; NKDA.',
        evidence_quote: 'let me send you over to cardiology for an echo',
        confidence: 'high',
      },
    ],
  };

  it('accepts a valid referrals payload', () => {
    expect(CreateReferralsRequestSchema.safeParse(base).success).toBe(true);
  });

  it('rejects empty letters array', () => {
    expect(
      CreateReferralsRequestSchema.safeParse({ ...base, letters: [] }).success
    ).toBe(false);
  });

  it('response shape carries documentIds array', () => {
    expect(
      CreateReferralsResponseSchema.safeParse({ documentIds: ['d1', 'd2'] }).success
    ).toBe(true);
  });
});
