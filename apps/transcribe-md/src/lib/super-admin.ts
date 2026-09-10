// ============================================================================
// WHO IS A PLATFORM SUPER_ADMIN — ONE PREDICATE, EVERY READER
// ----------------------------------------------------------------------------
// A platform SUPER_ADMIN is an account whose `products[]` contains
// `Product.SUPER_ADMIN`, read FROM THE DATABASE ROW. That is what both admin
// gates admit on (lib/admin-api-gate.ts, app/admin/layout.tsx), and it is the
// only thing grant-admin / revoke-admin write.
//
// `users.role === 'SUPER_ADMIN'` is a DIFFERENT fact: the practice RBAC role
// that /system-admin reads. The MFA-disable lock was keyed on the role while
// both gates were keyed on products. In production, both platform
// SUPER_ADMINs are role DOCTOR, so the lock guarded accounts the gates do not
// treat as admins and missed the ones they do (PR #952 refutation round,
// lockout[1]). One rule, several readers: the readers disagreed while every
// arm stayed green.
// ============================================================================

import { Product } from '@prisma/client';

/** True iff `products` is an array containing `Product.SUPER_ADMIN`.
 *  Anything else (null, undefined, a string, an object) is false. It fails
 *  closed, and a bare string 'SUPER_ADMIN' does not pass by substring. */
export function hasSuperAdminProduct(products: unknown): boolean {
  return Array.isArray(products) && products.includes(Product.SUPER_ADMIN);
}

/** The MFA-disable lock: a platform SUPER_ADMIN may not remove its own factor,
 *  because both admin gates admit on it.
 *
 *  ⚠️ The legacy `role === 'SUPER_ADMIN'` lock is KEPT alongside the product
 *  predicate. Dropping it would let those accounts disable MFA they cannot
 *  disable today. That widens, and this repair never widens. */
export function isMfaDisableLocked(user: {
  products: unknown;
  role: string | null | undefined;
}): boolean {
  return hasSuperAdminProduct(user.products) || user.role === 'SUPER_ADMIN';
}
