import Link from 'next/link';
import { APP_URL, APP_SIGNUP_URL } from '@/lib/constants';
import { QuillMark } from './QuillMark';

const LINKS = [
  { href: '/#how', label: 'How' },
  { href: '/#features', label: 'Features' },
  { href: '/#compare', label: 'Vs. others' },
  { href: '/#security', label: 'Security' },
  { href: '/#pricing', label: 'Pricing' },
  { href: '/#faq', label: 'FAQ' },
];

export function Nav() {
  return (
    <nav className="top">
      <div className="container nav-inner">
        <Link href="/" className="brand">
          <span className="brand-quill">
            <QuillMark gradientId="navQuill" />
          </span>
          <span>
            Quill<em>MD</em>
          </span>
        </Link>
        <div className="nav-links">
          {LINKS.map((link) => (
            <Link key={link.href} href={link.href}>
              {link.label}
            </Link>
          ))}
        </div>
        <div className="nav-cta">
          <a href={APP_URL} className="btn btn-ghost">
            Sign in
          </a>
          <a href={APP_SIGNUP_URL} className="btn btn-primary">
            Start free trial <span className="arrow">→</span>
          </a>
        </div>
      </div>
    </nav>
  );
}
