import { createHash } from 'node:crypto';

/**
 * SHA-256 hex digest of the full prompt (system + user concatenated).
 * Used in AiCall.promptHash so we can correlate retries without
 * persisting the PHI-carrying prompt text itself.
 */
export function hashPrompt(system: string, user: string): string {
  return createHash('sha256')
    .update(`${system}\n---\n${user}`, 'utf8')
    .digest('hex');
}
