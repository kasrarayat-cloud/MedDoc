---
id: A12-P1-004
title: No threat model document; no Architecture Decision Records (ADRs)
severity: P1
domain: docs/security-architecture
---

# Issue

QuillMD handles PHI under HIPAA. The repository has **no threat model**, **no STRIDE/DREAD analysis**, **no asset register**, and **no ADRs** (Architecture Decision Records). HIPAA §164.308(a)(1)(ii)(A) requires a written risk analysis. The HIPAA matrix in `docs/HIPAA_COMPLIANCE.md` is finding-driven, not threat-driven — it tracks remediation status against named findings (h7b, h8, h13, etc.) without a documented systematic enumeration of threats from which the findings derive.

ADRs matter for a different reason — most architectural decisions have load-bearing context that lives in commit messages or in Kasra's head. When the next engineer wants to understand why postgres is in a single bind-mount LUKS file rather than a Hetzner managed volume, the answer is in `RUNBOOK_ENCRYPTED_VOLUME.md` §0 prose; when they want to know why age was chosen over GPG, it's in `HIPAA_COMPLIANCE.md` h16 commentary; when they want to know why the rate limiter is in-process not Redis-backed, it's in `KNOWN_ISSUES.md` KI-4. These should each be standalone ADRs, dated and immutable, not buried in operational docs.

# Evidence

Threat model search:

```
$ find /opt/meddoc-pro -type f -iname "*threat*" -not -path "*/node_modules/*"
(no results)
$ find /opt/meddoc-pro -type f -iname "*risk-analysis*"
(no results)
$ find /opt/meddoc-pro -type f -iname "*stride*"
(no results)
$ find /opt/meddoc-pro -type f -iname "*asset-register*"
(no results)
```

ADR search:

```
$ find /opt/meddoc-pro -type d -name "adr"
(no results)
$ find /opt/meddoc-pro -type d -name "decisions"
(no results)
$ find /opt/meddoc-pro -type f -name "ADR-*"
(no results)
```

What exists in lieu of a threat model:

- `docs/HIPAA_COMPLIANCE.md` — finding-driven matrix (h-finding IDs from prior audits). Does not enumerate the threats from which findings derived.
- `docs/AUDIT_T-M18.md` — point-in-time audit report. Useful but not a living model.
- `docs/deep-audit-2026-05-03/` and `docs/deep-audit-round2-2026-05-03/` — audit reports from prior rounds. Same shape as T-M18: findings, not threats.
- `docs/SECURITY-FIXES.md` — operational fix log (env-file permissions, etc.). Reactive.
- `LAUNCH_READINESS.md` §B — §-controls reviewed for one moment in time.

What exists in lieu of ADRs (decisions documented in the wrong place):

| Decision | Where it lives now | Should be ADR-NNN |
|---|---|---|
| LUKS-on-loop-file vs Hetzner managed vs full-disk | `RUNBOOK_ENCRYPTED_VOLUME.md` §0 + h8 commentary | ADR — PHI-at-rest encryption strategy |
| age vs GPG for offsite | `HIPAA_COMPLIANCE.md` h16 commentary | ADR — offsite encryption library |
| Backblaze B2 vs S3 vs Wasabi | `phase-6.2-backup-strategy.md` | ADR — offsite-backup vendor |
| In-memory vs Redis rate limiter | `KNOWN_ISSUES.md` KI-4 | ADR — rate limiter scope |
| Single-session enforcement | implicit in the code; not documented | ADR — auth session model |
| Server Actions vs API routes split | implicit in the codebase | ADR — request-handling pattern |
| Anthropic prompt cache 5-min TTL strategy | POST_MERGE_TODO §11 (Phase 5.2) prose | ADR — Coding Coach LLM cost model |
| Daily 03:00 UTC backup window | `phase-6.2-backup-strategy.md` | ADR — backup cadence + RPO commitment |
| MOCK_AI_CALLS for tests | comment in code + DEPLOYMENT_RUNBOOK §1.6 | ADR — test isolation strategy |
| meddoc-pro decommission | POST_MERGE_TODO §21 | ADR — product line decommission |
| Phase 5 → Phase 7 Linear V1 → Apple Product migration | POST_MERGE_TODO §8 + §13 | ADR — design-system theming strategy |
| Single-VPS architecture (no horizontal scaling) | implicit | ADR — scaling posture for pilot |
| `RxWarning` 3-band → 4-band severity mapping at component boundary | POST_MERGE_TODO §9 prose | ADR — pharmacology severity taxonomy |

