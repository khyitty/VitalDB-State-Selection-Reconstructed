"""Validate and render publication-safe aggregate Phase 8E results."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vitaldb_state_selection.publication.phase8f_renderer import (  # noqa: E402
    load_aggregate,
    render_payloads,
    validate_aggregate,
    write_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.verify_only and args.overwrite:
        parser.error("--verify-only cannot be combined with --overwrite")
    schema = json.loads((ROOT / "schemas/phase8f_aggregate_results.schema.json").read_text(encoding="utf-8"))
    input_sha256 = hashlib.sha256(args.input.read_bytes()).hexdigest()
    payload = load_aggregate(args.input)
    validate_aggregate(payload, schema)
    outputs = render_payloads(payload, source_sha256=input_sha256)
    summary = {
        "input_sha256": input_sha256,
        "output_file_count": len(outputs),
        "verify_only": bool(args.verify_only),
        "writes_performed": 0 if args.verify_only else len(outputs),
    }
    if not args.verify_only:
        write_outputs(args.output_dir, outputs, overwrite=args.overwrite)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
