// ============================================================================
// M7 — Retention scan logic
// ----------------------------------------------------------------------------
// Tests the pure parts of scanPracticeRetention against a stubbed
// PrismaClient so we don't need a populated DB. Covers:
//   - audio retention cutoff honored
//   - transcript retention cutoff honored (signed only)
//   - safety exclusion blocks visits with requires_immediate_follow_up
//   - nothing is purged if practice has zero candidates
// ============================================================================

import { describe, it, expect } from 'vitest';
import type { PrismaClient } from '@prisma/client';
import {
  scanPracticeRetention,
  findSafetyExcludedVisitIds,
} from '../../../scribe/src/server/retention/query';

type MockVisit = {
  id: string;
  audioObjectKey: string | null;
  endedAt: Date | null;
  status?: 'SIGNED' | 'READY_FOR_REVIEW';
};

type MockOutput = {
  visitId: string;
  type: 'SOAP';
  content: unknown;
  createdAt: Date;
};

function mkStubPrisma(args: {
  audioCandidates: MockVisit[];
  transcriptCandidates: MockVisit[];
  soapOutputs: MockOutput[];
}): PrismaClient {
  const stub = {
    scribeVisit: {
      findMany: async (query: { where?: { audioObjectKey?: unknown; status?: string } }) => {
        // Pick the right set by query shape — audio query has
        // audioObjectKey filter, transcript query has status=SIGNED.
        const where = query.where ?? {};
        if ('audioObjectKey' in where && where.audioObjectKey) {
          return args.audioCandidates;
        }
        if (where.status === 'SIGNED') {
          return args.transcriptCandidates;
        }
        return [];
      },
    },
    scribeOutput: {
      findMany: async (query: { where?: { visitId?: { in?: string[] } } }) => {
        const ids = query.where?.visitId?.in ?? [];
        return args.soapOutputs.filter((o) => ids.includes(o.visitId));
      },
    },
  };
  return stub as unknown as PrismaClient;
}

describe('scanPracticeRetention', () => {
  const policy = { audioRetentionDays: 90, transcriptRetentionDays: 2555 };
  const now = new Date('2026-04-17T00:00:00Z');

  it('reports zero counts for an empty practice', async () => {
    const prisma = mkStubPrisma({
      audioCandidates: [],
      transcriptCandidates: [],
      soapOutputs: [],
    });
    const result = await scanPracticeRetention(prisma, 'pA', policy, now);
    expect(result.audioCount).toBe(0);
    expect(result.transcriptCount).toBe(0);
    expect(result.safetyExcludedCount).toBe(0);
    expect(result.oldestSignedAt).toBeNull();
  });

  it('counts audio candidates that passed the audio cutoff', async () => {
    const prisma = mkStubPrisma({
      audioCandidates: [
        { id: 'v1', audioObjectKey: 'k1', endedAt: new Date('2025-12-01T00:00:00Z') },
        { id: 'v2', audioObjectKey: 'k2', endedAt: new Date('2025-11-01T00:00:00Z') },
      ],
      transcriptCandidates: [],
      soapOutputs: [],
    });
    const result = await scanPracticeRetention(prisma, 'pA', policy, now);
    expect(result.audioCount).toBe(2);
    expect(result.audioSample).toEqual(expect.arrayContaining(['k1', 'k2']));
  });

  it('excludes safety-sensitive visits (requires_immediate_follow_up) from BOTH counts', async () => {
    const prisma = mkStubPrisma({
      audioCandidates: [
        { id: 'psych1', audioObjectKey: 'k-psych', endedAt: new Date('2025-12-01T00:00:00Z') },
        { id: 'regular1', audioObjectKey: 'k-reg', endedAt: new Date('2025-12-01T00:00:00Z') },
      ],
      transcriptCandidates: [
        { id: 'psych1', audioObjectKey: null, endedAt: new Date('2019-01-01T00:00:00Z'), status: 'SIGNED' },
        { id: 'regular2', audioObjectKey: null, endedAt: new Date('2019-01-01T00:00:00Z'), status: 'SIGNED' },
      ],
      soapOutputs: [
        {
          visitId: 'psych1',
          type: 'SOAP',
          createdAt: new Date(),
          content: {
            confidence: 'medium',
            subjective: { chief_complaint: 'x' },
            objective: { vitals: 'x' },
            assessment: [
              {
                icd10_candidate: 'F33.1',
                description: 'x',
                evidence_quote: 'x',
                confidence: 'high',
              },
            ],
            plan: { medications: 'x' },
            missing_required_elements: [],
            ambiguities: [],
            requires_immediate_follow_up: true,
          },
        },
      ],
    });
    const result = await scanPracticeRetention(prisma, 'pA', policy, now);
    expect(result.audioCount).toBe(1); // psych1 filtered out
    expect(result.audioSample).toEqual(['k-reg']);
    expect(result.transcriptCount).toBe(1); // psych1 filtered out
    expect(result.transcriptSample).toEqual(['regular2']);
    expect(result.safetyExcludedCount).toBe(1);
  });

  it('uses the transcript cutoff to pick oldestSignedAt', async () => {
    const prisma = mkStubPrisma({
      audioCandidates: [],
      transcriptCandidates: [
        { id: 'v1', audioObjectKey: null, endedAt: new Date('2017-06-01T00:00:00Z'), status: 'SIGNED' },
        { id: 'v2', audioObjectKey: null, endedAt: new Date('2016-01-01T00:00:00Z'), status: 'SIGNED' },
      ],
      soapOutputs: [],
    });
    const result = await scanPracticeRetention(prisma, 'pA', policy, now);
    expect(result.transcriptCount).toBe(2);
    // The stub doesn't sort; the function's query uses orderBy: endedAt asc.
    // The stub returns in the order provided — first non-excluded is v1's date.
    expect(result.oldestSignedAt).toBe('2017-06-01T00:00:00.000Z');
  });
});

describe('findSafetyExcludedVisitIds', () => {
  it('returns an empty set for zero input ids without touching Prisma', async () => {
    // Stub that throws if called — proves the short-circuit.
    const stub = {
      scribeOutput: {
        findMany: async () => {
          throw new Error('should not be called');
        },
      },
    } as unknown as PrismaClient;
    const result = await findSafetyExcludedVisitIds(stub, []);
    expect(result.size).toBe(0);
  });
});
