# form-detect — the ONE-PIPELINE form-vision sidecar (#326).
# Detects fillable-field boxes with CommonForms/FFDNet (self-hosted, CPU) and
# verifies layout fidelity for the stage-5 certify gate.
#
# The FFDNet-L weights are PINNED by HuggingFace revision AND asserted by sha256
# at build time; the sha is the model's identity in the certification signature
# (ruling #326). A weights change ⇒ a new sha ⇒ forced re-certification.
FROM python:3.12-slim

# ── pins (the load-bearing ones) ────────────────────────────────────────────
ENV FFDNET_MODEL=FFDNet-L \
    FFDNET_HF_REPO=jbarrow/FFDNet-L \
    FFDNET_HF_REVISION=82547d6c89fd35120ff944cdce866ac2202e2152 \
    FFDNET_WEIGHTS=/app/weights/FFDNet-L.pt \
    FFDNET_WEIGHTS_SHA=2a69102275c8950b04c7f7281f01e1f8ee7aa88179ac450b8df25819c07b8275 \
    COMMONFORMS_VERSION=0.2.1 \
    HF_HOME=/app/hf-cache \
    PORT=8000 \
    PYTHONUNBUFFERED=1

# libGL/glib for opencv (ultralytics dep); curl for the healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch/torchvision FIRST, PINNED, so commonforms' resolve is already
# satisfied and never pulls the CUDA build — and detection numerics are frozen.
RUN pip install --no-cache-dir torch==2.14.0 torchvision==0.29.0 \
      --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the pinned weights and ASSERT the sha256 — the build fails closed if the
# model is not byte-identical to the one that will be recorded in certifications.
RUN python -c "import os; from huggingface_hub import hf_hub_download; \
  p=hf_hub_download(repo_id=os.environ['FFDNET_HF_REPO'], filename='FFDNet-L.pt', revision=os.environ['FFDNET_HF_REVISION']); \
  os.makedirs('/app/weights', exist_ok=True); \
  import shutil; shutil.copy(p, os.environ['FFDNET_WEIGHTS'])" \
 && python -c "import hashlib, os; \
  h=hashlib.sha256(open(os.environ['FFDNET_WEIGHTS'],'rb').read()).hexdigest(); \
  exp=os.environ['FFDNET_WEIGHTS_SHA']; \
  print('weights sha256', h); \
  assert h==exp, f'WEIGHTS SHA MISMATCH: got {h} expected {exp}'"

COPY app.py .

# Warm the model at build so first-request latency is not a cold YOLO load.
RUN python -c "from commonforms.inference import FFDNetDetector; \
  import os; FFDNetDetector(os.environ['FFDNET_WEIGHTS'], device='cpu'); print('model loads OK')"

HEALTHCHECK --interval=30s --timeout=8s --start-period=40s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["python", "app.py"]
