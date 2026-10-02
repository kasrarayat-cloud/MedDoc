# Can the app's rendered layout path run in an isolated QA process? — 2026-09-29

Read-only investigation plus two proof runs on candidate `8e3dcfd0`, as the unprivileged `claude` account, with
internet sockets denied by a seccomp filter (positive control: `AF_INET` gave `EPERM` in-process and in children;
`AF_UNIX` allowed). No provider call, no sudo or systemd, the installed services untouched. Written by the lead from
the investigating agent's returned findings (the agent could not write report files).

## Verdict

- **Every component of the v3 layout path runs as `claude`** on the candidate: `documents.service` with
  `QUILLMD_WORD_ENGINE=v3`; `layout_transport.verify_document` over a real Unix socket (`/tmp/qlw-*/l.sock` — a
  scratchpad-length path fails with `AF_UNIX path too long`) with its owner and `SO_PEERCRED` checks; the unmodified
  `layout_server.serve`/`qualify`; `worker.py` layout_prepare and `layout_pdf_worker.py` under Landlock and seccomp;
  the receipt checks.
- **The renderer is a `docker run`** of a pinned local image (`layout_server.py` `render()`, line 41):
  `docker run --pull never --network none --read-only --user <uid> --cap-drop ALL --pids-limit 128 --memory 1g
  --cpus 1 … sha256:4bd4489d15b7326143e5575c789d93f675f77d85dc857900dd28ae1591d55a4b` (stock gotenberg 8.34.0,
  LibreOffice 26.2.4.2), then `docker rm -f`. There is no `soffice`/LibreOffice anywhere on the host filesystem. The
  investigation was barred from Docker, so the image's presence in the local cache was not checked.
- **No deployed configuration has the witness.** `QUILLMD_LAYOUT_SOCKET` and `QUILLMD_LAYOUT_SERVICE_UID` are absent
  from `ops/deployment_profile.py`; the production renderer refuses unknown names; no layout unit, process or socket
  exists. A run **without** the witness reproduces deployed behaviour; a run **with** it measures a configuration no
  deployed service has. No test or CI step runs the real renderer.

## Proof runs (synthetic python-docx tab-column form)

| mode | inspect | fill / effective_values |
|---|---|---|
| renderer refused (docker call intercepted, never executed) | 0 fields, 1 pending, "Layout verification required…" | `DocumentError layout_unresolved` |
| hash-gated replay of the pinned image's retained real PDFs (byte-identical inputs only) | 1 field `Finding`, layout_verified, receipt `word-tab-containment-v2` | export `5a27851c…`, byte-identical to the retained real-render export; effective_values `[false, true]` |

The replay proves the non-container components only; it cannot serve a campaign, because new answers produce export
bytes with no cached render.

## Timing (from retained real renders, same image and verifier)

Container 8.2–8.7 s per synthetic form, 12.7–12.9 s for D10; whole request about 9.5–10 s synthetic and 18–19 s for
D10. The server is sequential, and every inspect, fill or effective_values call on a layout form is one request.

## Census on the 40 development originals (candidate engine, no witness)

Only D10 reaches the witness. Without it D10 publishes 77 fields with 112 coded-column candidates pending, and any
fill is refused with `layout_unavailable` — even one answer in an unrelated text field. With the replayed witness:
181 fields (104 verified, 8 held), above the default limit of 100 answerable fields unless batch generation is on.
D01 needs the Word SDK runtime: it runs in qualification mode from the retained runtime `word-narrative-build-10`
(its 17 build inputs match the candidate's sources; 90 fields, 14 review requirements, 1.3–1.4 s); the
non-qualification install needs sudo. The other 38 have no pending layout.

## Consequence for the campaign

The mapping stage's **primary condition is deployed-equivalent: no witness.** A run with the witness is a separately
labelled QA condition, used only where it adds diagnostic value, and needs the pinned image present locally (checked
with `docker image inspect`, never pulled).
