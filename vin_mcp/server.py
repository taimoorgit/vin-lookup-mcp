from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import urlopen

VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
VPIC_API_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"
CANADIAN_SPECS_API_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/GetCanadianVehicleSpecifications/?{query}"
PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {"name": "vin-mcp", "version": "0.1.0"}


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


def _decode_vin(vin: str) -> dict[str, Any]:
    url = VPIC_API_URL.format(vin=quote(vin))

    try:
        with urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"NHTSA API request failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach the NHTSA API: {exc.reason}.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("NHTSA API returned invalid JSON.") from exc

    results = payload.get("Results") or []
    if not results:
        raise RuntimeError("NHTSA API returned no results for this VIN.")

    record = results[0]
    error_code = _clean_value(record.get("ErrorCode"))
    error_text = _clean_value(record.get("ErrorText"))

    return {
        "vin": vin,
        "summary": _summary(record),
        "raw": _filter_fields(record),
        "api_error_code": error_code,
        "api_error_text": error_text,
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


def decode_vin(vin: str) -> dict[str, Any]:
    normalized_vin = _normalize_vin(vin)
    if not VIN_PATTERN.fullmatch(normalized_vin):
        raise ValueError(
            "VIN must be 17 characters and use only digits and capital letters "
            "excluding I, O, and Q."
        )

    return _decode_vin(normalized_vin)


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


def get_canadian_vehicle_specifications(
    year: int,
    make: str,
    model: str | None = None,
    units: str = "Metric",
) -> dict[str, Any]:
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


def _decode_vin_tool_definition() -> dict[str, Any]:
    return {
        "name": "decode_vin",
        "title": "Decode Vehicle VIN",
        "description": (
            "Decode a 17-character vehicle VIN using NHTSA's free vPIC API. "
            "Use this when a user mentions a VIN and wants details about the vehicle."
        ),
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "vin": {
                    "type": "string",
                    "description": "The 17-character vehicle identification number to decode.",
                }
            },
            "required": ["vin"],
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "vin": {"type": "string"},
                "summary": {"type": "object"},
                "raw": {"type": "object"},
                "api_error_code": {"type": ["string", "null"]},
                "api_error_text": {"type": ["string", "null"]},
            },
            "required": ["vin", "summary", "raw", "api_error_code", "api_error_text"],
            "additionalProperties": False,
        },
    }


def _canadian_specs_tool_definition() -> dict[str, Any]:
    return {
        "name": "get_canadian_vehicle_specifications",
        "title": "Get Canadian Vehicle Specifications",
        "description": (
            "Get Canadian vehicle specifications from NHTSA vPIC by year, make, "
            "and optionally model. Use this for Canadian-market dimensions or specs."
        ),
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Vehicle model year."},
                "make": {"type": "string", "description": "Vehicle make, for example Acura."},
                "model": {
                    "type": "string",
                    "description": "Optional model name or trim text to narrow the results.",
                },
                "units": {
                    "type": "string",
                    "description": "Either Metric or US.",
                    "enum": ["Metric", "US"],
                },
            },
            "required": ["year", "make"],
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "search_criteria": {"type": ["string", "null"]},
                "count": {"type": "integer"},
                "message": {"type": ["string", "null"]},
                "summary": {"type": "object"},
                "results": {"type": "array"},
            },
            "required": ["search_criteria", "count", "message", "summary", "results"],
            "additionalProperties": False,
        },
    }


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("utf-8").partition(":")
        headers[key.strip().lower()] = value.strip()

    content_length = headers.get("content-length")
    if not content_length:
        raise RuntimeError("Missing Content-Length header.")

    body = sys.stdin.buffer.read(int(content_length))
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _write_message(payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def _write_response(request_id: Any, result: dict[str, Any]) -> None:
    _write_message({"jsonrpc": "2.0", "id": request_id, "result": result})


def _write_error(request_id: Any, code: int, message: str) -> None:
    _write_message(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
    )


def _handle_initialize(request_id: Any, params: dict[str, Any]) -> None:
    requested_version = params.get("protocolVersion") or PROTOCOL_VERSION
    _write_response(
        request_id,
        {
            "protocolVersion": requested_version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": (
                "Use the decode_vin tool when a user mentions a 17-character VIN "
                "or asks for vehicle details from a VIN."
            ),
        },
    )


def _handle_tools_list(request_id: Any) -> None:
    _write_response(
        request_id,
        {"tools": [_decode_vin_tool_definition(), _canadian_specs_tool_definition()]},
    )


def _handle_tools_call(request_id: Any, params: dict[str, Any]) -> None:
    tool_name = params.get("name")
    arguments = params.get("arguments") or {}

    try:
        if tool_name == "decode_vin":
            vin = arguments.get("vin")
            if not isinstance(vin, str):
                raise ValueError("The 'vin' argument must be a string.")
            result = decode_vin(vin)
        elif tool_name == "get_canadian_vehicle_specifications":
            year = arguments.get("year")
            make = arguments.get("make")
            model = arguments.get("model")
            units = arguments.get("units", "Metric")
            if not isinstance(year, int):
                raise ValueError("The 'year' argument must be an integer.")
            if not isinstance(make, str):
                raise ValueError("The 'make' argument must be a string.")
            if model is not None and not isinstance(model, str):
                raise ValueError("The 'model' argument must be a string when provided.")
            if not isinstance(units, str):
                raise ValueError("The 'units' argument must be a string when provided.")
            result = get_canadian_vehicle_specifications(year, make, model, units)
        else:
            _write_error(request_id, -32601, "Unknown tool.")
            return
    except Exception as exc:
        _write_response(
            request_id,
            {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            },
        )
        return

    _write_response(
        request_id,
        {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "structuredContent": result,
            "isError": False,
        },
    )


def _serve_stdio() -> None:
    while True:
        message = _read_message()
        if message is None:
            break

        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}

        if method == "initialize":
            _handle_initialize(request_id, params)
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            _handle_tools_list(request_id)
        elif method == "tools/call":
            _handle_tools_call(request_id, params)
        elif request_id is not None:
            _write_error(request_id, -32601, f"Method not found: {method}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="VIN MCP server and direct VIN decoder CLI.",
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

    _serve_stdio()


if __name__ == "__main__":
    main()
