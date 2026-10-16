# Prospective declaration: isolated Corti replay on normal HTTPS

Authority: the user's current instruction expressly authorizes installing verified
candidate 1a44df32d behind authenticated synthetic-only access on normal HTTPS,
without rebuilding or repeating the completed replay campaign. The new descendant
adds only a separate draft Word export, candidate prefix isolation and installation
mechanism. It does not activate Corti or CPT in the existing dashboard.

Execute through scripts/run-ruled-mutation.sh, calling the committed
rebuild/ops/corti_https_install.py. This is a new bounded installation authority;
no prior consumed provider allowance, native promotion packet, or funding is reused.
The current worktree HEAD is the exact candidate source archive and health revision.
All changes are in the isolated feature worktree. Main and the native release are
not promoted, rebuilt or edited.

Expected changes:
- New root-owned candidate source under /opt/quillmd-corti-candidate/releases/HEAD.
- New private state copy at /var/lib/quillmd-corti-candidate and root-only isolated
  environment at /opt/quillmd-corti-candidate/environment. No provider credentials.
- New DynamicUser quillmd-corti-candidate.service on existing loopback port 9146
  and equally confined quillmd-corti-candidate-worker.service,
  with no capabilities, no Docker access, protected filesystem and local-only IP
  access. It replaces only the two positively identified detached candidate
  processes. The worker supports only fixture/replay work; it has no external credentials.
- Reuse only the existing test_quillmd_corti_workflow database at port 55449;
  give its existing dedicated container restart policy unless-stopped.
- Add only /synthetic/corti to app.quillmd.com nginx routing, using the existing
  managed-helper publication pattern, nginx -t and nginx reload. Original ingress
  SHA256 a6b45d31a328559d8b37de6281683ec60201c880191fef758347827edc5f73eb
  must match. Invalid nginx publication restores the captured original.
- Candidate sessions/CSRF are secure, distinct and scoped to the prefix;
  ordinary account authentication and clinician/patient authorization remain.
- Verification may create candidate login sessions/audit rows and the separate
  draft export cache only. No new coding requests or clinical generation.

Must remain unchanged:
- Existing native doctor/admin/worker process identities and '/' ingress block;
  main commit, existing ICD workflow, native configuration and clinical database.
- Retained original Corti response, hashes, FAIL verdict, adapter/parser evidence;
  original clinical Word and approved R12-only export bytes; saved coding decision.
- Held 99213 stays excluded from approved export. K59.00 remains rejected.
- No purchase, vendor communication, real-patient activation or provider call.

Validation: focused new draft/prefix checks, existing approved-export byte check,
then ordinary clinician HTTPS sign-in and actual original/approved/draft downloads
on desktop/mobile. Do not repeat the completed replay campaign or rebuild. Record
source revision, endpoint, unit identity, ingress hashes, download hashes and
preserved evidence. A synthetic draft is never an approved CPT document.

Rollback: remove this exact prefix addition using the captured ingress hash as a
concurrency guard, nginx -t/reload, stop/disable only the two new candidate units.
Retain candidate source, state and all evidence. Native services are not restarted.
