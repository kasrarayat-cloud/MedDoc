// HANDOFF §2.1 — inline SVG icon set ported 1:1 from
// /tmp/design_handoff_quillmd_app/app/shell.jsx (`const Ic = { ... }`).
// Kept as a single barrel export so the rest of the redesign can call
// `<Ic.heart width={14} />` exactly as the prototype does. Every glyph
// uses currentColor so the caller's text color drives the stroke/fill.

import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement>;

const stroke = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};
const fill = {
  viewBox: '0 0 24 24',
  fill: 'currentColor',
};

export const Ic = {
  // nav
  home: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5" />
    </svg>
  ),
  users: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <circle cx="9" cy="8" r="3.3" />
      <path d="M2.5 20c0-3.2 2.9-5.5 6.5-5.5s6.5 2.3 6.5 5.5" />
      <circle cx="17" cy="7" r="2.6" />
      <path d="M15.5 14.5c3.2.2 5.5 2.2 6 4.5" />
    </svg>
  ),
  visits: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <rect x="3.5" y="4.5" width="17" height="16" rx="2.5" />
      <path d="M8 9h8M8 13h6M8 17h4" />
    </svg>
  ),
  template: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <rect x="3.5" y="4.5" width="17" height="16" rx="2.5" />
      <path d="M3.5 9h17M8.5 9V20" />
    </svg>
  ),
  settings: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  search: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  ),
  plus: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  ),
  check: (p: IconProps) => (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...p}
    >
      <path d="m5 12 5 5L20 7" />
    </svg>
  ),
  arrowRight: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M5 12h14M13 5l7 7-7 7" />
    </svg>
  ),
  arrowLeft: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M19 12H5M11 5l-7 7 7 7" />
    </svg>
  ),
  chevDown: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  ),
  chevRight: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="m9 6 6 6-6 6" />
    </svg>
  ),
  mic: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  ),
  upload: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
      <path d="M12 15V4M7 9l5-5 5 5" />
    </svg>
  ),
  download: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
      <path d="M12 4v11M7 10l5 5 5-5" />
    </svg>
  ),
  edit: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M4 20h4l10-10-4-4L4 16z" />
      <path d="m14 6 4 4" />
    </svg>
  ),
  copy: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <rect x="8" y="8" width="12" height="12" rx="2" />
      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
    </svg>
  ),
  more: (p: IconProps) => (
    <svg {...fill} {...p}>
      <circle cx="5" cy="12" r="1.5" />
      <circle cx="12" cy="12" r="1.5" />
      <circle cx="19" cy="12" r="1.5" />
    </svg>
  ),
  alert: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M12 3 2 21h20z" />
      <path d="M12 10v5M12 18v.01" />
    </svg>
  ),
  info: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 10v7M12 7v.01" />
    </svg>
  ),
  sparkle: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" />
    </svg>
  ),
  play: (p: IconProps) => (
    <svg {...fill} {...p}>
      <path d="M7 4v16l13-8z" />
    </svg>
  ),
  pause: (p: IconProps) => (
    <svg {...fill} {...p}>
      <rect x="6" y="4" width="4" height="16" rx="1" />
      <rect x="14" y="4" width="4" height="16" rx="1" />
    </svg>
  ),
  stop: (p: IconProps) => (
    <svg {...fill} {...p}>
      <rect x="5" y="5" width="14" height="14" rx="2" />
    </svg>
  ),
  star: (p: IconProps) => (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
      {...p}
    >
      <path d="m12 3 2.8 6 6.6.6-5 4.5 1.5 6.5L12 17l-5.9 3.6L7.6 14l-5-4.5 6.6-.6z" />
    </svg>
  ),
  shield: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6z" />
    </svg>
  ),
  clock: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  ),
  signature: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M3 17c3-5 5-9 7-9 3 0 1 6 3 6 2 0 4-3 6-3" />
      <path d="M3 21h18" />
    </svg>
  ),
  close: (p: IconProps) => (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      {...p}
    >
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  ),
  filter: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M4 5h16l-6 8v6l-4-2v-4z" />
    </svg>
  ),
  command: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M6 4a2 2 0 0 0 0 4h12a2 2 0 1 0 0-4 2 2 0 0 0-2 2v12a2 2 0 1 0 4 0 2 2 0 0 0-2-2H6a2 2 0 1 0 2 2V6a2 2 0 0 0-2-2z" />
    </svg>
  ),
  pill: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <rect x="3" y="9" width="18" height="6" rx="3" transform="rotate(-45 12 12)" />
      <path d="m8 8 8 8" />
    </svg>
  ),
  heart: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.5-7 10-7 10z" />
    </svg>
  ),
  bone: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M7 4a2.5 2.5 0 1 0-3 3 2.5 2.5 0 0 0 .5 3L14 19.5a2.5 2.5 0 0 0 3 .5 2.5 2.5 0 1 0 3-3 2.5 2.5 0 0 0-.5-3L10 4.5A2.5 2.5 0 0 0 7 4z" />
    </svg>
  ),
  nerve: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M4 6s2 2 4 2 4-4 8-4M4 12s2 2 4 2 4-4 8-4M4 18s2 2 4 2 4-4 8-4" />
    </svg>
  ),
  lung: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M12 3v9M8 21c-2 0-4-1-4-4V11c0-3 2-4 4-4s2 2 2 4v7c0 2-1 3-2 3zM16 21c2 0 4-1 4-4V11c0-3-2-4-4-4s-2 2-2 4v7c0 2 1 3 2 3z" />
    </svg>
  ),
  eye: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ),
  stethoscope: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M6 3v6a5 5 0 0 0 10 0V3M6 3h2M14 3h2M11 14v3a4 4 0 0 0 8 0v-1" />
      <circle cx="19" cy="13" r="2" />
    </svg>
  ),
  folder: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  ),
  trash: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <path d="M4 6h16M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14" />
    </svg>
  ),
  lock: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 1 1 8 0v3" />
    </svg>
  ),
  mobile: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <rect x="7" y="3" width="10" height="18" rx="2" />
      <path d="M11 18h2" />
    </svg>
  ),
  desktop: (p: IconProps) => (
    <svg {...stroke} {...p}>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </svg>
  ),
  dot: (p: IconProps) => (
    <svg {...fill} {...p}>
      <circle cx="12" cy="12" r="4" />
    </svg>
  ),
  wave: (p: IconProps) => (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      {...p}
    >
      <path d="M2 12h2M6 9v6M10 5v14M14 8v8M18 10v4M22 12h0" />
    </svg>
  ),
} as const;

export type IconName = keyof typeof Ic;
