import './final.css';

// final.css is imported here so it loads ONLY on the /final route — the root landing,
// /motion, /heroes and /structures stay byte-identical. The page carries S2's type (global
// Manrope + IBM Plex Mono from the root layout), so no extra font is loaded.
export default function FinalLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
