import type { SemanticMapping } from './ir';
import { canonicalSha256 } from './canonical';

export function templateTwinMappingsSha256(
  mappings: readonly SemanticMapping[],
): string {
  return canonicalSha256(
    [...mappings].sort((a, b) => a.fieldId.localeCompare(b.fieldId)),
  );
}
