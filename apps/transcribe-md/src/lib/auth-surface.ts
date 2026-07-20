import "server-only";

import { isAdminRequestHost, isPhysicianRequestHost } from "@/lib/admin-host";
import {
  isTemplateTwinAdminControlService,
  isTemplateTwinAdminAppService,
  isTranscribeMdPhysicianAppService,
} from "@/lib/template-twin/admin-app-service";

/**
 * Exact request origin for reading or refreshing an existing Auth.js session.
 * This is deliberately broader than login: the isolated control process may
 * parse the admin-host JWT claims before its bounded SQL verifier rechecks
 * them, but it still cannot accept a physician-host or unknown-process request.
 */
export function isSessionRequestAllowed(
  requestHeaders: Pick<Headers, "get">,
): boolean {
  if (isTranscribeMdPhysicianAppService()) {
    return isPhysicianRequestHost(requestHeaders);
  }
  if (isTemplateTwinAdminAppService() || isTemplateTwinAdminControlService()) {
    return isAdminRequestHost(requestHeaders);
  }
  return false;
}

/** Exact same-image login origin for the currently running service role. */
export function isLoginRequestAllowed(
  requestHeaders: Pick<Headers, "get">,
): boolean {
  if (isTemplateTwinAdminAppService()) {
    return isAdminRequestHost(requestHeaders);
  }
  return (
    isTranscribeMdPhysicianAppService() &&
    isPhysicianRequestHost(requestHeaders)
  );
}

/** Registration exists only on the ordinary physician service and host. */
export function isSignupRequestAllowed(
  requestHeaders: Pick<Headers, "get">,
): boolean {
  return (
    isTranscribeMdPhysicianAppService() &&
    isPhysicianRequestHost(requestHeaders)
  );
}
