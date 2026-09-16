"""form-detect — the form-vision sidecar for the ONE-PIPELINE (#326).

Detects fillable-field boxes on rendered PDF pages with CommonForms/FFDNet
(self-hosted, CPU) and labels each from the nearest text. Also verifies layout
fidelity (pixels changed outside the boxes) for the stage-5 certify gate.

The FFDNet weights are PINNED and baked into the image; their sha256 is returned
by /health and /detect so it can enter the certification signature — a weights
change is a new sha, which forces re-certification (ruling #326).

Endpoints (all JSON unless noted):
  GET  /health   -> {ok, model, weights_sha, commonforms_version, image_size, confidence}
  POST /detect   (body: PDF bytes) -> {model, weights_sha, pages:[{index,width_pt,
                 height_pt, boxes:[{x,y,w,h,type,label}]}]}   # x,y,w,h in PDF
                 points, bottom-left origin (pdf-lib space)
  POST /verify   (JSON: {original:<b64 pdf>, filled:<b64 pdf>, boxes:[{boxes:[...]}],
                 dpi:int}) -> per-page {outside_box_changed_px, outside_box_total_px,
                 inside_box_changed_px, box_area_pct}
"""
from __future__ import annotations

import io
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pypdfium2 as pdfium

try:
    from commonforms import __version__ as CF_VERSION
except Exception:
    CF_VERSION = os.environ.get("COMMONFORMS_VERSION", "unknown")
from commonforms.inference import FFDNetDetector, render_pdf
from commonforms.utils import Page

MODEL = os.environ.get("FFDNET_MODEL", "FFDNet-L")
WEIGHTS_PATH = os.environ["FFDNET_WEIGHTS"]          # baked, pinned
WEIGHTS_SHA = os.environ["FFDNET_WEIGHTS_SHA"]        # pinned sha256 (asserted at build)
CONFIDENCE = float(os.environ.get("FFDNET_CONFIDENCE", "0.3"))
IMAGE_SIZE = int(os.environ.get("FFDNET_IMAGE_SIZE", "1600"))
PORT = int(os.environ.get("PORT", "8000"))

def _verify_weights_or_die() -> None:
    """Assert the weights ACTUALLY on disk hash to the pinned sha — the reported
    signature must identify the model that answers, not merely echo an env var
    (adversarial pass finding #5). Fail closed."""
    import hashlib

    got = hashlib.sha256(open(WEIGHTS_PATH, "rb").read()).hexdigest()
    if got != WEIGHTS_SHA:
        raise SystemExit(
            f"FATAL: weights at {WEIGHTS_PATH} hash {got} != pinned {WEIGHTS_SHA}"
        )


_verify_weights_or_die()

# The certification signature — everything that moves the detected boxes. A
# change to ANY of these must force re-certification (#326). Pinned deps freeze
# the rest (see requirements.txt / Dockerfile).
DETECTOR_SIGNATURE = {
    "model": MODEL,
    "weights_sha": WEIGHTS_SHA,
    "confidence": CONFIDENCE,
    "image_size": IMAGE_SIZE,
    "commonforms_version": CF_VERSION,
}

# Load the detector ONCE at startup (the weights path is the pinned local file).
_DETECTOR = FFDNetDetector(WEIGHTS_PATH, device="cpu")


def _detect(pdf_bytes: bytes) -> dict:
    # write to a temp file: render_pdf/formalpdf takes a path
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tf:
        tf.write(pdf_bytes)
        tf.flush()
        pages: list[Page] = render_pdf(tf.name)
        widgets_by_page = _DETECTOR.extract_widgets(
            pages, confidence=CONFIDENCE, image_size=IMAGE_SIZE
        )

    pdf = pdfium.PdfDocument(pdf_bytes)
    out_pages = []
    for i in range(len(pdf)):
        page = pdf[i]
        w_pt, h_pt = page.get_size()
        # page text with positions for nearest-text labelling
        text_items = _page_text_items(page, w_pt, h_pt)
        boxes = []
        for wdg in widgets_by_page.get(i, []):
            bb = wdg.bounding_box  # normalized [0,1], y from TOP (image origin)
            x = bb.x0 * w_pt
            y = (1.0 - bb.y1) * h_pt  # bottom-left origin
            bw = (bb.x1 - bb.x0) * w_pt
            bh = (bb.y1 - bb.y0) * h_pt
            label, source = _nearest_label({"x": x, "y": y, "w": bw, "h": bh}, text_items)
            boxes.append(
                {
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "w": round(bw, 2),
                    "h": round(bh, 2),
                    "type": wdg.widget_type,
                    "label": label,
                    "label_source": source,
                }
            )
        out_pages.append(
            {
                "index": i,
                "width_pt": round(w_pt, 2),
                "height_pt": round(h_pt, 2),
                "boxes": boxes,
            }
        )
    return {
        "model": MODEL,
        "weights_sha": WEIGHTS_SHA,
        "detector": DETECTOR_SIGNATURE,
        "pages": out_pages,
    }


