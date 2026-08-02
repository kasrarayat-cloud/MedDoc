# ============================================================================
# Gotenberg + the fonts the PDF export embeds.
# ----------------------------------------------------------------------------
# ⚠️ THE PREVIEW IS RENDERED HERE, AND IT COULD NOT RENDER THE DOCUMENT'S TYPE.
#
# `preview-visit-document.ts` generates the DOCX and posts it to this container;
# LibreOffice converts it and the returned PDF is what the doctor sees as the
# on-screen paper. The Word file NAMES Charter and Inter Tight — the same faces
# `pdf-generator.ts` EMBEDS — but naming is not resolving. Measured on the
# running container before this image existed:
#
#     docker exec meddoc-pro-gotenberg-1 fc-list | grep -ci 'charter|inter tight'
#     → 0
#
# The stock image ships Caladea, Carlito, DejaVu, Liberation and Noto. So
# LibreOffice substituted, and the preview showed a different typeface from the
# download at every size. "Exports match preview 1:1" (SPEC.md:200) was
# unreachable from the generators alone, however carefully they were aligned.
#
# The TTFs here are the exact files the PDF embeds — one directory, so the two
# renderers cannot drift onto different cuts of the same family.
#
# Build context is `apps/transcribe-md/fonts` deliberately: this needs nine
# files, and a repo-root context would ship the whole tree to the daemon.
# ============================================================================
FROM gotenberg/gotenberg:8

USER root
COPY *.ttf /usr/share/fonts/truetype/quillmd/
COPY LICENSES-*.txt /usr/share/fonts/truetype/quillmd/
# fontconfig caches its index; a font dropped in without this is present on disk
# and invisible to LibreOffice, which is the same "installed but not resolving"
# failure one level down.
RUN fc-cache -f && fc-list | grep -qi charter && fc-list | grep -qi 'inter tight'
USER gotenberg
