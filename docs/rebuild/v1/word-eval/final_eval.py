"""Frozen per-document evaluation of a Word candidate on one corpus set (dev | holdout | qual).

A document is an AUTOMATIC SUCCESS only if all hold (word-compatibility-target.md, "Scoring"):
  1. detection  strict score: every ground-truth area CORRECT (right destination, kind class, option count),
                duplicates disambiguated, no unmatched detected field           [tolerant variant reported apart]
  2. fills      three answer profiles fill without refusal: EMPTY (no answers), ORDINARY, LONG (~400-char text)
  3. export     for ORDINARY and LONG: package re-opens; every package part the fill did not change is
                byte-identical; structure counts unchanged; untouched paragraphs identical; printed text around
                answers kept in order; every text answer visible in a LibreOffice render (unique token per
                answer); no increase in overprinted characters versus the original render.
  EMPTY must return a package whose entries are all byte-identical to the original.
Nothing is netted: every document stays in the denominator; reasons are recorded per document.
"""
import hashlib, importlib.util, io, json, pathlib, re, subprocess, sys, time, traceback, zipfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
spec = importlib.util.spec_from_file_location("word_v3", "/opt/meddoc-pro/.worktrees/v1-word/rebuild/documents/word_v3.py")
w = importlib.util.module_from_spec(spec); sys.modules["word_v3"] = w; spec.loader.exec_module(w)
import score as scoring                      # eval/score.py
import fill_eval                             # eval/fill_eval.py (structure/text checks)

C = pathlib.Path("/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus")
MANIFEST = pathlib.Path("/opt/meddoc-pro/.worktrees/v1-release/docs/rebuild/v1/word-corpus-manifest.json")
TOOLS_PY = "/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/tools-venv/bin/python"  # pypdfium2 (render text layer)


def answers_for(fields, profile):
    out = {}
    if profile == "empty":
        return out
    for i, f in enumerate(fields):
        k, opts, n = f["kind"], f.get("options") or [], i + 1
        if k in ("signature", "initials"):
            continue
        if k == "checkbox":
            out[f["key"]] = True
        elif k == "choice":
            if opts:
                out[f["key"]] = opts[min(1, len(opts) - 1)]
        elif k == "multi_choice":
            if opts:
                out[f["key"]] = opts[:2]
        elif k == "date":
            out[f["key"]] = "03/14/2026"
        elif k == "time":
            out[f["key"]] = "14:30"
        elif k == "table_rows":
            cols = len(f["locator"]["target"]["columns"])
            out[f["key"]] = [["T%dr%dc%d" % (n, r, c) for c in range(cols)] for r in range(2)]
        elif profile == "long" and k in ("text", "long_text"):
            out[f["key"]] = "Q%dv " % n + ("synthetic long answer text " * 15).strip()
        elif k == "long_text":
            out[f["key"]] = "Q%dv first line.\nSecond line." % n
        else:
            out[f["key"]] = "Q%dv" % n
    for f in fields:                            # the longest answer the area allows, never more
        cap = f.get("max_chars")
        if cap and isinstance(out.get(f["key"]), str) and len(out[f["key"]]) > cap:
            v = out[f["key"]]
            out[f["key"]] = v[:cap]
    return out


def package_identity(src, out, changed_ok):
    a, b = zipfile.ZipFile(io.BytesIO(src)), zipfile.ZipFile(io.BytesIO(out))
    na, nb = [i.filename for i in a.infolist()], [i.filename for i in b.infolist()]
    if na != nb:
        return ["package entries differ"]
    probs = []
    for name in na:
        if name in changed_ok:
            continue
        if a.read(name) != b.read(name):
            probs.append("unchanged part differs: %s" % name)
    return probs


def export_checks(src, fields, answers):
    """fill + mechanical checks; returns (problems, output_bytes)."""
    out = w.fill(src, fields, answers)
    touched = {f["locator"]["part"] for f in fields if f["key"] in answers}
    for f in fields:
        if f["key"] in answers:
            touched |= {c["part"] for c in f["locator"]["target"].get("copies", [])}
            touched |= {b["part"] for b in f["locator"]["target"].get("boxes", [])}
    probs = package_identity(src, out, touched)
    det = {"fields": fields}
    # reuse the fill_eval structural/text checks with these exact answers
    fill_eval_answers = answers
    res = check_with(src, out, fields, fill_eval_answers)
    probs += res
    return probs, out


