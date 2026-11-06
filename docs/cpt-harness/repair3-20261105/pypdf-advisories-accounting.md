# CPT Studio's pypdf 6.21.2 advisories: accounted for, not resolved (harness repair 3, item 9)

Recorded by session a12d8fb3 on 2026-11-05, for the owner's second message of 2026-11-05: "resolve or account for the
PDF-security advisories (pypdf 6.21.2, interpretation 68) before claiming readiness for wider uploads".
**They are accounted for here. They are not resolved.** No readiness for wider uploads is claimed.

## What is installed, and why

CPT Studio runs pypdf 6.21.2 (`cpt-studio/requirements.txt`). Interpretation 68 deferred the move to 6.21.4, because four
reader rounds on 6.21.4 did not converge:
- round 4's refutation filed 13 findings, 6 major: checklist-row false holds and readings, and two cost overruns;
- the branch `fix/cpt-studio-pypdf-6.21.4-20261031` is kept unmerged with its records.

The trade-off is the owner's (class b), and it is unchanged:
- stay on 6.21.2 with the advisories below;
- accept round 4's false holds on some glyph-index and EUC-H checklist layouts to clear the audit;
- or fund further rounds.

The cpt-studio CI job's dependency audit is red on these seven, as on `main` since 2026-10-31. It is declared, not
concealed.

## The seven advisories (pip-audit with descriptions, 2026-11-05T22:3xZ)

| advisory | fixed in | class | what triggers it |
|---|---|---|---|
| CVE-2026-119203 | 6.21.4 | denial of service: infinite loop | opening an incomplete file without a `trailer` |
| CVE-2026-119204 | 6.21.4 | denial of service: large memory | parsing a page tree with many shared resources |
| CVE-2026-119205 | 6.21.4 | denial of service: infinite loop | cloning or duplicating a `DictionaryObject` |
| CVE-2026-119206 | 6.21.3 | denial of service: large runtime | retrieving the page labels of a file |
| CVE-2026-119207 | 6.21.3 | denial of service: large memory | loading an invalid dictionary |
| CVE-2026-119208 | 6.21.3 | denial of service: large runtime and memory | the page count of an encrypted PDF that declares a wrong `/Count` |
| CVE-2026-119209 | 6.21.3 | denial of service: large memory | opening a file with cross-reference streams |

All seven are availability defects triggered by a crafted PDF. None is a code-execution, disclosure or integrity defect.

## CPT Studio's boundary around them (read from the code at `1974c8cb1`)

- **Upload size:** at most 15 MiB (`settings.MAX_UPLOAD_BYTES`). A PDF is read for at most 40 pages
  (`settings.MAX_PDF_PAGES`).
- **A separate child process:** PDF extraction runs in its own process (`studio/ingest/extract.py` `_run_child`,
  `python -m studio.ingest._child`). Its limits are:
  - address space 1.5 GiB (`RLIMIT_AS`, `AS_LIMIT_BYTES`);
  - CPU of the time limit plus 1 s, then SIGKILL 5 s later (`RLIMIT_CPU`, `CPU_GRACE_S`);
  - bounded file size and task count (`RLIMIT_FSIZE`, `RLIMIT_NPROC`);
  - a wall-clock deadline of 240 s (`settings.EXTRACTION_TIMEOUT_SECONDS`) that kills the whole process group.
- **An overrun** fails that document's extraction with a stated message. The worker, the web process and other
  documents' records are not touched.
- **Measured:** `tests/test_ingest.py` SandboxTests, 12 tests OK on 2026-11-05. They include
  `test_memory_limit_is_enforced`, `test_timeout_kills_the_whole_process_group` and `test_crashes_and_exit_statuses`.

## What remains (the residual, stated plainly)

- **Each crafted PDF can cost up to one extraction child's limits:** 1.5 GiB and about 240 s. The service has one
  worker, so a member who uploads crafted files one after another can delay the workspace's other documents for as
  long as they keep doing so. That is an availability limitation and a reason not to accept untrusted uploads.
- **These limits contain the generic failure,** whether it is a loop, a memory growth or a long runtime. They are not a
  per-advisory proof: no crafted reproduction of any of the seven was run against CPT Studio.
- **CPT Studio stays a private synthetic workspace.** Uploads come from authenticated workspace members, and
  synthetic-only attestation is required per revision. **Readiness for wider or untrusted uploads is not claimed**
  while these advisories remain.
