# Bounded source-policy refutation — 2026-09-28

Reviewed frozen dirty source on `dd6b4a7a82df30909dd949a652211a52d3cf9491` in `/opt/meddoc-pro/.worktrees/v1-document-relations`. Read-only: no source, database, provider, corpus, deployment or policy activation changes. This pass is complete; it is not a full clinical/Word rendering qualification.

## Demonstrated counterexamples

1. **Section boundary leaks patient authorship.** `rebuild/documents/source_policy.py:27` assigns a role before the `elif` at lines29–31 can test a section ending in that same paragraph. Input: body paragraph `For the patient:` with `w:pPr/w:sectPr`, followed by paired table `What progress was observed?` in the next section. Output: table answer gets `source_author=patient`, bound to the preceding section's role. A distinct empty section-break paragraph correctly clears the role. This is classification of XML structure, not a native Word display observation.
2. **Ordinary example clears patient authorship.** `source_policy.py:29` considers any initial `For ...:` a role boundary. Input: body `For the patient:`, then ordinary unstyled `For example: describe changes since your last visit.`, then the paired question. Output: question has no answer policy. No new author role, heading or section was supplied. The original role-only positive gets patient policy.
3. **Clinician review of a symptom report becomes patient document-review attestation.** `source_policy.py:54`–58 matches token order without tying review to the patient as reviewer or to the form being completed. Input: paired label `Confirm the patient report of chest pain was reviewed by the clinician.` Output: `attestation=document_review`. The statement concerns the clinician reviewing a symptom report; it does not assert that the patient has seen this document. This is a wrong policy classification, not a claim that the program filled an unsupported answer.

All three reproduce through the actual standalone worker, whose result reports `landlock+seccomp`, exit0 and empty stderr. The unchanged positive also succeeds through that worker.

## Controls and limits

`probe.py` ran15 finite component cases. Eleven initially matched exact expectations, three are the classifications above, and the remaining exact-error-code mismatch is **not a defect**: patient signature writes were safely refused with `invalid_answer` rather than the probe's anticipated `protected_signing_area`. Thus12/15 substantive controls held. Changed author and attestation source text each refuse export with `mapping_mismatch`; unchanged source exports. Complete attestation text is retained. Ordinary patient mentions do not assign authorship; actual role/heading/distinct-section boundaries clear it. No additional counterexample demonstrated in these lenses.

Source SHA256 before and after the component probes are identical in `01-results.json`. `02-sandbox-results.json` retains four actual worker results. No filled document was written to Git; synthetic scratch DOCX files existed only in our session TMPDIR and were removed by their TemporaryDirectory context.

## Exact replay commands

From `/opt/meddoc-pro/.worktrees/v1-disposition-integration`:

```
/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python -B rebuild/.runtime/source-policy-refutation/probe.py
/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python -B rebuild/.runtime/source-policy-refutation/sandbox_probe.py
```

The component probe denies socket connect and sets QUILLMD_ENV_MANAGED=1. Standalone workers receive only PATH/LANG/TZ and use the repository's actual sandbox. The scripts bind their source path explicitly to the reviewed root tree; replay against another snapshot must change only that path in a new copy and retain originals.
