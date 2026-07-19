# 2. 새 Repository Migration Plan

## 2.1 두 저장소의 역할

### 기존 저장소

`khyitty/VitalDB-Feature-Selection`

역할:

* 98-case development 및 pilot archive
* 과거 prediction, feature selection, PPO 결과 보존
* engineering 구현의 source provenance
* 삭제·history rewrite 금지

### 새 저장소

`khyitty/VitalDB-State-Selection-Reconstructed`

역할:

* 전체 VitalDB eligibility audit
* 새로운 confirmatory cohort
* 새로운 split과 test
* 독립적으로 검증된 재사용 코드
* 새 prediction 및 PPO 프로토콜
* 최종 연구 산출물

## 2.2 기존 저장소 archive 처리

기존 저장소에는 다음 안내를 추가한다.

> This repository contains exploratory development based on a non-random first-100-case sample that yielded 98 usable cases. Its prediction and PPO results are not confirmatory full-cohort results. The test split was inspected during development, and the PK-PD/RL environment is a reconstruction from published information rather than an exact reproduction of the unpublished original implementation.

권장 tag:

```text
legacy-98case-development-final
```

기존 branch나 commit을 삭제하지 않는다.

## 2.3 코드 이전 분류

### A. 이전 가능하지만 반드시 독립 검증할 코드

* Schnider propofol PK equation
* Minto remifentanil PK equation
* combined BIS PD equation
* exact zero-order-hold transition
* `solve_ivp` 비교 검증
* unit conversion 함수
* Gymnasium wrapper 구조
* state adapter interface
* PPO training loop
* checkpoint save/load/resume
* run status 및 failure logging
* artifact hash 및 inventory
* patient-level split guard
* train-only preprocessing 함수
* Elastic Net 구현
* patient-level stability-selection 구현
* GRU 및 Attention-GRU architecture
* patient-level bootstrap
* test-access guard
* synthetic unit test

기존 README가 기록한 PK-PD simulator는 exact ZOH와 1초 내부 integration을 사용하며, 공개식으로 재구성된 비임상 simulator로 정의되어 있다. 이 구현은 이전할 수 있지만 새 저장소에서 다시 검증해야 한다.

### B. 재작성해야 하는 코드

* 전체 case eligibility 조회
* track inventory
* clinical metadata 병합
* case 다운로드 orchestration
* signal quality filtering
* cohort manifest 생성
* split 생성
* raw-to-modeling dataset pipeline
* test sealing
* volatile-agent 판별
* track alias resolution

특히 기존 `main.py`의 first-100 제한과 기존 required-track 조건은 그대로 가져오면 안 된다.

### C. 절대 이전하지 않을 데이터 의존 artifact

* 기존 98 case ID
* 기존 split CSV
* 기존 train/validation/test NPZ
* 기존 scaler
* 기존 imputation statistics
* 기존 Cp/Ce trajectory
* 기존 feature ranking
* 기존 selection frequency
* 기존 candidate manifest
* 기존 `selected_control_core`
* 기존 PPO protocol hash
* 기존 cohort fingerprint
* 기존 checkpoint
* 기존 metric CSV
* 기존 figure
* 기존 test prediction
* 기존 backend decision
* 기존 full PPO run output

## 2.4 권장 directory structure

