#!/usr/bin/env bash

set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to run this smoke test." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to run this smoke test." >&2
  exit 1
fi

echo "Running README example 1..."
uv run python -m vin_mcp.server --decode 1HGCM82633A004352 \
  | jq -e '.vin == "1HGCM82633A004352" and .summary.Make == "HONDA" and .summary.Model == "Accord"' >/dev/null

echo "Running README example 2..."
uv run python -m vin_mcp.server --decode 1HGCM82633A004352 --summary-only \
  | jq -e '.Make == "HONDA" and .Model == "Accord" and .ModelYear == "2003"' >/dev/null

echo "Running README example 3..."
uv run python -m vin_mcp.server \
  --canadian-specs-year 2011 \
  --canadian-specs-make Acura \
  | jq -e '.count >= 1 and .summary.make == "ACURA" and (.results | length >= 1)' >/dev/null

echo "Running README example 4..."
uv run python -m vin_mcp.server \
  --canadian-specs-year 2011 \
  --canadian-specs-make Acura \
  --summary-only \
  | jq -e '.year == 2011 and .make == "ACURA" and (.Model | type == "string")' >/dev/null

echo "Smoke tests passed."
