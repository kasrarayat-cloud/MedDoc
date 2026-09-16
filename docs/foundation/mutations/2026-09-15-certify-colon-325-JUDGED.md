# RULED-ACT JUDGMENT — RULING C colon-note certify + activate (`2026-09-15-certify-colon-325.md`)

**Judged read-only against production, 2026-09-16.** The act ran inside
`transcribe-md-worker` at revision `e07caca7` (== the declaration's tree HEAD;
guard 3 verdict `ok — equals`). Declaration committed `9beec7a1` at
`2026-09-15T18:05:40Z`; act started `2026-09-15T20:10:33Z` — commit provably
precedes the act.

## Verdict: 10 of 10 declared rows correct. The owner's colon operative note is CERTIFIED + ACTIVE through the real path.

| declared | expected | observed | ✓ |
|---|---|---|---|
| `note_templates` | 21 → 22 | 22 | ✓ |
| new active "Colonoscopy Operative Note" | `8f027c50…` active | `8f027c50-70ac-41cc-a0e5-86582a7a806b` status=active | ✓ |
| prior `cmu1tpvsj…` status | active → inactive (kept) | inactive | ✓ |
| `template_twin_certifications` | 6 → 7 | 7 (`cmu33yrle…`, certifiedById = owner, certifiedAt `20:12:19.634Z`) | ✓ |
| `pdfNativeCertified` templates | 7 → 8 | 8 | ✓ |
| new compiled version `certificationStatus` | CERTIFIED | CERTIFIED (`4de6f662…`, round-trip verified `20:12:19.486Z`) | ✓ |
| owner active templates | stays 1 | 1 (= the mint) | ✓ |
| `transcribe_visits` | 70 (unchanged) | 70 | ✓ |
| signed visits | 41 (unchanged) | 41 | ✓ |
| `patients` | 0 | 0 | ✓ |
| `8e22a23d…` | stays inactive | inactive | ✓ |

The auto path behaved exactly as the inspect rehearsal predicted:
`auto-confirm: confirmed=16 declined_visitMetadata=8 declined_other=0` — every
clinical field conceptable under REGISTRY-3 + #324 + #325, only the eight
record-derived headers declined (the #247 human-confirm the ruled act performs).
`pdf-native certify: anchors=12 missing=1` — `certifyPdfTemplate` is
bytes-authoritative and certifies on anchors>0, so the one non-re-anchoring
label is expected and harmless. Synthetic round-trip PASSED.

## The process hung after the act; the ACT did not fail

The script printed its whole transcript through `[323] DONE newTemplateId=…` at
`20:12:19Z` and then **did not exit** for 5h24m, held alive by an open pg pool
handle — its success path never called `process.exit()`. The mutation door's
`docker exec` blocked on it in **silence**. The act had fully landed; nothing
said so and nothing timed out. Reaped by `SIGTERM` of the in-container node
runtime (pid 476, cmdline naming the certify script); the door then returned
exit 143 (128+SIGTERM). **Exit 143 is an artifact of the manual reap, not a
failure of the act** — verified by the 10/10 judgment above BEFORE the process
was touched.

Root-caused and fixed in the same batch (branch `fix/ruled-act-explicit-exit`):
`scripts/lib/exit-cleanly.ts` (scripts now exit explicitly) and
`scripts/lib/run-watched.sh` (the door now times out with "finished output but
did not exit" instead of waiting in silence). See that PR.

## RULING C — COMPLETE

REGISTRY-3 (#323), the multi-line-heading affordance (#324), the S2 numbered-slot
section binding (#325), and the certification of the owner's Colonoscopy
Operative Note are all shipped, judged, and live. `8f027c50…` is the active
operative note; `cmu1tpvsj…` is superseded and kept.
