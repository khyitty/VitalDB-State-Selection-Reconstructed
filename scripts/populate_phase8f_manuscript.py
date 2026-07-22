"""Populate the Phase 8F manuscript from one schema-validated frozen aggregate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.publication.manuscript_population import populate_manuscript  # noqa: E402
from vitaldb_state_selection.publication.phase8f_renderer import load_aggregate, validate_aggregate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mapping-output", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    aggregate = load_aggregate(args.aggregate)
    schema = json.loads((ROOT / "schemas/phase8f_aggregate_results.schema.json").read_text(encoding="utf-8"))
    validate_aggregate(aggregate, schema)
    source = args.input.read_text(encoding="utf-8")
    populated, report = populate_manuscript(source, aggregate)
    report = {
        "schema_version": "phase8f-manuscript-token-map-v1",
        "source_aggregate_sha256": hashlib.sha256(args.aggregate.read_bytes()).hexdigest(),
        **report,
    }
    manuscript_bytes = populated.encode("utf-8")
    mapping_bytes = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if args.verify_only:
        print(json.dumps({**report, "writes_performed": 0}, sort_keys=True))
        return 0
    if args.output.exists() and args.output.resolve() != args.input.resolve():
        raise RuntimeError("manuscript output already exists; overwrite refused")
    if args.mapping_output.exists():
        raise RuntimeError("manuscript mapping output already exists; overwrite refused")
    for path, payload in ((args.output, manuscript_bytes), (args.mapping_output, mapping_bytes)):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".partial", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    print(json.dumps({**report, "writes_performed": 2}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
