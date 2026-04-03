# vin-lookup-mcp

`vin-lookup-mcp` is a small MCP server for NHTSA vPIC lookups.

It runs on Python 3.14+ with `uv` and exposes:

- VIN decoding via `decode_vin`
- Canadian vehicle specs via `get_canadian_vehicle_specifications`

## Free API

This project uses NHTSA's public vPIC API:

- API docs: https://vpic.nhtsa.dot.gov/api/Home
- Decoder UI: https://vpic.nhtsa.dot.gov/decoder/

No API key is required.

## MCP tools

The server exposes two MCP tools:

- `decode_vin(vin: str)`
- `get_canadian_vehicle_specifications(year: int, make: str, model?: str, units?: "Metric" | "US")`

`decode_vin`:

- normalizes the VIN
- validates that it is a 17-character VIN
- calls `DecodeVinValuesExtended`
- returns:
  - `vin`
  - `summary`
  - `raw`
  - `api_error_code`
  - `api_error_text`

`get_canadian_vehicle_specifications`:

- calls NHTSA's `GetCanadianVehicleSpecifications`
- accepts `year` and `make`, with optional `model` and `units`
- returns:
  - `search_criteria`
  - `count`
  - `message`
  - `summary`
  - `results`

## Project structure

```text
.
├── pyproject.toml
├── README.md
└── vin_mcp
    ├── __init__.py
    └── server.py
```

## Install with uv

Create a virtual environment with `uv`:

```bash
uv venv --python 3.14
uv sync
```

If `uv` is installed in `~/.local/bin` and is not on your shell `PATH`, either run it with the full path:

```bash
~/.local/bin/uv venv --python 3.14
~/.local/bin/uv sync
```

or add this to your shell config:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Run locally

Start the MCP stdio server:

```bash
uv run python -m vin_mcp.server
```

If `uv` is not on your `PATH` yet:

```bash
~/.local/bin/uv run python -m vin_mcp.server
```

## Test without MCP

You can decode a VIN directly from the command line:

```bash
uv run python -m vin_mcp.server --decode 1HGCM82633A004352
```

For just the compact summary:

```bash
uv run python -m vin_mcp.server --decode 1HGCM82633A004352 --summary-only
```

You can also test the Canadian specifications endpoint directly:

```bash
uv run python -m vin_mcp.server \
  --canadian-specs-year 2011 \
  --canadian-specs-make Acura
```

For just the compact summary:

```bash
uv run python -m vin_mcp.server \
  --canadian-specs-year 2011 \
  --canadian-specs-make Acura \
  --summary-only
```

For a quick end-to-end CLI smoke test, run:

```bash
./scripts/smoke_test.sh
```

## Example MCP config

For an MCP client that launches local stdio servers, the config will look roughly like this:

```json
{
  "mcpServers": {
    "vin": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "vin_mcp.server"]
    }
  }
}
```

Replace the Python path with your real project virtualenv path.

## Notes

- vPIC is strongest for vehicles intended for sale or import into the United States.
- Canadian specifications come from the dedicated vPIC `GetCanadianVehicleSpecifications` endpoint.
- NHTSA notes that VIN decoding is for model years 1981 and newer.
- The server currently advertises two tools through MCP tool metadata, and the MCP client or model decides when to call them.
- This server implements the MCP stdio protocol directly, so it does not need the Python MCP SDK.
- Because the project has no external dependencies, `uv sync` should work without internet once the local Python is available.

## Why I built this

I was shopping for cars and wanted to talk to ChatGPT about them by pasting the VIN number rather than the full model information.

As an TechOps Eng at Stripe, we use a lot of MCP servers so I wanted to learn how to build my own. I only used Codex for this.
