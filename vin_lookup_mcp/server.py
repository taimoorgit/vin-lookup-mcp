from __future__ import annotations

import argparse
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import urlopen

from mcp.server.fastmcp import FastMCP

VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
VPIC_API_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"
CANADIAN_SPECS_API_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/GetCanadianVehicleSpecifications/?{query}"

mcp = FastMCP(
    "vin-lookup-mcp",
    instructions=(
        "Use this server for NHTSA vPIC vehicle lookups. "
        "Use decode_vin for 17-character VIN decoding. "
        "Use get_canadian_vehicle_specifications for Canadian-market specs by year, make, "
        "and optional model."
    ),
)


def _normalize_vin(vin: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", vin).upper()


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return value


def _filter_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: cleaned
        for key, value in record.items()
        if key not in {"ErrorCode", "ErrorText"}
        if (cleaned := _clean_value(value)) is not None
    }


def _summary(record: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "Make",
        "Model",
        "ModelYear",
        "VehicleType",
        "BodyClass",
        "Series",
        "Trim",
        "Manufacturer",
        "PlantCountry",
        "PlantState",
        "PlantCity",
        "EngineModel",
        "DisplacementL",
        "FuelTypePrimary",
        "DriveType",
        "Doors",
        "GVWR",
    ]
    return {
        key: cleaned
        for key in keys
        if (cleaned := _clean_value(record.get(key))) is not None
    }


def _fetch_json(url: str) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"NHTSA API request failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach the NHTSA API: {exc.reason}.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("NHTSA API returned invalid JSON.") from exc


@mcp.tool()
def decode_vin(vin: str) -> dict[str, Any]:
    """Decode a 17-character vehicle VIN using NHTSA's free vPIC API."""

    normalized_vin = _normalize_vin(vin)
    if not VIN_PATTERN.fullmatch(normalized_vin):
        raise ValueError(
            "VIN must be 17 characters and use only digits and capital letters "
            "excluding I, O, and Q."
        )

    payload = _fetch_json(VPIC_API_URL.format(vin=quote(normalized_vin)))
    results = payload.get("Results") or []
    if not results:
        raise RuntimeError("NHTSA API returned no results for this VIN.")

    record = results[0]
    error_code = _clean_value(record.get("ErrorCode"))
    error_text = _clean_value(record.get("ErrorText"))

    return {
        "vin": normalized_vin,
        "summary": _summary(record),
        "raw": _filter_fields(record),
        "api_error_code": error_code,
        "api_error_text": error_text,
    }


def _normalize_make_or_model(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Make and model values cannot be empty.")
    return cleaned


def _canadian_specs_summary(specs_map: dict[str, str], year: int, make: str, model: str | None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "year": year,
        "make": specs_map.get("Make", make),
    }
    if model:
        summary["requested_model"] = model
    for key in ("Model", "WB", "OL", "OW", "OH", "CW", "TWF", "TWR", "WD"):
        value = specs_map.get(key)
        if value is not None:
            summary[key] = value
    return summary


@mcp.tool()
def get_canadian_vehicle_specifications(
    year: int,
    make: str,
    model: str | None = None,
    units: str = "Metric",
) -> dict[str, Any]:
    """Get Canadian vehicle specifications from NHTSA vPIC by year, make, and optional model."""

    if year < 1900:
        raise ValueError("Year must be a valid 4-digit model year.")

    normalized_units = units.strip().title()
    if normalized_units not in {"Metric", "Us"}:
        raise ValueError("Units must be either 'Metric' or 'US'.")

    query = {
        "year": year,
        "make": _normalize_make_or_model(make),
        "format": "json",
        "units": "US" if normalized_units == "Us" else "Metric",
    }
    if model:
        query["model"] = _normalize_make_or_model(model)

    payload = _fetch_json(CANADIAN_SPECS_API_URL.format(query=urlencode(query)))
    results = payload.get("Results") or []
    if not results:
        raise RuntimeError("NHTSA API returned no Canadian vehicle specifications.")

    structured_results = []
    for item in results:
        specs_list = item.get("Specs") or []
        specs_map = {
            spec["Name"]: spec["Value"]
            for spec in specs_list
            if isinstance(spec, dict)
            and isinstance(spec.get("Name"), str)
            and isinstance(spec.get("Value"), str)
        }
        structured_results.append({"specs": specs_list, "specs_map": specs_map})

    first_map = structured_results[0]["specs_map"]
    return {
        "search_criteria": payload.get("SearchCriteria"),
        "count": payload.get("Count", len(structured_results)),
        "message": payload.get("Message"),
        "summary": _canadian_specs_summary(first_map, year, query["make"], model),
        "results": structured_results,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="vin-lookup-mcp server and direct VIN decoder CLI.",
    )
    parser.add_argument(
        "--decode",
        metavar="VIN",
        help="Decode a VIN directly without starting the MCP stdio server.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="When used with a direct CLI command, print only the summary fields.",
    )
    parser.add_argument(
        "--canadian-specs-year",
        type=int,
        help="Get Canadian vehicle specifications by model year.",
    )
    parser.add_argument(
        "--canadian-specs-make",
        help="Vehicle make for the Canadian specifications lookup.",
    )
    parser.add_argument(
        "--canadian-specs-model",
        help="Optional model text for the Canadian specifications lookup.",
    )
    parser.add_argument(
        "--canadian-specs-units",
        default="Metric",
        help="Units for Canadian specs: Metric or US.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    if args.decode:
        result = decode_vin(args.decode)
        payload = result["summary"] if args.summary_only else result
        print(json.dumps(payload, indent=2))
        return

    if args.canadian_specs_year is not None:
        if not args.canadian_specs_make:
            raise SystemExit("--canadian-specs-make is required with --canadian-specs-year")
        result = get_canadian_vehicle_specifications(
            args.canadian_specs_year,
            args.canadian_specs_make,
            args.canadian_specs_model,
            args.canadian_specs_units,
        )
        payload = result["summary"] if args.summary_only else result
        print(json.dumps(payload, indent=2))
        return

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