def check_with(src, out, fields, answers):
    res = {"problems": []}
    pkg0, pkg1 = w.open_package(src), w.open_package(out)
    idx_pre = w.SlotIndex(pkg0)
    has_rows = any(f["locator"]["target"]["type"] == "table_rows" for f in fields if f["key"] in answers)
    drop = {}
    for f in fields:
        t = f["locator"]["target"]
        if f["key"] in answers and t.get("all"):
            cell = idx_pre.by_id["%s#%s" % (f["locator"]["part"], f["locator"]["slot"])]
            drop[f["locator"]["part"]] = drop.get(f["locator"]["part"], 0) + max(0, len(cell.el.findall(w.q("w:p"))) - 1)
    for part in pkg0.content_parts():
        c0, c1 = fill_eval.counts(pkg0.tree(part)), fill_eval.counts(pkg1.tree(part))
        c0["p"] -= drop.get(part, 0)
        for k in c0:
            if c0[k] != c1[k] and not (has_rows and k in ("tr", "tc", "p")):
                res["problems"].append("structure %s %s: %d -> %d" % (part, k, c0[k], c1[k]))
    t0, idx0 = fill_eval.para_texts(pkg0)
    t1, _ = fill_eval.para_texts(pkg1)
    allowed = {}
    for f in fields:
        if f["key"] in answers:
            for pid, pos in fill_eval.allowed_removals(f, idx0).items():
                if allowed.get(pid) == "all" or pos == "all":
                    allowed[pid] = "all"
                else:
                    allowed.setdefault(pid, set()).update(pos)
    for sid, text in t0.items():
        if sid not in t1:
            if allowed.get(sid) != "all":
                res["problems"].append("paragraph lost %s" % sid)
            continue
        new = t1[sid]
        if sid not in allowed:
            if new != text:
                res["problems"].append("untargeted paragraph changed %s" % sid)
        elif allowed[sid] != "all":
            kept = "".join(ch for i, ch in enumerate(text) if i not in allowed[sid])
            if not fill_eval.is_subsequence(kept, new):
                res["problems"].append("printed text lost in %s" % sid)
    return res["problems"]


def render(pdf_dir, docx_paths):
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.chmod(0o777)
    src_dir = docx_paths[0].parent
    src_dir.chmod(0o777)
    for p in docx_paths:
        p.chmod(0o644)
    cmd = ["docker", "run", "--rm", "--network", "none", "--user", "1001", "-v", "%s:/in:ro" % src_dir, "-v", "%s:/out" % pdf_dir,
           "--entrypoint", "soffice", "gotenberg/gotenberg:8", "--headless", "--norestore", "--convert-to", "pdf", "--outdir", "/out"]
    cmd += ["/in/" + p.name for p in docx_paths]
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3600)


def render_checks(orig_pdf, filled_pdf, fields, answers):
    code = r'''
import json, re, sys
sys.path.insert(0, sys.argv[4])
import render_eval as r
p0, p1 = r.page_chars(sys.argv[1]), r.page_chars(sys.argv[2])
text1 = re.sub(r"[\s\-\u00ad]+", "", "".join(t for t, _ in p1)).lower()
probes = json.loads(sys.argv[3])
missing = [k for k, v in probes.items() if v.lower() not in text1]
print(json.dumps({"pages": [len(p0), len(p1)], "overlap": [r.overlaps(p0), r.overlaps(p1)], "missing": missing}))
'''
    probes = {}
    for f in fields:
        a = answers.get(f["key"])
        if isinstance(a, str) and f["kind"] in ("text", "long_text", "measurement", "number"):
            probes[f["key"]] = re.sub(r"[\s\-]+", "", a.split("\n")[0])[:14]
        elif isinstance(a, list) and a and isinstance(a[0], list):
            probes[f["key"]] = a[0][0]
    if not filled_pdf.exists():
        return ["render failed"], {}
    outp = subprocess.run([TOOLS_PY, "-c", code, str(orig_pdf), str(filled_pdf), json.dumps(probes), str(pathlib.Path(__file__).parent)],
                          capture_output=True, text=True, timeout=900)
    if outp.returncode != 0:
        return ["render check crashed: %s" % outp.stderr[-300:]], {}
    info = json.loads(outp.stdout)
    probs = []
    if info["overlap"][1] > info["overlap"][0]:
        probs.append("overprinting +%d chars" % (info["overlap"][1] - info["overlap"][0]))
    if info["missing"]:
        probs.append("%d answers not visible in render" % len(info["missing"]))
    return probs, info


