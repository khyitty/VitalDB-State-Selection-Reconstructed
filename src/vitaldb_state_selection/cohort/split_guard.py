"""Reusable integrity and membership guard for the public Phase 8A split."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from .subject_split import (
    ALLOCATION_METHOD,
    EXPECTED_CASE_COUNT,
    EXPECTED_SUBJECT_COUNT,
    SOURCE_COHORT_PROTOCOL_VERSION,
    SPLIT_MANIFEST_VERSION,
    SPLIT_SEED,
    STARTING_COMMIT,
    STUDY_PROTOCOL_VERSION,
    TEST_SUBJECT_TARGET,
    TRAIN_SUBJECT_TARGET,
    sorted_identifier_sha256,
)


class SplitGuardError(RuntimeError):
    """Raised for split contamination, unknown IDs, or integrity failures."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def canonical_seal_payload(seal: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in seal.items()
        if key not in {"creation_timestamp_utc", "seal_payload_sha256"}
    }


def seal_payload_sha256(seal: Mapping[str, object]) -> str:
    return hashlib.sha256(_json_bytes(canonical_seal_payload(seal))).hexdigest()


def _normalize_ids(values: Iterable[object], field: str) -> list[str]:
    result = [str(value).strip() for value in values]
    if any(not value or not value.isdecimal() for value in result):
        raise SplitGuardError(f"{field} contains an invalid identifier")
    if len(result) != len(set(result)):
        raise SplitGuardError(f"{field} contains duplicate identifiers")
    return result