# Risk

- **HIPAA**: §164.308(a)(1)(ii)(A) "Conduct an accurate and thorough assessment of the potential risks and vulnerabilities" — current answer is "we run periodic audits and address findings." OCR considers periodic audits part of the program, not the risk-analysis itself. Without a written, dated, threat-enumerated risk analysis, a Security Rule audit reveals a documentation gap.
- **Decision provenance**: when next engineer asks "why this and not that", the answer is in someone's head or in a runbook. ADRs make decisions immutable + dated + reviewable.
- **Architectural drift**: without ADRs, large swings (e.g. Phase 5 → 7 redesign) happen without a written record of what was rejected and why. Future-self can't audit the alternatives considered.
- **Audit defensibility**: a threat model that enumerates assumed adversaries (curious doctor, malicious doctor, compromised SaaS provider, ransomware, BGP attack, insider) and the controls in place for each gives an OCR examiner a map; the absence forces the examiner to assemble the map from findings — and any gap they notice becomes a finding.

# Recommended fix

**Threat model.**

Create `docs/THREAT_MODEL.md` (or `docs/security/threat-model.md`). Use STRIDE per asset class:

```
## Asset 1: PHI in transit
| Threat | Mitigation | Owner | Verified |
| Spoofing | TLS 1.2+ via Caddy with HSTS preload | platform | Phase 13 |
| Tampering | TLS provides integrity | platform | Phase 13 |
| Repudiation | audit_logs row per access | platform | T-M16 |
| Information disclosure | no plaintext path; Caddy redirect 80→443 | platform | Phase 13 |
| DoS | rate-limit (KI-4 caveat) | platform | T-M18.3 |
| Elevation | NextAuth + single-session + bcrypt-12 | auth | T-M19 |

## Asset 2: PHI at rest in Postgres
| ... |

## Asset 3: PHI at rest in MinIO (audio)
| ... |

## Asset 4: PHI at rest in Backblaze B2
| ... |

## Asset 5: PHI in transit to Anthropic / Deepgram / OpenAI
| ... |

## Asset 6: Audit log integrity
| ... |

## Asset 7: AI-output integrity (hallucination, prompt-injection)
| ... |
```

Each row links to the runbook + the section of HIPAA_COMPLIANCE.md that addresses it.

Adversaries to enumerate:
- Curious doctor (own-tenant)
- Malicious doctor (cross-tenant probe)
- Compromised SaaS provider (Anthropic / Deepgram / OpenAI / Resend / Backblaze)
- Compromised registrar (DNS hijack — see A12-P1-001 Scenario 6)
- Ransomware on the host
- BGP attack on the apex
- Insider (Kasra rotates out)
- Subpoena (compelled disclosure — note BAA limits)
- Patient (subject access request, deletion request)

**ADRs.**

Create `docs/adr/` directory. Use the standard Michael Nygard format (Title / Status / Context / Decision / Consequences). Numbered sequentially; never deleted; superseded by later ADRs which link back.

Backfill the ~13 decisions enumerated in the Evidence table — pull the prose from the runbooks/POST_MERGE_TODO and lift it into a self-contained ADR. Each ADR is one page max. The runbook prose can stay; it gets a "see ADR-NNN for the decision rationale" pointer at the top.

Add an `adr/README.md` index linking each ADR. Add a sentence in `docs/ONBOARDING.md` (per A12-P1-003) telling new engineers to start with the ADR index for "why is it like this."

Add to the AGENTS.md / contributor guide: every meaningful design choice in a PR review must either reference an existing ADR or include a new one. (For PRs that don't change architecture, no ADR required; the choice surfaces in PR review.)

For both the threat model and the ADRs, mark them as "first version 2026-05-XX, reviewed quarterly". Quarterly review attaches to the existing rotation cadence in `ROTATION_RUNBOOK.md`.
