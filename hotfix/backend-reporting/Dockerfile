ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# If the base image runs Python jobs, ensure sitecustomize is importable on startup.
ENV PYTHONPATH=/app

COPY sitecustomize.py /app/sitecustomize.py

# Optional: patch the Node dist bundle (if this base image includes it).
COPY patch-config-validator.js /app/patch-config-validator.js

# If the base image runs the Node "amazon-ppc-backend" CLI, patch the compiled
# config validator to lazily validate config when first accessed.
#
# Symptom in logs:
#   "Config not validated yet. Call validateConfig() first."
#
# This is a best-effort patch: if the dist bundle isn't present, it no-ops.
RUN set -eu; \
    if [ -d /app/dist ] && command -v node >/dev/null 2>&1; then \
      node /app/patch-config-validator.js || true; \
    fi
