"""Schema-validated, atomic CSV manifest I/O."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from jsonschema import Draft202012Validator


class ManifestValidationError(ValueError):
    """Raised for schema-invalid or structurally invalid manifest records."""


def load_schema(path: Path) -> dict:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_records(records: Sequence[Mapping[str, object]], schema: Mapping) -> None:
    validator = Draft202012Validator(schema)
    failures: list[str] = []
    for index, record in enumerate(records):
        errors = sorted(validator.iter_errors(dict(record)), key=lambda item: list(item.path))
        failures.extend(
            f"row {index} {'.'.join(str(part) for part in error.path)}: {error.message}"
            for error in errors
        )
    if failures:
        raise ManifestValidationError("\n".join(failures[:20]))


def _serialize(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def _types(spec: Mapping[str, object]) -> set[str]:
    value = spec.get("type", "string")
    return {value} if isinstance(value, str) else set(value)


def _deserialize(value: str, spec: Mapping[str, object]) -> object:
    types = _types(spec)
    if value == "" and "null" in types:
        return None
    if "array" in types or "object" in types:
        return json.loads(value)
    if "string" in types:
        return value
    if "boolean" in types:
        lowered = value.lower()
        if lowered not in {"true", "false"}:
            raise ManifestValidationError(f"invalid boolean CSV value: {value!r}")
        return lowered == "true"
    if "integer" in types:
        return int(value)
    if "number" in types:
        return float(value)
    return value


def write_csv_manifest(
    path: Path, records: Sequence[Mapping[str, object]], schema: Mapping
) -> None:
    validate_records(records, schema)
    fields = list(schema["properties"])
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
            writer.writeheader()
            for record in records:
                writer.writerow({field: _serialize(record.get(field)) for field in fields})
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def read_csv_manifest(path: Path, schema: Mapping) -> list[dict[str, object]]:
    properties = schema["properties"]
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(properties):
            raise ManifestValidationError(
                f"manifest header mismatch: expected {list(properties)}, got {reader.fieldnames}"
            )
        records = [
            {field: _deserialize(value, properties[field]) for field, value in row.items()}
            for row in reader
        ]
    validate_records(records, schema)
    return records
