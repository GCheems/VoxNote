#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

required_uv="uv 0.7.14"
actual_uv="$(uv --version)"
if [[ "$actual_uv" != "$required_uv"* ]]; then
  echo "Lock generation requires $required_uv; found: $actual_uv" >&2
  exit 1
fi

uv pip compile --no-cache requirements-macos-arm64-py311.in \
  --python-platform aarch64-apple-darwin \
  --python-version 3.11 \
  --resolution highest \
  --upgrade \
  --generate-hashes \
  --emit-index-url \
  --no-annotate \
  --output-file requirements-macos-arm64-py311.lock.txt

uv pip sync --dry-run --no-cache --no-build --require-hashes \
  --python-platform aarch64-apple-darwin \
  --python-version 3.11 \
  requirements-macos-arm64-py311.lock.txt
