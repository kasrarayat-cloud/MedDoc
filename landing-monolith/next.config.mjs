/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export → plain HTML/CSS/JS served by host nginx from
  // /var/www/quillmd-staging. No server runtime, no container.
  output: 'export',
  // Static export can't use the Next image optimizer; we self-host
  // pre-sized assets and reference them directly.
  images: { unoptimized: true },
  // Emit /path/index.html so nginx serves clean URLs without a rewrite.
  trailingSlash: true,
  reactStrictMode: true,
};

export default nextConfig;
