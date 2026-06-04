import { describe, expect, it } from 'vitest';
import { isStaleDeploymentError } from '../stale-deployment';

describe('isStaleDeploymentError', () => {
  it('detects the Next.js unknown-server-action error (the c-mpz1o2ax incident)', () => {
    expect(
      isStaleDeploymentError(
        new Error('Server Action "4046931ee3eeab30c4e2e0bf2fe3d7d387531471b5" was not found on the server.'),
      ),
    ).toBe(true);
    expect(isStaleDeploymentError(Object.assign(new Error('boom'), { name: 'UnrecognizedActionError' }))).toBe(true);
    expect(
      isStaleDeploymentError(
        new Error('Failed to find Server Action "x". This request might be from an older or newer deployment.'),
      ),
    ).toBe(true);
  });

  it('matches a prod digest-only error shape', () => {
    expect(isStaleDeploymentError({ digest: 'Failed to find Server Action abc' })).toBe(true);
  });

  it('does NOT match ordinary errors (no false positives)', () => {
    expect(isStaleDeploymentError(new Error('PDF extraction timed out'))).toBe(false);
    expect(isStaleDeploymentError(new Error('Network request failed'))).toBe(false);
    expect(isStaleDeploymentError(new Error('Could not read that PDF'))).toBe(false);
    // a generic 404 WITHOUT the 'server action' context must NOT trip the detector
    expect(isStaleDeploymentError(new Error('Resource was not found on the server'))).toBe(false);
    expect(isStaleDeploymentError(null)).toBe(false);
    expect(isStaleDeploymentError(undefined)).toBe(false);
    expect(isStaleDeploymentError('a string')).toBe(false);
    expect(isStaleDeploymentError({})).toBe(false);
  });
});
