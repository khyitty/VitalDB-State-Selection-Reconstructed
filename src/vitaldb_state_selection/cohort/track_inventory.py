"""Exact, versioned track-alias resolution without fuzzy matching."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from .guards import CohortGuardError, assert_source_ids_within_range, normalize_caseid


@dataclass(frozen=True)
class AliasRegistry:
    schema_version: int
    active: dict[str, tuple[str, ...]]
    unit_status: dict[str, str]
    pending: tuple[str, ...]

    @classmethod
    def from_yaml(cls, path: Path) -> "AliasRegistry":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if payload.get("review_policy") != "human_approval_required":
            raise CohortGuardError("track alias configuration must require human approval")
        active: dict[str, tuple[str, ...]] = {}
        unit_status: dict[str, str] = {}
        claimed_names: dict[str, str] = {}
        for concept, item in payload.get("aliases", {}).items():
            if item.get("status") != "protocol_validated":
                raise CohortGuardError(f"unapproved active alias concept: {concept}")
            concept_unit_status = str(item.get("unit_status", ""))
            if concept_unit_status not in {"pending_human_review", "validated"}:
                raise CohortGuardError(f"invalid unit review status for {concept}")
            names = tuple(str(name).strip() for name in item.get("names", []))
            if not names or any(not name for name in names):
                raise CohortGuardError(f"alias concept has no exact names: {concept}")
            for name in names:
                if name in claimed_names:
                    raise CohortGuardError(
                        f"track alias {name!r} belongs to both {claimed_names[name]} and {concept}"
                    )
                claimed_names[name] = concept
            active[str(concept)] = names
            unit_status[str(concept)] = concept_unit_status
        pending = tuple(str(item) for item in payload.get("pending_concepts", []))
        if set(active) & set(pending):
            raise CohortGuardError("active and pending alias concepts overlap")
        return cls(int(payload["schema_version"]), active, unit_status, pending)

    def concept_for(self, track_name: str) -> str | None:
        for concept, names in self.active.items():
            if track_name in names:
                return concept
        return None

    def units_validated(self, concepts: Iterable[str]) -> bool:
        return all(self.unit_status.get(concept) == "validated" for concept in concepts)


def index_track_rows(
    rows: Iterable[Mapping[str, object]], registry: AliasRegistry
) -> dict[int, dict[str, list[dict[str, str]]]]:
    materialized = list(rows)
    assert_source_ids_within_range(row.get("caseid") for row in materialized)
    indexed: dict[int, dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in materialized:
        caseid = normalize_caseid(row.get("caseid"))
        name = str(row.get("tname", "")).strip()
        concept = registry.concept_for(name)
        if concept is None:
            continue
        tid = str(row.get("tid", "")).strip()
        if not tid:
            raise CohortGuardError(f"case {caseid} track {name!r} has no tid")
        indexed[caseid][concept].append({"tname": name, "tid": tid})
    return {
        caseid: {concept: list(items) for concept, items in concepts.items()}
        for caseid, concepts in indexed.items()
    }


def availability(
    case_tracks: Mapping[str, list[dict[str, str]]], registry: AliasRegistry
) -> dict[str, bool | None]:
    result: dict[str, bool | None] = {
        concept: bool(case_tracks.get(concept)) for concept in registry.active
    }
    result.update({concept: None for concept in registry.pending})
    return result