class SplitGuard:
    """Verified lookup and contamination checks for one sealed split version."""

    def __init__(
        self,
        subject_rows: list[dict[str, str]],
        case_rows: list[dict[str, str]],
        seal: Mapping[str, object],
    ) -> None:
        self.subject_split = {row["subjectid"]: row["assigned_split"] for row in subject_rows}
        self.case_split = {row["caseid"]: row["assigned_split"] for row in case_rows}
        self.case_subject = {row["caseid"]: row["subjectid"] for row in case_rows}
        self.seal = dict(seal)
        if len(self.subject_split) != len(subject_rows):
            raise SplitGuardError("duplicate subjectid in subject manifest")
        if len(self.case_split) != len(case_rows):
            raise SplitGuardError("duplicate caseid in case manifest")

    @classmethod
    def from_repository(cls, root: Path | str) -> "SplitGuard":
        root = Path(root)
        manifests = root / "data" / "manifests"
        paths = {
            "subject": manifests / "phase8a_subject_split_manifest.csv",
            "case": manifests / "phase8a_case_split_manifest.csv",
            "train_subject": manifests / "phase8a_train_subject_ids.csv",
            "test_subject": manifests / "phase8a_test_subject_ids.csv",
            "train_case": manifests / "phase8a_train_case_ids.csv",
            "test_case": manifests / "phase8a_test_case_ids.csv",
            "stratum": manifests / "phase8a_stratum_allocation.csv",
            "balance": manifests / "phase8a_metadata_balance_table.csv",
            "seal": manifests / "phase8a_test_seal.json",
            "inventory": manifests / "phase8a_artifact_checksums.json",
        }
        missing = [str(path.relative_to(root)) for path in paths.values() if not path.is_file()]
        if missing:
            raise SplitGuardError(f"missing Phase 8A artifacts: {missing}")

        inventory = json.loads(paths["inventory"].read_text(encoding="utf-8"))
        if inventory.get("self_excluded") is not True:
            raise SplitGuardError("artifact inventory must be self-excluded")
        entries = inventory.get("artifacts")
        if not isinstance(entries, list):
            raise SplitGuardError("invalid artifact checksum inventory")
        inventory_paths = set()
        for entry in entries:
            relative = str(entry.get("relative_path", ""))
            path = root / relative
            if not relative or not path.is_file():
                raise SplitGuardError(f"inventory path missing: {relative}")
            if relative in inventory_paths:
                raise SplitGuardError(f"duplicate inventory path: {relative}")
            inventory_paths.add(relative)
            if path.stat().st_size != int(entry.get("bytes", -1)) or _sha256(path) != entry.get("sha256"):
                raise SplitGuardError(f"artifact checksum mismatch: {relative}")
        if "data/manifests/phase8a_artifact_checksums.json" in inventory_paths:
            raise SplitGuardError("artifact inventory cannot include itself")
        if "PHASE_STATUS.md" in inventory_paths:
            raise SplitGuardError("artifact inventory cannot include PHASE_STATUS.md")
        if "data/manifests/phase8a_test_seal.json" not in inventory_paths:
            raise SplitGuardError("artifact inventory does not protect the test seal")

        subject_rows = _read_csv(paths["subject"])
        case_rows = _read_csv(paths["case"])
        seal = json.loads(paths["seal"].read_text(encoding="utf-8"))
        cls._verify_integrity(paths, subject_rows, case_rows, seal)
        return cls(subject_rows, case_rows, seal)

    @staticmethod
    def _verify_integrity(
        paths: Mapping[str, Path],
        subject_rows: list[dict[str, str]],
        case_rows: list[dict[str, str]],
        seal: Mapping[str, object],
    ) -> None:
        expected_constants = {
            "source_remote_commit_sha": STARTING_COMMIT,
            "source_cohort_protocol_version": SOURCE_COHORT_PROTOCOL_VERSION,
            "study_protocol_version": STUDY_PROTOCOL_VERSION,
            "split_manifest_version": SPLIT_MANIFEST_VERSION,
            "split_seed": SPLIT_SEED,
            "allocation_method": ALLOCATION_METHOD,
        }
        for field, expected in expected_constants.items():
            if seal.get(field) != expected:
                raise SplitGuardError(f"test seal {field} mismatch")
        if seal_payload_sha256(seal) != seal.get("seal_payload_sha256"):
            raise SplitGuardError("test seal canonical payload mismatch")
        if len(subject_rows) != EXPECTED_SUBJECT_COUNT or len(case_rows) != EXPECTED_CASE_COUNT:
            raise SplitGuardError("split manifest accounting mismatch")
        subject_counts = {name: sum(row["assigned_split"] == name for row in subject_rows) for name in ("train", "test")}
        if subject_counts != {"train": TRAIN_SUBJECT_TARGET, "test": TEST_SUBJECT_TARGET}:
            raise SplitGuardError("subject split target mismatch")
        if any(row["assigned_split"] not in {"train", "test"} for row in subject_rows + case_rows):
            raise SplitGuardError("invalid assigned_split value")
        if any(
            row.get("source_cohort_protocol_version") != SOURCE_COHORT_PROTOCOL_VERSION
            or row.get("study_protocol_version") != STUDY_PROTOCOL_VERSION
            or row.get("split_manifest_version") != SPLIT_MANIFEST_VERSION
            for row in subject_rows + case_rows
        ):
            raise SplitGuardError("manifest protocol or split version mismatch")

        subject_map = {row["subjectid"]: row["assigned_split"] for row in subject_rows}
        if len(subject_map) != len(subject_rows):
            raise SplitGuardError("duplicate subjectid")
        case_map = {row["caseid"]: row for row in case_rows}
        if len(case_map) != len(case_rows):
            raise SplitGuardError("duplicate caseid")
        for row in case_rows:
            if row["subjectid"] not in subject_map:
                raise SplitGuardError("case has unknown parent subject")
            if row["assigned_split"] != subject_map[row["subjectid"]]:
                raise SplitGuardError("case split differs from parent subject split")

        train_subject_ids = _read_csv(paths["train_subject"])
        test_subject_ids = _read_csv(paths["test_subject"])
        train_case_ids = _read_csv(paths["train_case"])
        test_case_ids = _read_csv(paths["test_case"])
        expected_id_sets = {
            "train_subject": {row["subjectid"] for row in subject_rows if row["assigned_split"] == "train"},
            "test_subject": {row["subjectid"] for row in subject_rows if row["assigned_split"] == "test"},
            "train_case": {row["caseid"] for row in case_rows if row["assigned_split"] == "train"},
            "test_case": {row["caseid"] for row in case_rows if row["assigned_split"] == "test"},
        }
        actual_id_sets = {
            "train_subject": set(_normalize_ids((row["subjectid"] for row in train_subject_ids), "subjectid")),
            "test_subject": set(_normalize_ids((row["subjectid"] for row in test_subject_ids), "subjectid")),
            "train_case": set(_normalize_ids((row["caseid"] for row in train_case_ids), "caseid")),
            "test_case": set(_normalize_ids((row["caseid"] for row in test_case_ids), "caseid")),
        }
        if actual_id_sets != expected_id_sets:
            raise SplitGuardError("ID manifest membership mismatch")
        if actual_id_sets["train_subject"] & actual_id_sets["test_subject"]:
            raise SplitGuardError("subject split overlap")
        if actual_id_sets["train_case"] & actual_id_sets["test_case"]:
            raise SplitGuardError("case split overlap")

        expected_hashes = {
            "sha256_sorted_train_subject_ids": sorted_identifier_sha256(train_subject_ids, "subjectid"),
            "sha256_sorted_test_subject_ids": sorted_identifier_sha256(test_subject_ids, "subjectid"),
            "sha256_sorted_train_case_ids": sorted_identifier_sha256(train_case_ids, "caseid"),
            "sha256_sorted_test_case_ids": sorted_identifier_sha256(test_case_ids, "caseid"),
            "sha256_full_subject_split_manifest": _sha256(paths["subject"]),
            "sha256_full_case_split_manifest": _sha256(paths["case"]),
            "sha256_stratum_allocation": _sha256(paths["stratum"]),
            "sha256_metadata_balance_table": _sha256(paths["balance"]),
        }
        for field, expected in expected_hashes.items():
            if seal.get(field) != expected:
                raise SplitGuardError(f"test seal hash mismatch: {field}")

        required_false = (
            "test_raw_accessed",
            "test_template_created",
            "test_outcome_accessed",
            "ppo_tuned_on_test",
            "ppo_trained",
            "alternate_seed_search_performed",
            "balance_optimized_seed_selection",
        )
        if any(seal.get(field) is not False for field in required_false):
            raise SplitGuardError("test seal records a prohibited action")
        if seal.get("split_generation_count") != 1:
            raise SplitGuardError("split generation count must equal one")
        if seal.get("membership_public") is not True or seal.get("seal_purpose") != "integrity_not_secrecy":
            raise SplitGuardError("test seal publication-purpose mismatch")

    def split_for_subject(self, subjectid: object) -> str:
        key = _normalize_ids([subjectid], "subjectid")[0]
        try:
            return self.subject_split[key]
        except KeyError as error:
            raise SplitGuardError(f"unknown subjectid: {key}") from error

    def split_for_case(self, caseid: object) -> str:
        key = _normalize_ids([caseid], "caseid")[0]
        try:
            return self.case_split[key]
        except KeyError as error:
            raise SplitGuardError(f"unknown caseid: {key}") from error

    def _assert_ids(self, values: Iterable[object], *, field: str, expected_split: str) -> None:
        identifiers = _normalize_ids(values, field)
        lookup = self.subject_split if field == "subjectid" else self.case_split
        unknown = [value for value in identifiers if value not in lookup]
        if unknown:
            raise SplitGuardError(f"unknown {field}: {unknown[0]}")
        observed = {lookup[value] for value in identifiers}
        if observed != {expected_split}:
            raise SplitGuardError(f"{field} request contaminates {expected_split}-only access")

    def assert_train_subjects(self, subjectids: Iterable[object]) -> None:
        self._assert_ids(subjectids, field="subjectid", expected_split="train")

    def assert_test_subjects(self, subjectids: Iterable[object]) -> None:
        self._assert_ids(subjectids, field="subjectid", expected_split="test")

    def assert_train_cases(self, caseids: Iterable[object]) -> None:
        self._assert_ids(caseids, field="caseid", expected_split="train")

    def assert_test_cases(self, caseids: Iterable[object]) -> None:
        self._assert_ids(caseids, field="caseid", expected_split="test")

    def assert_subject_case_request(
        self,
        subjectids: Iterable[object],
        caseids: Iterable[object],
        *,
        expected_split: str,
    ) -> None:
        subjects = _normalize_ids(subjectids, "subjectid")
        cases = _normalize_ids(caseids, "caseid")
        self._assert_ids(subjects, field="subjectid", expected_split=expected_split)
        self._assert_ids(cases, field="caseid", expected_split=expected_split)
        subject_set = set(subjects)
        for caseid in cases:
            if self.case_subject[caseid] not in subject_set:
                raise SplitGuardError("case/subject mixed request mismatch")
