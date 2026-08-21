#!/usr/bin/env bash
# Assemble the static documentation site in docs/.
#
# The site is served from docs/ alone, so the specification has to sit next to index.html: a relative
# fetch is the only way to load it without a CDN. docs/openapi.yaml is therefore a build artefact and
# is not committed — openapi.yaml at the repository root is the source of truth.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/gen-catalogue.py
cp openapi.yaml docs/openapi.yaml

echo "site ready: docs/ (serve it, e.g. python3 -m http.server --directory docs 8000)"
