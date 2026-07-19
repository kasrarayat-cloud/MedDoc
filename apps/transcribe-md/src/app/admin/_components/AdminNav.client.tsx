"use client";

// ============================================================================
// Top-bar nav for the /admin/* surface
// ----------------------------------------------------------------------------
// Secondary nav strip below the main TopNav. Moves the operator between
// Overview, Users, API Usage, Threats, and HIPAA. Active link is rendered
// as a sage underline tab in the Linear V1 dark canvas.
//
// Placement: each page.tsx renders this just below its own header.
// Lightweight client component — only `usePathname` makes it client-only.
//
// Phase 5 (Linear V1 Faithful) — Phase 4's `theme` prop has been retired
// because every surface now renders against the same dark canvas.
// ============================================================================

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/usage", label: "API Usage" },
  { href: "/admin/threats", label: "Threats" },
  { href: "/admin/hipaa", label: "HIPAA" },
  { href: "/admin/template-twin-release", label: "Template Twin release" },
] as const;

export default function AdminNav() {
  const pathname = usePathname();
  return <LinearAdminNav pathname={pathname} />;
}

function isActive(href: string, pathname: string): boolean {
  // Match exact (/admin) or prefix (/admin/users → matches /admin/users/anything)
  return href === "/admin"
    ? pathname === "/admin"
    : pathname === href || pathname.startsWith(`${href}/`);
}

function LinearAdminNav({ pathname }: { pathname: string }) {
  // Linear V1 secondary nav strip — sage underline on active tab,
  // mono-cap labels match admin-v1.html's tabbar idiom.
  return (
    <nav className="border-b border-linear-border bg-linear-surface-1">
      <div className="mx-auto max-w-[1440px] px-6">
        <ul className="-mb-px flex items-center gap-1">
          {ITEMS.map((item) => {
            const active = isActive(item.href, pathname);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={
                    "inline-flex h-11 items-center border-b-2 px-3 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage " +
                    (active
                      ? "border-linear-sage text-linear-text"
                      : "border-transparent text-linear-text-3 hover:text-linear-text-2")
                  }
                >
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