```text
VitalDB-State-Selection-Reconstructed/
├─ README.md
├─ LICENSE
├─ pyproject.toml
├─ requirements.txt
├─ .gitignore
│
├─ configs/
│  ├─ eligibility_audit.yaml
│  ├─ prediction_protocol.yaml
│  ├─ feature_selection.yaml
│  ├─ pkpd_protocol.yaml
│  └─ ppo_protocol.yaml
│
├─ docs/
│  ├─ research_reset_protocol_v1.md
│  ├─ repository_migration_plan.md
│  ├─ eligibility_audit_plan.md
│  ├─ legacy_98case_statement.md
│  ├─ claim_boundary.md
│  ├─ pkpd_equation_traceability.md
│  └─ protocol_deviations.md
│
├─ src/
│  └─ vitaldb_state_selection/
│     ├─ cohort/
│     │  ├─ clinical_metadata.py
│     │  ├─ track_inventory.py
│     │  ├─ eligibility.py
│     │  ├─ signal_quality.py
│     │  └─ splitting.py
│     ├─ data/
│     │  ├─ downloader.py
│     │  ├─ track_aliases.py
│     │  ├─ resampling.py
│     │  └─ windows.py
│     ├─ pkpd/
│     ├─ prediction/
│     ├─ selection/
│     ├─ rl/
│     ├─ statistics/
│     └─ provenance/
│
├─ scripts/
│  ├─ run_metadata_audit.py
│  ├─ download_candidate_signals.py
│  ├─ run_signal_quality_audit.py
│  ├─ freeze_confirmatory_cohort.py
│  └─ verify_no_first_n_limit.py
│
├─ schemas/
│  ├─ eligibility_manifest.schema.json
│  ├─ download_manifest.schema.json
│  └─ signal_quality_manifest.schema.json
│
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ synthetic/
│  └─ guards/
│
├─ data/
│  ├─ raw/
│  ├─ manifests/
│  ├─ interim/
│  ├─ processed/
│  └─ modeling/
│
└─ outputs/
```

`data/raw`, modeling arrays, checkpoint 및 대형 output은 Git에 commit하지 않는다. Manifest, schema, protocol, small summary와 checksum은 commit한다.

## 2.5 Provenance 기록

모든 이전 파일에 대해 다음 표를 유지한다.

`docs/migration_provenance.csv`

| column                | 의미                          |
| --------------------- | --------------------------- |
| target_path           | 새 저장소 경로                    |
| source_repository     | 기존 저장소                      |
| source_path           | 기존 파일 경로                    |
| source_commit_sha     | 가져온 정확한 commit              |
| migration_type        | copy / refactor / rewrite   |
| scientific_dependency | 데이터 의존 여부                   |
| required_tests        | 통과해야 할 test                 |
| audit_status          | pending / passed / rejected |
| migration_date        | 이전 날짜                       |
| notes                 | 변경 내용                       |

이전 코드의 주석이나 문서에 source commit SHA를 남긴다. 새 저장소에 기존 Git history를 합치는 방식은 사용하지 않는다.

## 2.6 Test 정책

### 이전 승인 조건

코드는 다음을 모두 통과해야 새 연구에 사용할 수 있다.

* synthetic input unit test
* unit consistency test
* missing-value behavior test
* deterministic seed test
* patient leakage test
* test-access guard
* exact ZOH 대 `solve_ivp`
* non-negativity 및 finite-value test
* 동일 state에서 기존 환경과 새로운 환경의 transition 비교
* 상태 profile을 바꿔도 underlying transition과 reward가 동일한지 확인

### 금지되는 test

* 기존 98-case metric을 정답으로 고정하는 test
* 기존 feature ranking을 재현해야 통과하는 test
* 기존 PPO checkpoint와 동일 output을 요구하는 test

## 2.7 Commit 순서

### Commit 1 — 연구 규칙과 빈 구조

```text
Initialize confirmatory study governance
```

포함:

* README
* Research Reset Protocol v1
* Migration Plan
* Eligibility Audit Plan
* legacy statement
* claim boundary
* directory skeleton
* `.gitignore`
* manifest schema 초안

### Commit 2 — 전체 eligibility audit

```text
Add full VitalDB eligibility audit framework
```

포함:

* metadata 조회
* track inventory
* first-N 방지 guard
* manifest 생성
* resume 및 failure log
* audit test

### Commit 3 — signal download 및 quality audit

```text
Add resumable signal download and quality audit
```

### Commit 4 — PK-PD 코드 이전

```text
Migrate and revalidate reconstructed PK-PD modules
```

### Commit 5 — prediction 및 feature selection

```text
Add confirmatory prediction and selection pipeline
```

### Commit 6 — RL environment와 PPO

```text
Add state-controlled PPO comparison framework
```

### Commit 7 — end-to-end smoke

```text
Validate confirmatory pipeline integration
```

full model 또는 full PPO는 Commit 7의 검증과 protocol freeze 이후에만 실행한다.

---

