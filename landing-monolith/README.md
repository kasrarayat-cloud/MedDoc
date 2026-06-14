# QuillMD — "Obsidian Monolith" landing (staging)

A net-new, cinematic dark marketing landing for **staging.quillmd.com**. Self-contained
Next.js static export — **not** part of the npm workspace, and it touches nothing in
production (quillmd.com / app.quillmd.com / the app pipeline / co-tenant vhosts are all
unaffected). Skin/marketing only.

## Design
Obsidian black canvas (`#06070A`), gold (`#E8B85C`) + turquoise (`#3FD8C8`) as the only
accents, sharp edges, ray-traced glass + volumetric glow. Type: **Anton** (ultra-bold
condensed display), **Manrope** (body), **IBM Plex Mono** (terminal/data) — all self-hosted
via `next/font`. Sections: Hero (monolith reveal + mouse-tracked glow) · Live Sandbox
(waveform + a SOAP note typing itself) · The Note's Journey (RECORD→DRAFT→VERIFY→SIGN node
graph) · Security (cyber-vault, true claims only) · Terminal CTA (a real accessible email
form styled as a command line). Responsive, visible keyboard focus, `prefers-reduced-motion`
respected (all motion degrades gracefully; content is visible without JS).

## Develop
```bash
npm install
npm run dev      # http://localhost:3210
```

## Build (static export)
```bash
npm run build    # → out/   (plain HTML/CSS/JS, self-hosted fonts + assets)
```

## Images
Two Higgsfield renders are self-hosted in `public/assets/`:
- `hero-monolith.*` — floating obsidian-glass prism with internal gold/turquoise data streams.
- `security-vault.*` — cybernetic glass padlock encrypting data streams.
On-brand SVG **placeholders** ship in the repo; drop the real images in (same basenames),
update the two `<img src>` in `components/Hero.tsx` + `components/Security.tsx`, rebuild.

## Deploy
See `deploy/deploy-staging.sh` and `deploy/staging.quillmd.com.nginx.conf`. The static
export is served by host nginx from `/var/www/quillmd-staging` behind a Let's Encrypt cert —
exactly the `leathererp-landing` static-vhost pattern. A specific `server_name` with **no**
`default_server` means the vhost cannot affect any other site.

**Preconditions (Kasra):** DNS `staging.quillmd.com A 147.189.172.8`, and the two image URLs.

## Teardown
```bash
# remove the vhost + cert + files; nothing else is affected
rm /etc/nginx/sites-enabled/quillmd-staging && nginx -t && nginx -s reload
rm /etc/nginx/sites-available/quillmd-staging
rm -rf /var/www/quillmd-staging
certbot delete --cert-name staging.quillmd.com
```
