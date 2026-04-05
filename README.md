# vin-lookup-mcp

`vin-lookup-mcp` is an MCP server for NHTSA vPIC lookups. It exposes two tools:

- `decode_vin` for 17-character VIN decoding
- `get_canadian_vehicle_specifications` for Canadian-market vehicle specs

## Example prompt

```text
Use only the registered MCP tool `decode_vin` for each VIN below. Do not inspect local files, search my home directory, or invoke `python`/`uv` directly. Decode each VIN with the MCP tool and give me a short summary for each one.

5YJ3E1EB5KF123456
1N4AL21E87C118393
1P8ZA1279SZ215470
1HGCM82633A004352
1FTFW1EF1EKE12345
JHMFA16586S012345
2HGFG3B59FH512345
3VWFE21C04M000001
1G1JC5244T7258391
JTDKB20U093123456
```

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

## Run locally

Start the MCP stdio server:

```bash
uv run python -m vin_lookup_mcp.server
```

## Test without MCP

You can decode a VIN directly from the command line:

```bash
uv run python -m vin_lookup_mcp.server --decode 1HGCM82633A004352
```

For just the compact summary:

```bash
uv run python -m vin_lookup_mcp.server --decode 1HGCM82633A004352 --summary-only
```

You can also test the Canadian specifications endpoint directly:

```bash
uv run python -m vin_lookup_mcp.server \
  --canadian-specs-year 2011 \
  --canadian-specs-make Acura
```

For just the compact summary:

```bash
uv run python -m vin_lookup_mcp.server \
  --canadian-specs-year 2011 \
  --canadian-specs-make Acura \
  --summary-only
```

For a quick end-to-end CLI smoke test, run:

```bash
bash scripts/smoke_test.sh
```

## Project structure

```text
.
├── pyproject.toml
├── README.md
├── scripts
│   └── smoke_test.sh
└── vin_lookup_mcp
    ├── __init__.py
    └── server.py
```

## Notes

- vPIC is strongest for vehicles intended for sale or import into the United States.
- Canadian specifications come from the dedicated vPIC `GetCanadianVehicleSpecifications` endpoint.
- NHTSA notes that VIN decoding is for model years 1981 and newer.
- The MCP server uses the official Python MCP SDK via `FastMCP`.

## Why I built this

I was shopping for cars and wanted to talk to ChatGPT about them by pasting the VIN number rather than the full model information.

At my job we use a lot of MCP servers so I wanted to learn how to build my own. I only used Codex for this.
