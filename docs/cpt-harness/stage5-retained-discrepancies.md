# CPT harness, Stage 5.1: the retained discrepancies, reproduced and classified (before the harness)

Evidence for checklist item 5.1. These are the discrepancies the round-3 live walk (2026-10-31, `80df1831d168`) and the
round-4 work left standing. Each was reproduced offline: by the round-4 H1 replay of the retained live inputs (the
regression set h4-01 to h4-06, h2-08, h2-10), and, for Corti, from the retained requests and responses (round-4 item 4).

**Where the evidence is:**
- `docs/foundation/reports/2026-10-31-cpt-studio-gi3-install.md` ("Provider omissions (Corti), kept separate");
- the round-4 declarations in `cpt-studio/tests/fixtures/gi4/declarations/*.json`, including the cycle-2 amendments with
  their H1 tables;
- the round-4 Wave 1 cycle-2 reports, recorded in the checklist's progress log.

**Classification.** Each discrepancy is an APPLICATION error (one of CPT Studio's own readers), a PROVIDER omission
(Corti did not propose the expected code), or a DOCUMENTATION question (the document itself does not settle it).

## Classification

| # | document | discrepancy | class | how it was reproduced | state after round-4 cycle 2 (projected) | what harness@2 is expected to do |
|---|---|---|---|---|---|---|
| 1 | h4-01 | 99204 held: E/M basis not read | APPLICATION (the visit reader). The note documents 52 minutes and a moderate level, and the reader reads neither | H1 replay; round-4 PV1 cycle-2 report | still held: the PV1 C1/C2 release was dropped after two non-converging refutation cycles | a participant locates the time or level passage. A reviewer confirms it as the answer to the em_basis question (HARNESS.md 11.3). The hold changes only on that confirmation |
| 2 | h4-03 | date of service: 4 HARD `date.sends-only-the-truth` failures | APPLICATION (the date reader) | H1 replay (installed 13/17 HARD) | 13/17 as installed: the PD strong-head hold was dropped | a participant's located date offered for the date question. A confirmation enters it as the member's date through the existing context safeguards |
| 3 | h4-06 | 45385 held on extent | APPLICATION (the extent reader) | H1 replay; PI cycle-2 report | still held: the PI E1 release was dropped | a located extent passage offered for the extent question; reviewer confirmation |
| 4 | h4-03 | 43244 held on extent | APPLICATION (the extent reader) | H1 replay; PI cycle-2 report | still held (E1 dropped) | as row 3 |
| 5 | h4-05 | no EUS code (43259 expected) | PROVIDER (Corti proposed no EUS code; every proposal was another family's alternative). Also APPLICATION: CPT Studio's reader marked the EUS historical | retained Corti request and response | unchanged | Astra or Fable may propose 43259 with located evidence. It keeps the participant's origin and is evaluated on the same path. If the reader's "historical" reading holds or excludes it, the status correction (11.3) or the existing Reinstate applies |
| 6 | h4-02 | no EGD with biopsy (43239 expected beside 45331); Corti selected 45330 | PROVIDER | retained Corti request and response | unchanged; 45330 still needs a clarification | a participant may propose 43239 with located evidence, keeping its origin |
| 7 | h2-10 | ERCP stent exchange: Corti 43274 where 43276 is expected | PROVIDER, and APPLICATION: the inventory reads no stent-exchange act (PA3: `act_missing`) | round-2 record; PA declaration | 43274 READY as installed; 43276 not proposed | a participant may propose 43276. Whether it can be READY depends on the inventory reading the exchange; otherwise it holds, with the correction path available |

## What is NOT claimed

- **No expected code here was set by a qualified coder.** The expectations are the synthetic documents' authors'
  provisional ones (SOFT in the H1 tables). Clinical validation therefore remains NOT ESTABLISHED (checklist, final
  verdicts).
- **The "harness@2 is expected to do" column is a design expectation, not a result.** Each row is measured again on the
  harness release, offline first, then live (5.3, 6.3).
