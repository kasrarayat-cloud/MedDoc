# Protected export read-back and retained voice fixture

This narrowly repairs two exact CI failures on `7907ae5aa38c2a6c9e27eab1b09a758df315125b`. It does not change generation, source ownership, the frozen note corpus, its gold answers, the human signing guard, or any provider request.

The stage's independent export reader now treats `write_protected` destinations as preserved original content. A proposed automatic answer there remains a failed read-back, including when its displayed checkbox already matches the proposed answer. The frozen r1-11 fixture uses the existing hash-bound prospective Consent exclusion; an independent ordinary Smoker checkbox retains reviewed-blank unticking and unreviewed preservation. Direct fills of the untouched frozen Consent mapping remain refused for both checked and unchecked values. An erased existing human-owned check also fails read-back.

The original voice selector retains its raw transcript, raw provider response, no-proof zero-answer control and held correction controls. Its explicitly reviewed replay now pins the two exact supported values and Assessment citation rather than the obsolete scalar count of one. The raw transcript says strain rather than the audio's sprain; this fixture establishes source fidelity after review, not transcription accuracy or human microphone acceptance.

The DB/network-blocked packet executed all ten export-reader methods plus the exact historical voice selector: 11 passed in 17.945 seconds, real exit 0. No database, renderer, provider request, installed surface or full-CI claim is made.

Raw evidence is preserved below `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/clinical/voice-retained-003-005/`:

| Artifact | SHA-256 | Result |
| --- | --- | --- |
| `ci-export-readback-original-7907.log` | `254426c64806edf75fb273ca7c0812b0e85541f7aa8ddc0e48a2612c163f7686` | Original 8 methods: 9 errors and 1 failure; exit 1 |
| `ci-voice-usefulness-original-7907.log` | `5cf79bc67f080a25945f96d8d2dbf8fcd19d8aeebc23b0307316639f225a751d` | Original exact selector: 2 != 1; exit 1 |
| `ci-voice-usefulness-capture-7907.json` | `a9b09d9aa300aa88f53cd4ec8f3e2c41b954ab23836f75a83512576554266ecb` | Separate unchanged-source capture, exit 0 |
| `ci-checker-repaired-first.log` | `98fb3d8a5252c71e8aefb61457d9752d012cc791b9afacbd357237455840c3a5` | Repaired focused 11-method packet, exit 0 |

The original official CI failure blocks remain at `operations/ci-7907ae5a-20261004/support-failure-blocks.json` (SHA-256 `3c4db430ec10827a1576e3c575e4f584e0bacb117b1364670145deaa2b920897`) and `core2-failure-blocks.json` (SHA-256 `8f7dfeb6bcaa3644694462571c8afff46046c4508437e40e592969c272e5d832`). The original eight export methods remain present; two protected-source controls supplement them without replacing their historical outcomes.
