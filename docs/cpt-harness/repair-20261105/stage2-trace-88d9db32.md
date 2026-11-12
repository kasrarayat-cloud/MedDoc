# Harness repair (owner directive 2026-11-05): stage 2, the trace of encounter 88d9db32

Traced by session a12d8fb3 on 2026-11-05 from the protected records of
`https://cpt.quillmd.com/#doc/88d9db32-65b5-4a55-98ee-b82ce0da8941`: the retained raw response bytes of every provider
run, each assessment's `participants` record, every proposal of the current assessment (`0e7c965b`, 07:43:47Z, sha256
`ab463654d147…`) and its completeness and clarifications. All read through a read-only transaction; the export sits in
the session's evidence directory and is reaped at close-out. This records what the records say, not what a model is
assumed to have done.

## What the document documents (read before any output)

A synthetic two-procedure report of 2026-11-04 by the endoscopist: an upper endoscopy to the second part of the duodenum
with through-the-scope balloon dilation of a Schatzki ring to 18 mm and cold-forceps biopsies of the gastric antrum and
body, then "The stomach was decompressed and the endoscope withdrawn."; and a colonoscopy to the cecum and terminal ileum
with a lift-assisted snare EMR of a 17 mm ascending-colon lesion (a prophylactic clip, no bleeding treated), a separate
7 mm sigmoid polyp removed by cold snare, a separate 5 mm distal-rectal mucosal patch sampled with cold biopsy forceps
("it was not excised by snare"), and a submucosal tattoo injected 3 cm distal to a separate 12 mm transverse-colon
abnormality that was left in place ("separate from the saline lift performed for the ascending-colon EMR"). Monitored
anesthesia care was given by the anesthesia service. The session's provisional reading, before any output was read:
43249, 43239, 45390, 45385, 45380 and 45381, each one unit; the lift injection and the clip are part of the EMR; the
decompression at withdrawal has no separate code; the anesthesia is another provider's service. This is the session's
reading, not a qualified coder's adjudication, and it is not used as an acceptance oracle.

## Where each service went

| documented service | Corti, first answer | Corti, bounded second review | Astra, first reading | Fable, first reading | peer reviews | CPT Studio, current assessment |
|---|---|---|---|---|---|---|
| balloon dilation, 43249 | not selected, not a candidate (its candidates include 43248) | not selected, though asked about the dilation | proposed (exact quotes) | proposed (exact quotes) | both support it, and add no code | an alternative of origin `participant`: D14 (`PARTICIPANT_NOT_ADDED`); the dilation left unresolved |
| gastric biopsies, 43239 | selected | selected again | proposed | proposed | no position taken | ready (Corti's proposal; both participants recorded as proposers) |
| ascending EMR, 45390 | not selected, not a candidate | not selected, though asked about the EMR | proposed | proposed | both support it | an alternative, D14; the EMR left unresolved |
| sigmoid cold snare, 45385 | not selected, not a candidate | not selected, though asked about the snare | proposed | proposed | both support it | an alternative, D14; the snare left unresolved |
| rectal biopsy, 45380 | selected | selected again | proposed | proposed | no position taken | ready, but its act is labelled "at the rectum, sigmoid colon": the comparison "separate from the sigmoid polyp" was read as a second biopsy site |
| transverse tattoo, 45381 | selected | selected again | proposed | proposed | no position taken; both answer CPT Studio's tattoo question as performed (Fable "performed"; Astra in words: the tattoo was performed and "not resected today" refers to the lesion) | held (`needs_clarification`): a false conflict, the lift injection read as performed against the Impression's "marked with submucosal tattoo for future localization and not resected today" read as a negated tattoo |
| gastric decompression | — | asked about it; no code | no code | no code | — | unresolved: the inventory reads a performed decompression act in the upper endoscopy, and the coverage catalogue has no upper-endoscopy code that accounts for one, so nothing can resolve it |

So the facts are:
- **Corti omitted 43249, 45390 and 45385, twice.** Its first answer selected 45380, 45381 and 43239 (with diagnoses) and
  listed 43248, 99204, 45331, 99214 and four quality codes as candidates, with no per-code alternatives. The second
  review, whose scope named exactly the dilation, the decompression, the EMR and the snare, selected the same three CPT
  codes and listed 45378, 99204, 99213, 99214, 91110, 45331 and quality codes as candidates.
- **Astra and Fable each proposed all six, independently.** Both first readings were read (`state: read`, no
  unverified quote; Fable's answer arrived inside a json code fence, which CPT Studio's parser accepts) and frozen
  before the peer reviews (`frozen`, `reading_sha256` recorded). Both readings also list, under not-coded, the codes of
  the EMR's own components (45381 for the lift injection, 45385 for the snare inside the EMR, 45382 for the clip) as
  included, and the transverse abnormality's resection and the historical colonoscopy as not performed at this
  encounter; those are per-occurrence entries, not contradictions of their proposals. Fable states modifier 59 on
  43239, 45385, 45380 and 45381; Astra states one modifier on 43239, 45385, 45380 and 45381. Stated modifiers are
  recorded and never used.
- **The three were lost at CPT Studio's D14 gate**, not at a reader: `engine._Harness.merge` lists every participant
  code no decidable proposal carries as an informational alternative ("Proposed by Astra and Fable (independent
  participants), but not added as a proposal: …"), by design since 2026-11-03.
- **45381's hold and 45380's anatomy are shared-reader defects**, reproduced offline on unpatched `main` (below).
- **The decompression item is a catalogue and reconciliation gap**, not an omission by any participant.

## Offline reproduction (stage 3's starting point)

`reassess_offline.sh` restores a read-only dump of the live database (taken 09:15:40Z) into a throwaway database on the
test server and runs `reassess_retained --participants astra,fable`, then one worker pass with every provider unable to
send. Provider runs stayed 107 (97 sent) in each run.

| tree | 43239 | 45380 | 45381 | 43249 / 45390 / 45385 | unresolved |
|---|---|---|---|---|---|
| `main` 8645fd54 (the served readers) | ready | ready, "at the rectum, sigmoid colon" | held, the tattoo conflict | alternatives (D14) | dilation, decompression, EMR, snare |
| `main` + the package's accepted `repair.patch` | ready | **held**: a new false hold (below) | **ready** | alternatives (D14) | the same four |

The package's patch reproduces exactly what it claims on this encounter (the tattoo conflict gone; the biopsy's act
"of the 5 mm erythematous mucosal patch in the rectum"), and on Corti's actual evidence it also moves 45380 from ready to
held: Corti cites "cold biopsy forceps for histology; it was not excised by snare.", the routing-era reader reads an
unresolved negation there, and `engine._negation_resolved`, which released that doubt before the patch, now refuses
because the documented-service reader correctly reads the denied snare excision of the same patch in that passage, and
the release refuses on any not-done act it overlaps, of whatever kind. That is the same class as the tattoo and
resection defect: a denial of one act read as a doubt about another. It is repaired in stage 3 with its controls.