def main(set_name, out_root):
    out_root = pathlib.Path(out_root)
    (out_root / "detect").mkdir(parents=True, exist_ok=True)
    manifest = json.load(open(MANIFEST))
    families = {pathlib.Path(e["corpus_file"]).stem: e["families_declared"] for e in manifest["sets"][set_name]}
    docs = []
    stage = {"ordinary": [], "long": []}
    for orig in sorted((C / set_name / "originals").iterdir()):
        stem = orig.stem
        src_path = C / set_name / "converted" / (stem + ".docx") if orig.suffix == ".doc" else orig
        src = src_path.read_bytes()
        rec = {"stem": stem, "format": orig.suffix.lstrip("."), "families": families.get(stem, []), "reasons": []}
        t = time.time()
        try:
            det = w.inspect(src)
        except w.V3Failure as e:
            det = {"refused": str(e), "code": e.code}
        except Exception as e:
            det = {"crash": repr(e)}
        rec["inspect_seconds"] = round(time.time() - t, 3)
        (out_root / "detect" / (stem + ".json")).write_text(json.dumps(det, indent=1, ensure_ascii=False))
        gt = json.loads((C / set_name / "groundtruth" / (stem + ".json")).read_text())
        if "fields" not in det:
            rec["reasons"].append("not inspected: %s" % (det.get("refused") or det.get("crash")))
            rec.update(strict=False, tolerant=False, n=len(gt.get("answer_areas", [])))
            docs.append(rec)
            continue
        sc = scoring.score_doc(gt, det)
        rec.update({k: sc[k] for k in ("n", "ok", "missed", "wrong", "extras", "dup_bad", "strict", "tolerant")})
        if not sc["strict"]:
            rec["reasons"].append("detection: %d missed, %d wrong, %d extra, %d duplicate" % (sc["missed"], sc["wrong"], sc["extras"], sc["dup_bad"]))
        fields = det["fields"]
        for profile in ("empty", "ordinary", "long"):
            answers = answers_for(fields, profile)
            try:
                probs, out = export_checks(src, fields, answers)
                if profile == "empty":
                    probs = package_identity(src, out, set())
                else:
                    d = out_root / ("filled-" + profile)
                    d.mkdir(parents=True, exist_ok=True)
                    (d / (stem + ".docx")).write_bytes(out)
                    (d / (stem + ".answers.json")).write_text(json.dumps(answers))
                    stage[profile].append(d / (stem + ".docx"))
            except w.V3Failure as e:
                probs = ["fill refused (%s): %s" % (e.code, e)]
            except Exception as e:
                probs = ["fill crashed: %r" % e]
            if probs:
                rec["reasons"].append("%s fill: %s" % (profile, "; ".join(probs[:3])))
        docs.append(rec)
        print(stem[:3], "detect", "strict" if rec.get("strict") else ("tolerant" if rec.get("tolerant") else "fail"),
              "|", "; ".join(rec["reasons"])[:160], flush=True)
    # renders
    for profile in ("ordinary", "long"):
        if stage[profile]:
            render(out_root / ("render-" + profile), stage[profile])
    for rec in docs:
        for profile in ("ordinary", "long"):
            docx = out_root / ("filled-" + profile) / (rec["stem"] + ".docx")
            if not docx.exists():
                continue
            det = json.loads((out_root / "detect" / (rec["stem"] + ".json")).read_text())
            answers = json.loads((out_root / ("filled-" + profile) / (rec["stem"] + ".answers.json")).read_text())
            probs, info = render_checks(C / set_name / "renders" / rec["stem"] / "original.pdf",
                                        out_root / ("render-" + profile) / (rec["stem"] + ".pdf"), det["fields"], answers)
            rec.setdefault("render", {})[profile] = info
            if probs:
                rec["reasons"].append("%s render: %s" % (profile, "; ".join(probs)))
    for rec in docs:
        export_ok = not any(r.split(" ")[0] in ("empty", "ordinary", "long") for r in rec["reasons"])
        rec["export_ok"] = export_ok
        rec["automatic_success"] = bool(rec.get("strict")) and export_ok
        rec["automatic_success_tolerant"] = bool(rec.get("tolerant")) and export_ok
    fam = {}
    for f in ["F%d" % i for i in range(1, 11)]:
        cases = [r for r in docs if f in r["families"]]
        fam[f] = {"cases": len(cases), "success": sum(r["automatic_success"] for r in cases),
                  "success_tolerant": sum(r["automatic_success_tolerant"] for r in cases)}
    summary = {"set": set_name, "documents": len(docs),
               "automatic_success": sum(r["automatic_success"] for r in docs),
               "automatic_success_tolerant": sum(r["automatic_success_tolerant"] for r in docs),
               "detection_strict": sum(bool(r.get("strict")) for r in docs),
               "export_ok": sum(r["export_ok"] for r in docs),
               "areas": sum(r.get("n", 0) for r in docs), "areas_correct": sum(r.get("ok", 0) for r in docs),
               "areas_missed": sum(r.get("missed", 0) for r in docs), "areas_wrong": sum(r.get("wrong", 0) for r in docs),
               "extra_fields": sum(r.get("extras", 0) for r in docs), "families": fam}
    (out_root / "results.json").write_text(json.dumps({"summary": summary, "documents": docs}, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
