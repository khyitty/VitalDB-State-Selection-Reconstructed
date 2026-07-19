"""Outcome-blind Phase 5B eligibility decision-support summaries."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .guards import CohortGuardError, assert_manifest_complete, normalize_caseid
from .metadata_audit import EXPECTED_ACTIVE_ALIASES, assert_phase5a_boundaries
from .track_inventory import AliasRegistry


OFFICIAL_DATASET_OVERVIEW = (
    "https://vitaldb.net/dataset/?documentId="
    "13qqajnNZzkN7NZ9aXnaQ-47NWy7kx-a6gbrcEsi-gak"
    "&query=overview&sectionId=h.vcpgs1yemdb5"
)
OFFICIAL_OPEN_DATASET_API = (
    "https://vitaldb.net/docs/?documentId=API%2FWeb_API_OpenDataset.md"
)
EXPECTED_PRIMARY_COMPLETE_COUNT = 3289


@dataclass(frozen=True)
class RelevantTrackSpec:
    track_name: str
    field: str
    requested_scope: str
    official_description: str
    official_unit: str
    volatile_candidate: bool = False


RELEVANT_TRACK_SPECS = (
    RelevantTrackSpec("BIS/SQI", "bis_sqi_present", "bis_sqi", "Signal quality index", "%"),
    RelevantTrackSpec("Orchestra/PPF20_VOL", "ppf20_vol_present", "propofol_support", "Infused volume (propofol 20 mg/mL)", "mL"),
    RelevantTrackSpec("Orchestra/PPF20_CP", "ppf20_cp_present", "propofol_support", "Plasma concentration (propofol 20 mg/mL)", "mcg/mL"),
    RelevantTrackSpec("Orchestra/PPF20_CE", "ppf20_ce_present", "propofol_support", "Effect-site concentration (propofol 20 mg/mL)", "mcg/mL"),
    RelevantTrackSpec("Orchestra/PPF20_CT", "ppf20_ct_present", "propofol_support", "Target concentration (propofol 20 mg/mL)", "mcg/mL"),
    RelevantTrackSpec("Orchestra/RFTN20_VOL", "rftn20_vol_present", "remifentanil_20_support", "Infused volume (remifentanil 20 mcg/mL)", "mL"),
    RelevantTrackSpec("Orchestra/RFTN20_CP", "rftn20_cp_present", "remifentanil_20_support", "Plasma concentration (remifentanil 20 mcg/mL)", "ng/mL"),
    RelevantTrackSpec("Orchestra/RFTN20_CE", "rftn20_ce_present", "remifentanil_20_support", "Effect-site concentration (remifentanil 20 mcg/mL)", "ng/mL"),
    RelevantTrackSpec("Orchestra/RFTN20_CT", "rftn20_ct_present", "remifentanil_20_support", "Target concentration (remifentanil 20 mcg/mL)", "ng/mL"),
    RelevantTrackSpec("Orchestra/RFTN50_RATE", "rftn50_rate_present", "remifentanil_50_support", "Infusion rate (remifentanil 50 mcg/mL)", "mL/hr"),
    RelevantTrackSpec("Orchestra/RFTN50_VOL", "rftn50_vol_present", "remifentanil_50_support", "Infused volume (remifentanil 50 mcg/mL)", "mL"),
    RelevantTrackSpec("Orchestra/RFTN50_CP", "rftn50_cp_present", "remifentanil_50_support", "Plasma concentration (remifentanil 50 mcg/mL)", "ng/mL"),
    RelevantTrackSpec("Orchestra/RFTN50_CE", "rftn50_ce_present", "remifentanil_50_support", "Effect-site concentration (remifentanil 50 mcg/mL)", "ng/mL"),
    RelevantTrackSpec("Orchestra/RFTN50_CT", "rftn50_ct_present", "remifentanil_50_support", "Target concentration (remifentanil 50 mcg/mL)", "ng/mL"),
    RelevantTrackSpec("Primus/EXP_SEVO", "primus_exp_sevo_present", "volatile_candidate", "Expiratory sevoflurane pressure", "", True),
    RelevantTrackSpec("Primus/INSP_SEVO", "primus_insp_sevo_present", "volatile_candidate", "Inspiratory sevoflurane pressure", "", True),
    RelevantTrackSpec("Primus/EXP_DES", "primus_exp_des_present", "volatile_candidate", "Expiratory desflurane pressure", "", True),
    RelevantTrackSpec("Primus/INSP_DES", "primus_insp_des_present", "volatile_candidate", "Inspiratory desflurane pressure", "", True),
    RelevantTrackSpec("Solar8000/GAS2_EXPIRED", "solar8000_gas2_expired_present", "volatile_candidate", "Expiratory volatile concentration", "", True),
    RelevantTrackSpec("Solar8000/GAS2_INSPIRED", "solar8000_gas2_inspired_present", "volatile_candidate", "Inspiratory volatile concentration", "", True),
    RelevantTrackSpec("Primus/MAC", "primus_mac_present", "volatile_candidate", "Minimum alveolar concentration of volatile", "", True),
)

RATE_DOCUMENTATION = (
    {
        "track_name": "Orchestra/PPF20_RATE",
        "documented_meaning": "Infusion rate (propofol 20 mg/mL)",
        "documented_unit": "mL/hr",
        "review_status": "source_documented_pending_human_review",
    },
    {
        "track_name": "Orchestra/RFTN20_RATE",
        "documented_meaning": "Infusion rate (remifentanil 20 mcg/mL)",
        "documented_unit": "mL/hr",
        "review_status": "source_documented_pending_human_review",
    },
    {
        "track_name": "Orchestra/RFTN50_RATE",
        "documented_meaning": "Infusion rate (remifentanil 50 mcg/mL)",
        "documented_unit": "mL/hr",
        "review_status": "source_documented_pending_human_review",
    },
)


def assert_phase5b_boundaries(
    config: Mapping[str, object],
    registry: AliasRegistry,
    manifest_records: Sequence[Mapping[str, object]],
    phase5a_snapshot: Mapping[str, object],
) -> None:
    assert_phase5a_boundaries(config, registry)
    assert_manifest_complete([row["caseid"] for row in manifest_records])
    if len(manifest_records) != 6388:
        raise CohortGuardError("Phase 5B requires all 6,388 Phase 5A manifest rows")
    if phase5a_snapshot.get("phase") != "5A_full_metadata_and_track_inventory":
        raise CohortGuardError("Phase 5B requires the committed Phase 5A source snapshot")
    scope = phase5a_snapshot.get("scope", {})
    if scope.get("legacy_98_ids_accessed") is not False:
        raise CohortGuardError("Phase 5A legacy-ID boundary is not intact")
    if phase5a_snapshot.get("endpoints", {}).get("tracks", {}).get("status") != "complete":
        raise CohortGuardError("Phase 5A track snapshot is incomplete")


def build_relevant_track_presence(
    caseids: Sequence[object], track_rows: Sequence[Mapping[str, object]]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    normalized = [normalize_caseid(caseid) for caseid in caseids]
    assert_manifest_complete(normalized)
    specs_by_name = {spec.track_name: spec for spec in RELEVANT_TRACK_SPECS}
    flags = {
        caseid: {spec.field: False for spec in RELEVANT_TRACK_SPECS}
        for caseid in normalized
    }
    row_counts: Counter[str] = Counter()
    case_sets: dict[str, set[int]] = defaultdict(set)
    tid_sets: dict[str, set[str]] = defaultdict(set)
    for row in track_rows:
        name = str(row.get("tname", "")).strip()
        spec = specs_by_name.get(name)
        if spec is None:
            continue
        caseid = normalize_caseid(row.get("caseid"))
        if caseid not in flags:
            raise CohortGuardError(f"relevant track has out-of-manifest caseid {caseid}")
        flags[caseid][spec.field] = True
        row_counts[name] += 1
        case_sets[name].add(caseid)
        tid_sets[name].add(str(row.get("tid", "")).strip())

    volatile_fields = tuple(spec.field for spec in RELEVANT_TRACK_SPECS if spec.volatile_candidate)
    presence: list[dict[str, object]] = []
    for caseid in normalized:
        row: dict[str, object] = {"caseid": caseid, **flags[caseid]}
        row["volatile_candidate_track_present"] = any(
            bool(row[field]) for field in volatile_fields
        )
        presence.append(row)

    inventory = []
    for spec in RELEVANT_TRACK_SPECS:
        inventory.append(
            {
                "track_name": spec.track_name,
                "requested_scope": spec.requested_scope,
                "official_description": spec.official_description,
                "official_unit": spec.official_unit,
                "row_count": row_counts[spec.track_name],
                "case_count": len(case_sets[spec.track_name]),
                "distinct_tid_count": len(tid_sets[spec.track_name]),
                "review_status": "pending_human_review",
                "auto_approved": False,
                "merged_with_other_track": False,
                "official_source_url": OFFICIAL_DATASET_OVERVIEW,
            }
        )
    return presence, inventory


def _frequency(values: Sequence[object], *, missing_label: str = "<missing>") -> list[dict[str, object]]:
    counts = Counter(missing_label if value is None or value == "" else str(value) for value in values)
    return [
        {"value": value, "case_count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _adult_label(value: object) -> str:
    if value is True:
        return "adult_age_ge_18"
    if value is False:
        return "not_adult_age_lt_18"
    return "unknown"


def _bool_frequency(rows: Sequence[Mapping[str, object]], field: str) -> list[dict[str, object]]:
    return _frequency(["present" if row[field] is True else "absent" for row in rows])


def summarize_decision_support(
    manifest_records: Sequence[Mapping[str, object]],
    presence_records: Sequence[Mapping[str, object]],
    relevant_inventory: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    manifest_caseids = [normalize_caseid(row["caseid"]) for row in manifest_records]
    presence_caseids = [normalize_caseid(row["caseid"]) for row in presence_records]
    assert_manifest_complete(manifest_caseids)
    assert_manifest_complete(presence_caseids)
    if manifest_caseids != presence_caseids:
        raise CohortGuardError("Phase 5A manifest and Phase 5B presence rows are misaligned")
    presence_by_case = {int(row["caseid"]): row for row in presence_records}
    joined = [
        {**manifest, **presence_by_case[int(manifest["caseid"])]}
        for manifest in manifest_records
    ]
    primary = [
        row
        for row in joined
        if all(
            row[f"{concept}_track_available"] is True
            for concept in ("bis", "propofol_rate", "remifentanil_rate")
        )
    ]
    if len(primary) != EXPECTED_PRIMARY_COMPLETE_COUNT:
        raise CohortGuardError(
            f"expected {EXPECTED_PRIMARY_COMPLETE_COUNT} exact-primary cases, got {len(primary)}"
        )

    track_fields = [
        spec.field
        for spec in RELEVANT_TRACK_SPECS
        if spec.requested_scope in {
            "bis_sqi",
            "propofol_support",
            "remifentanil_20_support",
            "remifentanil_50_support",
        }
        and not spec.field.endswith("_ct_present")
    ]
    track_presence = {
        field: _bool_frequency(primary, field) for field in track_fields
    }
    combination_fields = (
        "anesthesia_type",
        "adult_candidate",
        "volatile_candidate_track_present",
        *track_fields,
    )
    combination_counts: Counter[str] = Counter()
    for row in primary:
        parts = []
        for field in combination_fields:
            value = row[field]
            if field == "adult_candidate":
                encoded = _adult_label(value)
            elif isinstance(value, bool):
                encoded = str(int(value))
            else:
                encoded = "<missing>" if value is None or value == "" else str(value)
            parts.append(f"{field}={encoded}")
        combination_counts["|".join(parts)] += 1

    exact_primary = primary
    exact_primary_adult = [row for row in exact_primary if row["adult_candidate"] is True]
    adult_general = [
        row for row in exact_primary_adult if row["anesthesia_type"] == "General"
    ]
    no_volatile_candidate = [
        row for row in adult_general if row["volatile_candidate_track_present"] is False
    ]
    scenarios = [
        {
            "scenario": "exact_primary_tracks_only",
            "descriptive_expected_case_count": len(exact_primary),
            "excluded_case_count": 6388 - len(exact_primary),
            "sequential_exclusion_reason_counts": {
                "missing_one_or_more_exact_primary_tracks": 6388 - len(exact_primary)
            },
        },
        {
            "scenario": "exact_primary_plus_adult_plus_exact_general",
            "descriptive_expected_case_count": len(adult_general),
            "excluded_case_count": 6388 - len(adult_general),
            "sequential_exclusion_reason_counts": {
                "missing_one_or_more_exact_primary_tracks": 6388 - len(exact_primary),
                "not_adult_after_exact_primary": len(exact_primary) - len(exact_primary_adult),
                "anesthesia_type_not_exact_general_after_primary_and_adult": len(exact_primary_adult) - len(adult_general),
            },
        },
        {
            "scenario": "exact_primary_plus_adult_plus_exact_general_plus_no_volatile_candidate_track",
            "descriptive_expected_case_count": len(no_volatile_candidate),
            "excluded_case_count": 6388 - len(no_volatile_candidate),
            "sequential_exclusion_reason_counts": {
                "missing_one_or_more_exact_primary_tracks": 6388 - len(exact_primary),
                "not_adult_after_exact_primary": len(exact_primary) - len(exact_primary_adult),
                "anesthesia_type_not_exact_general_after_primary_and_adult": len(exact_primary_adult) - len(adult_general),
                "volatile_candidate_track_present_after_prior_criteria": len(adult_general) - len(no_volatile_candidate),
            },
        },
    ]

    ages = [float(row["age"]) for row in manifest_records if row["age"] is not None]
    return {
        "phase": "5B_eligibility_decision_support_audit",
        "scientific_result": False,
        "decision_support_only": True,
        "case_accounting": {
            "manifest_row_count": len(manifest_records),
            "presence_row_count": len(presence_records),
            "caseid_min": min(manifest_caseids),
            "caseid_max": max(manifest_caseids),
            "duplicate_case_count": len(manifest_caseids) - len(set(manifest_caseids)),
            "missing_case_count": 6388 - len(set(manifest_caseids)),
        },
        "full_manifest_descriptive": {
            "anesthesia_type_frequency": _frequency([row["anesthesia_type"] for row in manifest_records]),
            "operation_type_frequency": _frequency([row["operation_type"] for row in manifest_records]),
            "emergency_status_frequency": _frequency([row["emergency_status"] for row in manifest_records]),
            "age": {
                "available_count": len(ages),
                "missing_count": len(manifest_records) - len(ages),
                "minimum": min(ages),
                "maximum": max(ages),
                "adult_definition": "age >= 18 years (protocol-defined descriptive flag)",
                "adult_status_frequency": _frequency([_adult_label(row["adult_candidate"]) for row in manifest_records]),
            },
            "asa_missingness": {
                "missing_count": sum(row["asa"] is None for row in manifest_records),
                "available_count": sum(row["asa"] is not None for row in manifest_records),
            },
        },
        "relevant_track_review": {
            "requested_track_name_count": len(RELEVANT_TRACK_SPECS),
            "phase5a_unapproved_name_total": 193,
            "all_193_semantically_classified": False,
            "review_status": "pending_human_review",
            "auto_approved_count": 0,
            "rftn20_rftn50_merged": False,
            "inventory": [dict(row) for row in relevant_inventory],
        },
        "exact_primary_subset": {
            "case_count": len(primary),
            "anesthesia_type_frequency": _frequency([row["anesthesia_type"] for row in primary]),
            "adult_status_frequency": _frequency([_adult_label(row["adult_candidate"]) for row in primary]),
            "volatile_candidate_track_presence": _bool_frequency(primary, "volatile_candidate_track_present"),
            "track_presence": track_presence,
            "combination_field_order": list(combination_fields),
            "combination_counts": [
                {"combination": key, "descriptive_expected_case_count": count}
                for key, count in sorted(combination_counts.items(), key=lambda item: (-item[1], item[0]))
            ],
        },
        "rate_and_label_primary_source_review": {
            "source_url": OFFICIAL_DATASET_OVERVIEW,
            "findings": [dict(item) for item in RATE_DOCUMENTATION],
            "rftn20_rftn50_meaning": "Official track descriptions distinguish remifentanil 20 mcg/mL from 50 mcg/mL.",
            "automatic_merge_performed": False,
            "config_unit_status_changed": False,
            "final_review_status": "pending_human_review",
        },
        "eligibility_scenarios": scenarios,
        "selected_scenario": None,
        "pending_decisions": [
            "tiva_classification",
            "volatile_exposure_from_values",
            "final_alias_approval",
            "case_level_rate_unit_validation",
            "legacy_98_overlap",
            "final_eligibility",
            "signal_quality_thresholds",
        ],
        "execution_flags": {
            "raw_signal_downloaded": False,
            "legacy_98_ids_accessed": False,
            "alias_configuration_changed": False,
            "quality_thresholds_finalized": False,
            "cohort_frozen": False,
            "split_created": False,
            "prediction_run": False,
            "feature_selection_run": False,
            "cpce_reconstruction_run": False,
            "ppo_run": False,
        },
    }


def render_decision_support_report(summary: Mapping[str, object]) -> str:
    descriptive = summary["full_manifest_descriptive"]
    primary = summary["exact_primary_subset"]
    lines = [
        "# Phase 5B Eligibility Decision-Support Audit",
        "",
        "## Interpretation boundary",
        "",
        "This is an outcome-blind decision-support inventory, not an eligibility rule",
        "selection or cohort freeze. Track presence does not prove non-zero drug delivery",
        "or volatile-agent exposure. No raw time-series signal or legacy 98-case ID was",
        "accessed. No alias or unit configuration was approved or changed.",
        "",
        "## Complete manifest accounting",
        "",
        "| Measure | Count |",
        "|---|---:|",
        f"| Phase 5A manifest rows | {summary['case_accounting']['manifest_row_count']} |",
        f"| Phase 5B presence rows | {summary['case_accounting']['presence_row_count']} |",
        f"| Duplicate case IDs | {summary['case_accounting']['duplicate_case_count']} |",
        f"| Missing case IDs | {summary['case_accounting']['missing_case_count']} |",
        "",
        "## Full 6,388-case clinical descriptors",
        "",
        "### Anesthesia type",
        "",
        "| Exact source value | Cases |",
        "|---|---:|",
    ]
    for item in descriptive["anesthesia_type_frequency"]:
        lines.append(f"| `{item['value']}` | {item['case_count']} |")
    lines.extend(["", "### Operation type", "", "| Exact source value | Cases |", "|---|---:|"])
    for item in descriptive["operation_type_frequency"]:
        lines.append(f"| `{item['value']}` | {item['case_count']} |")
    lines.extend(["", "### Emergency status", "", "| Exact source value | Cases |", "|---|---:|"])
    for item in descriptive["emergency_status_frequency"]:
        lines.append(f"| `{item['value']}` | {item['case_count']} |")
    age = descriptive["age"]
    asa = descriptive["asa_missingness"]
    lines.extend(
        [
            "",
            "### Age and ASA completeness",
            "",
            f"Observed age range: **{age['minimum']}–{age['maximum']} years**; missing age: **{age['missing_count']}**.",
            "Adult status is the protocol-defined descriptive flag `age >= 18`; it is not a cohort decision.",
            "",
            "| Adult-status flag | Cases |",
            "|---|---:|",
        ]
    )
    for item in age["adult_status_frequency"]:
        lines.append(f"| `{item['value']}` | {item['case_count']} |")
    lines.extend(
        [
            "",
            f"ASA is available in **{asa['available_count']}** cases and missing in **{asa['missing_count']}** cases.",
            "",
            "## Narrow research-relevant unapproved-track review",
            "",
            "Only the 21 requested or explicitly volatile-labeled names below were reviewed;",
            "the other Phase 5A names were not semantically classified. All remain",
            "`pending_human_review`, and no RFTN20/RFTN50 merge was performed.",
            "",
            "| Track | Official description | Unit in official overview | Cases | Rows |",
            "|---|---|---|---:|---:|",
        ]
    )
    for item in summary["relevant_track_review"]["inventory"]:
        lines.append(
            f"| `{item['track_name']}` | {item['official_description']} | "
            f"{item['official_unit'] or 'not reviewed here'} | {item['case_count']} | {item['row_count']} |"
        )
    lines.extend(
        [
            "",
            "## Exact-primary subset (3,289 cases)",
            "",
            "### Anesthesia type",
            "",
            "| Exact source value | Cases |",
            "|---|---:|",
        ]
    )
    for item in primary["anesthesia_type_frequency"]:
        lines.append(f"| `{item['value']}` | {item['case_count']} |")
    lines.extend(["", "### Adult status", "", "| Value | Cases |", "|---|---:|"])
    for item in primary["adult_status_frequency"]:
        lines.append(f"| `{item['value']}` | {item['case_count']} |")
    lines.extend(["", "### Volatile-candidate track presence", "", "| Value | Cases |", "|---|---:|"])
    for item in primary["volatile_candidate_track_presence"]:
        lines.append(f"| `{item['value']}` | {item['case_count']} |")
    lines.extend(["", "### BIS/SQI and PPF/RFTN support-track presence", "", "| Track-presence field | Present | Absent |", "|---|---:|---:|"])
    for field, frequencies in primary["track_presence"].items():
        counts = {item["value"]: item["case_count"] for item in frequencies}
        lines.append(f"| `{field}` | {counts.get('present', 0)} | {counts.get('absent', 0)} |")
    lines.extend(
        [
            "",
            "The full joint combination table is retained in the machine-readable summary",
            f"({len(primary['combination_counts'])} observed combinations; counts sum to 3,289).",
            "",
            "## Eligibility scenarios — comparison only",
            "",
            "No scenario was selected. `General` is matched as the exact source value, and",
            "the volatile criterion is track presence only, not measured exposure.",
            "",
            "| Scenario | Descriptive expected cases | Excluded from 6,388 |",
            "|---|---:|---:|",
        ]
    )
    for scenario in summary["eligibility_scenarios"]:
        lines.append(
            f"| `{scenario['scenario']}` | {scenario['descriptive_expected_case_count']} | {scenario['excluded_case_count']} |"
        )
    lines.extend(["", "### Sequential exclusion accounting", ""])
    for scenario in summary["eligibility_scenarios"]:
        lines.extend([f"**`{scenario['scenario']}`**", "", "| Reason | Cases |", "|---|---:|"])
        for reason, count in scenario["sequential_exclusion_reason_counts"].items():
            lines.append(f"| `{reason}` | {count} |")
        lines.append("")
    lines.extend(
        [
            "## Primary-source unit and label review",
            "",
            "The official VitalDB dataset overview documents `PPF20_RATE`, `RFTN20_RATE`,",
            "and `RFTN50_RATE` as `mL/hr`. It labels PPF20 as propofol 20 mg/mL and",
            "RFTN20/RFTN50 as remifentanil 20/50 mcg/mL. This documentary finding does",
            "not change the versioned unit-review status and does not merge the two",
            "remifentanil track families.",
            "",
            f"- [Official VitalDB dataset overview]({OFFICIAL_DATASET_OVERVIEW})",
            f"- [Official VitalDB Open Dataset API]({OFFICIAL_OPEN_DATASET_API})",
            "",
            "## Work deliberately not performed",
            "",
            "No raw-signal download, legacy-ID access, final alias approval, threshold",
            "finalization, cohort freeze, split, prediction, feature selection, Cp/Ce",
            "reconstruction, or PPO execution occurred. Phase 5B stops here.",
            "",
        ]
    )
    return "\n".join(lines)
