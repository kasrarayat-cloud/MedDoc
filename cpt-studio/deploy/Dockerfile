# CPT Studio application image. One image, two long-running roles (web, worker)
# and one-shot management commands; deploy/entrypoint.sh refuses anything else.
#
# Build context: the cpt-studio/ directory, with deploy/.dockerignore staged at
# the context root as .dockerignore (docker reads the ignore file only there).
# ops/install.py builds from `git archive` of the declared revision:
#
#   docker build -f deploy/Dockerfile --build-arg REVISION=<40-char sha> -t cpt-studio:<sha12> .
#
# Base pinned by digest: python:3.12-slim-bookworm (Python 3.12.15, linux/amd64),
# resolved 2026-10-23. Move it deliberately: pull, record the new digest here,
# rebuild, and rerun the suite inside the image.
FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70

# OCR only: tesseract with English data, and poppler for pdftoppm.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# uid/gid 10150, not the common 10001: on this host 10001 already runs a
# co-tenant's containers, and RLIMIT_NPROC (which the extraction sandbox sets
# from this container's own task count) is accounted per host uid. ops/install.py
# pins the same value and refuses when another workload uses it.
# The state directory is created here so a new named volume mounted on it
# inherits 10150:10150 0700. Nothing else in the image is writable by the app.
RUN groupadd --system --gid 10150 cptstudio \
    && useradd --system --uid 10150 --gid 10150 --no-create-home --home-dir /nonexistent \
        --shell /usr/sbin/nologin cptstudio \
    && install -d -o 10150 -g 10150 -m 0700 /var/lib/cpt-studio

# Read-only root filesystem at runtime: no bytecode writes, caches under /tmp
# (a tmpfs), uploads and originals under the state volume.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    XDG_CACHE_HOME=/tmp/.cache \
    CPT_STUDIO_STATE_DIR=/var/lib/cpt-studio

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# collectstatic imports settings, which require a secret. This value exists for
# this one step only; it is not in the image environment and signs nothing.
# It also writes with the upload modes (0700/0600), and COPY keeps the build
# context's own modes (an archive extracted under umask 077 has 0700
# directories). Either would leave code or assets unreadable by the application
# user: make all of /app root-owned 0755/0644.
RUN CPT_STUDIO_SECRET_KEY=collectstatic-build-step-only python manage.py collectstatic --noinput \
    && chmod -R u=rwX,go=rX /app

# Declared last so a new revision reuses every layer above.
ARG REVISION=development-unrecorded
ENV CPT_STUDIO_RELEASE_SHA=${REVISION}
LABEL org.opencontainers.image.title="CPT Studio" \
      org.opencontainers.image.revision=${REVISION}

USER 10150:10150
EXPOSE 8000
# Web role only. The worker serves no HTTP and is started with --no-healthcheck.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=4)"]
ENTRYPOINT ["/bin/sh", "/app/deploy/entrypoint.sh"]
CMD ["web"]
