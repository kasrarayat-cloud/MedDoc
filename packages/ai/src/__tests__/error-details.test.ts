// ============================================================================
// Q2 follow-up — Anthropic error-details JSON capture.
// ----------------------------------------------------------------------------
// When an Anthropic SDK call throws, anthropic.ts now extracts a small
// structured payload (httpStatus / apiErrorType / apiErrorMessage /
// requestId) and persists it to ai_calls.errorDetails. Pre-fix the
// catch path only saved errorCode='ERROR' which gave the forensic
// chain nothing to read — the kasra Opus-4.7-temperature-deprecation
// 400 was invisible at the DB level until we scraped worker logs.
//
// This test exercises the exported `anthropicErrorDetailsJson` helper
// directly — its contract is the same shape the catch path persists.
// ============================================================================

import { describe, it, expect } from 'vitest';

import { anthropicErrorDetailsJson } from '../anthropic';

describe('anthropicErrorDetailsJson — Anthropic SDK error shape', () => {
  it('extracts httpStatus / apiErrorType / apiErrorMessage / requestId from a BadRequestError', () => {
    // Mimic what @anthropic-ai/sdk throws on a 400 invalid_request:
    const err = Object.assign(new Error('400 ...'), {
      status: 400,
      error: {
        type: 'error',
        error: {
          type: 'invalid_request_error',
          message: '`temperature` is deprecated for this model.',
        },
      },
      request_id: 'req_011Cak6PuPZh55vSz1tzNZYk',
    });
    const json = JSON.parse(anthropicErrorDetailsJson(err));
    expect(json.httpStatus).toBe(400);
    expect(json.apiErrorType).toBe('invalid_request_error');
    expect(json.apiErrorMessage).toBe(
      '`temperature` is deprecated for this model.'
    );
    expect(json.requestId).toBe('req_011Cak6PuPZh55vSz1tzNZYk');
  });

  it('handles authentication_error (401) with full payload', () => {
    const err = Object.assign(new Error('401 ...'), {
      status: 401,
      error: {
        type: 'error',
        error: {
          type: 'authentication_error',
          message: 'invalid x-api-key',
        },
      },
      request_id: 'req_auth_xyz',
    });
    const json = JSON.parse(anthropicErrorDetailsJson(err));
    expect(json.httpStatus).toBe(401);
    expect(json.apiErrorType).toBe('authentication_error');
    expect(json.requestId).toBe('req_auth_xyz');
  });

  it('handles 5xx with no body gracefully (network / proxy errors)', () => {
    const err = Object.assign(new Error('Internal Server Error'), {
      status: 500,
    });
    const json = JSON.parse(anthropicErrorDetailsJson(err));
    expect(json.httpStatus).toBe(500);
    expect(json.apiErrorType).toBeNull();
    expect(json.apiErrorMessage).toBeNull();
    expect(json.requestId).toBeNull();
  });

  it('handles a non-Error value (string thrown) without crashing', () => {
    const json = JSON.parse(anthropicErrorDetailsJson('some string'));
    expect(json.httpStatus).toBeNull();
    expect(json.apiErrorType).toBeNull();
    expect(json.apiErrorMessage).toBeNull();
    expect(json.requestId).toBeNull();
  });

  it('handles undefined gracefully', () => {
    const json = JSON.parse(anthropicErrorDetailsJson(undefined));
    expect(json.httpStatus).toBeNull();
  });

  it('truncates an oversized apiErrorMessage to keep JSON under 4 KB', () => {
    // 5000-char error message — should be truncated.
    const longMsg = 'X'.repeat(5000);
    const err = Object.assign(new Error('400 ...'), {
      status: 400,
      error: {
        type: 'error',
        error: { type: 'invalid_request_error', message: longMsg },
      },
    });
    const result = anthropicErrorDetailsJson(err);
    expect(result.length).toBeLessThanOrEqual(4096);
    const json = JSON.parse(result);
    expect(json.httpStatus).toBe(400);
    expect(json.apiErrorMessage).toContain('[truncated]');
    expect(json.apiErrorMessage!.length).toBeLessThan(longMsg.length);
  });

  it('reads requestId from response.headers["request-id"] when not in body', () => {
    const err = Object.assign(new Error('400 ...'), {
      status: 400,
      error: { type: 'error', error: { type: 'invalid_request_error', message: 'oops' } },
      headers: { 'request-id': 'req_from_headers' },
    });
    const json = JSON.parse(anthropicErrorDetailsJson(err));
    expect(json.requestId).toBe('req_from_headers');
  });
});