def _page_text_items(page, w_pt, h_pt) -> list[dict]:
    """Text runs with PDF-point bounding boxes (bottom-left origin)."""
    tp = page.get_textpage()
    items = []
    n = tp.count_rects()
    for r in range(n):
        # get_rect gives (left, bottom, right, top) in PDF points, bottom-left origin
        left, bottom, right, top = tp.get_rect(r)
        text = tp.get_text_bounded(left=left, bottom=bottom, right=right, top=top)
        t = (text or "").strip()
        if t:
            items.append({"x0": left, "y0": bottom, "x1": right, "y1": top, "text": t})
    return items


LABEL_ROW_BAND = 9.0  # a text row, FIXED — not scaled by box height (adv #2)
LABEL_LEFT_REACH = 120.0  # max horizontal gap for a left label (adv #1)
LABEL_ABOVE_REACH = 44.0  # max vertical gap for a heading above


def _nearest_label(box: dict, items: list[dict]) -> tuple[str, str]:
    """Label a box and say WHERE the label came from: a run to the LEFT on the
    box's text-baseline row (a field:value pair) → ('..','left'); else a heading
    directly ABOVE (a section body) → ('..','above'); else ('',''). The source
    lets grouping tell a section from a field regardless of a trailing colon.

    A LEFT label is matched to the box's BASELINE row (near the bottom for a tall
    box), so a tall widget keeps its own baseline-aligned label but does not grab
    a middle-aligned label from an adjacent field (adv pass2 #3 / pass1 #2). A far
    same-row fragment is excluded by the 120pt reach (adv pass1 #1).
    """
    bx, by, bw, bh = box["x"], box["y"], box["w"], box["h"]
    b_top = by + bh
    label_row = by + min(bh / 2.0, 8.0)  # the text baseline area of the box
    left_limit = bx + bw * 0.33  # a real left label ends within the box's left third

    def cy(it):
        return (it["y0"] + it["y1"]) / 2.0

    left = [
        it
        for it in items
        if it["text"]
        and it["x0"] < left_limit
        and it["x1"] <= left_limit
        and abs(cy(it) - label_row) <= LABEL_ROW_BAND
        and (bx - it["x1"]) <= LABEL_LEFT_REACH
    ]
    if left:
        return (max(left, key=lambda it: it["x1"])["text"], "left")

    above = [
        it
        for it in items
        if it["text"]
        and it["y0"] >= b_top - 2
        and it["x0"] <= bx + bw
        and it["x1"] >= bx
        and (it["y0"] - b_top) <= LABEL_ABOVE_REACH
    ]
    if above:
        return (min(above, key=lambda it: it["y0"] - b_top)["text"], "above")
    return ("", "")


def _verify(original: bytes, filled: bytes, boxes_by_page: list, dpi: int) -> dict:
    s = dpi / 72.0
    pad = max(2, int(0.03 * dpi))
    thresh = 24

    def render(b):
        pdf = pdfium.PdfDocument(b)
        try:
            pdf.init_forms()
        except Exception:
            pass
        out = []
        sizes = []
        for i in range(len(pdf)):
            pg = pdf[i]
            bmp = pg.render(scale=s, may_draw_forms=True)
            out.append(np.asarray(bmp.to_pil().convert("RGB"), dtype=np.int16))
            sizes.append(pg.get_size())
        return out, sizes

    o_imgs, sizes = render(original)
    f_imgs, _ = render(filled)
    per_page = []
    for i, (o, f) in enumerate(zip(o_imgs, f_imgs)):
        if f.shape != o.shape:
            f = f[: o.shape[0], : o.shape[1]]
        H, W = o.shape[:2]
        _, h_pt = sizes[i]
        mask = np.zeros((H, W), dtype=bool)
        for bx in (boxes_by_page[i]["boxes"] if i < len(boxes_by_page) else []):
            x0 = max(0, int(bx["x"] * s) - pad)
            y0 = max(0, int((h_pt - (bx["y"] + bx["h"])) * s) - pad)
            x1 = min(W, int((bx["x"] + bx["w"]) * s) + pad)
            y1 = min(H, int((h_pt - bx["y"]) * s) + pad)
            mask[y0:y1, x0:x1] = True
        diff = np.abs(o - f).max(axis=2) > thresh
        outside = int((diff & ~mask).sum())
        inside = int((diff & mask).sum())
        per_page.append(
            {
                "page": i,
                "outside_box_changed_px": outside,
                "outside_box_total_px": int((~mask).sum()),
                "inside_box_changed_px": inside,
                "box_area_pct": round(100 * int(mask.sum()) / (W * H), 2),
            }
        )
    return {"pages": per_page, "dpi": dpi, "threshold": thresh}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True, "detector": DETECTOR_SIGNATURE})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        try:
            if self.path == "/detect":
                self._send(200, _detect(raw))
            elif self.path == "/verify":
                import base64

                req = json.loads(raw.decode())
                original = base64.b64decode(req["original"])
                filled = base64.b64decode(req["filled"])
                self._send(
                    200, _verify(original, filled, req["boxes"], int(req.get("dpi", 150)))
                )
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # fail LOUD — the caller decides
            self._send(500, {"error": type(e).__name__, "detail": str(e)})

    def log_message(self, *a):  # quiet default access log
        pass


if __name__ == "__main__":
    print(f"form-detect: model={MODEL} sha={WEIGHTS_SHA[:12]} port={PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
