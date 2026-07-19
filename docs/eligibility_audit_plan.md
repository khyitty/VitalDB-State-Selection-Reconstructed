# 3. 전체 VitalDB Eligibility Audit 실행 계획

## 3.1 목적

전체 6,388 case에 동일한 기준을 적용해 다음을 확인한다.

* 어떤 case가 연구 질문에 적합한가?
* 필수 metadata와 track이 있는가?
* 실제 signal을 사용할 수 있는가?
* 제외된 case가 왜 제외되었는가?
* 최종 코호트가 어떤 모집단을 대표하는가?

어떤 단계에서도 정렬된 앞부분, `head()`, `[:100]`, `N_CASES` 제한을 사용하지 않는다.

## 3.2 Audit configuration

`configs/eligibility_audit.yaml`

```yaml
audit_name: vitaldb_full_eligibility_v1
expected_case_range:
  start: 1
  end: 6388

production_mode: true
allow_case_limit: false
allow_first_n: false
exclude_legacy_98: true

required_demographics:
  - age
  - sex
  - height
  - weight

required_primary_tracks:
  - bis
  - propofol_rate
  - remifentanil_rate

primary_population:
  adult_only: true
  general_anesthesia_only: true
  tiva_only: true
  exclude_volatile_agent_exposure: true
```

## 3.3 Phase 0 — Code-level first-N 방지

production audit 시작 전에 다음 guard가 반드시 통과해야 한다.

* case ID 전체 개수 검증
* 최소 ID와 최대 ID 검증
* 중복 ID 0
* 정렬 후 SHA-256 fingerprint 생성
* `max_cases`, `N_CASES`, `pilot`, `head`, `first_n` 설정 감지 시 즉시 실패
* 다운로드 완료 수가 candidate 수보다 작으면 completion 처리 금지
* manifest에 없는 case를 조용히 버리는 코드 금지

권장 test:

```text
test_full_case_range_is_present
test_no_case_limit_in_production
test_no_first_n_slice
test_duplicate_caseids_are_rejected
test_missing_case_requires_failure_record
```

## 3.4 Phase 1 — Clinical metadata와 track inventory

전체 case에 대해 signal을 다운로드하기 전에 가벼운 inventory를 수행한다.

### 생성 파일

`data/manifests/all_case_eligibility_manifest.csv`

### 필수 column

#### 식별 및 source

* `caseid`
* `source_query_timestamp`
* `vitaldb_library_version`
* `clinical_metadata_available`
* `track_inventory_available`

#### Demographics

* `age`
* `age_available`
* `sex`
* `sex_available`
* `height`
* `height_available`
* `weight`
* `weight_available`
* `bmi`
* `asa`

#### 수술 정보

* `anesthesia_type`
* `operation_type`
* `emergency_status`
* `anesthesia_start`
* `anesthesia_end`
* `operation_start`
* `operation_end`

#### Track 존재 여부

* `bis_track_available`
* `bis_sqi_track_available`
* `propofol_rate_track_available`
* `propofol_volume_track_available`
* `remifentanil_rate_track_available`
* `remifentanil_volume_track_available`
* `device_propofol_cp_available`
* `device_propofol_ce_available`
* `device_remifentanil_cp_available`
* `device_remifentanil_ce_available`
* `volatile_agent_track_available`

#### 1차 판단

* `legacy_98_case`
* `adult_candidate`
* `tiva_candidate`
* `volatile_exposure_possible`
* `candidate_at_metadata_stage`
* `metadata_exclusion_flags`

제외 사유는 하나의 문자열로 덮지 않고 복수 flag로 저장한다.

## 3.5 Track alias 관리

VitalDB 장비 및 기록 방식에 따라 같은 의미의 track 이름이 다를 수 있으므로 alias를 코드에 흩어 두지 않는다.

`configs/track_aliases.yaml`

```yaml
bis:
  - BIS/BIS

propofol_rate:
  - Orchestra/PPF20_RATE
  - known_validated_aliases

remifentanil_rate:
  - Orchestra/RFTN20_RATE
  - known_validated_aliases
```

실제 inventory에서 발견한 새로운 alias는 자동 채택하지 않는다. 단위와 의미를 확인한 뒤 versioned configuration에 추가한다.

## 3.6 Phase 2 — Metadata-stage 후보 생성

1차 candidate가 되려면 다음을 만족해야 한다.

* legacy 98이 아님
* 성인
* TIVA로 분류 가능
* volatile agent 병용이 확인되지 않음
* 필수 demographics 존재
* BIS track 존재
* propofol rate track 존재
* remifentanil rate track 존재
* 시간 범위 확인 가능

Remifentanil track이 없을 때 이를 “0을 투여했다”고 해석하지 않는다. 기록 부재와 실제 무투여를 구분할 수 없으므로 primary cohort에서는 제외한다.

## 3.7 Phase 3 — Signal download

Metadata-stage candidate 전부를 다운로드한다.

### 저장 구조

```text
data/raw/cases/{caseid}/
  clinical.json
  track_inventory.json
  bis.parquet
  propofol_rate.parquet
  remifentanil_rate.parquet
  optional_tracks/
  source_metadata.json
```

### 원칙

* raw 파일은 수정하지 않는다.
* 다운로드 후 checksum을 저장한다.
* case별 상태를 기록한다.
* 실패한 case는 제외하지 않고 `failed` 상태로 남긴다.
* 재실행 시 완료 case는 checksum을 확인한 뒤 건너뛴다.
* 다운로드 순서가 cohort 선택에 영향을 주지 않는다.

### Download manifest

`data/manifests/download_manifest.csv`

* `caseid`
* `status`
* `attempt_count`
* `started_at`
* `completed_at`
* `tracks_requested`
* `tracks_downloaded`
* `bytes_downloaded`
* `checksum`
* `failure_type`
* `failure_message`
* `retryable`
* `library_version`

### 재시도 규칙

* 네트워크/API 오류: 최대 3회 재시도
* track 없음: 재시도하지 않고 명시적 실패
* parsing 오류: 원본 응답과 traceback 보존
* 세 번 실패한 case도 manifest에서 삭제하지 않음

## 3.8 Phase 4 — Signal-level quality audit

각 case에 같은 검사를 적용한다.

### BIS 검사

* 값이 0–100 범위 안인지
* timestamp가 단조 증가하는지
* 중복 timestamp
* sampling gap
* 전체 coverage
* propofol 투여 구간 내 coverage
* 최대 연속 missing gap
* BIS 0 구간
* 급격한 discontinuity
* SQI가 있을 경우 BIS와의 정렬

BIS 0은 자동 삭제하지 않고 warning flag로 남긴다. BIS 0은 실제 깊은 억제일 수도 있고 artifact일 수도 있기 때문이다.

### Drug-rate 검사

* 음수값
* 비수치값
* 단위 확인
* timestamp 정렬
* missing과 0 구분
* rate 변화 빈도
* 비정상적으로 큰 값
* volume track과의 누적 일관성
* device restart 가능성
* case 시작 이전 투약 가능성

단위를 확인하기 전에 임의 최대 rate로 outlier를 삭제하지 않는다.

### Alignment 검사

* BIS와 drug-rate 시간축 중첩
* 마취 시작·종료 시간과 signal의 일치
* propofol 시작·종료 구간
* 분석 가능한 연속 구간
* 60초 history와 30초 future target 생성 가능성

### 생성 파일

`data/manifests/signal_quality_manifest.csv`

* `caseid`
* `download_complete`
* `bis_coverage`
* `propofol_rate_coverage`
* `remifentanil_rate_coverage`
* `max_bis_gap_seconds`
* `max_propofol_gap_seconds`
* `max_remifentanil_gap_seconds`
* `usable_seconds`
* `potential_window_count`
* `rate_unit_valid`
* `time_alignment_valid`
* `cpce_reconstructable`
* `warning_flags`
* `exclusion_flags`
* `eligible_signal_stage`

## 3.9 Phase 5 — Outcome-blind 품질 기준 동결

Metadata와 coverage distribution까지만 확인하고 다음을 확정한다.

* minimum usable duration
* minimum coverage
* maximum gap
* permitted interpolation/forward-fill
* case당 minimum windows
* burn-in period

이 단계에서는 다음을 보지 않는다.

* t+30 BIS 분포
* persistence MAE
* 모델 성능
* feature coefficient
* candidate ranking

결정 후 `eligibility_audit.yaml`의 version을 올리고 hash를 생성한다. 그 뒤 기준을 바꾸려면 protocol deviation으로 기록해야 한다.

## 3.10 Phase 6 — Cp/Ce reconstruction audit

### 기본 방법

* Propofol: Schnider PK model
* Remifentanil: Minto PK model
* exact zero-order-hold matrix exponential
* 내부 시간 간격 1초
* 과거 rate만 사용하는 causal reconstruction

### 검증

* 일정 rate infusion synthetic test
* bolus 또는 step-change test
* exact ZOH와 `solve_ivp` 비교
* concentration non-negativity
* mass 및 unit consistency
* demographic boundary test
* missing-rate sensitivity
* 초기 state 0 sensitivity
* burn-in sensitivity

Device-reported Cp/Ce는 필수 track이나 정답으로 사용하지 않는다. Train split에서만 reconstructed 값과 descriptive comparison을 수행한다.

## 3.11 Phase 7 — Final cohort freeze

최종 manifest:

`data/manifests/final_confirmatory_cohort.csv`

* `caseid`
* `eligible`
* 모든 exclusion flag
* `usable_seconds`
* `usable_windows`
* `cohort_version`
* `audit_config_hash`
* `source_manifest_hash`
* `raw_checksum`
* `legacy_overlap`
* `final_split`

별도 파일:

* `exclusion_flow.csv`
* `exclusion_reason_counts.csv`
* `cohort_characteristics.csv`
* `cohort_fingerprint.json`
* `audit_completion_report.md`

모든 숫자는 실제 audit 결과가 나온 뒤 작성한다.

## 3.12 Phase 8 — Patient-level split

* 최종 cohort freeze 후 실행
* old 98 overlap 0 확인
* 고정 seed
* train 70%, validation 15%, test 15%
* metadata 기반 층화
* split overlap 0
* split manifest와 fingerprint 저장

Test split 생성 후 다음 기능을 차단한다.

* test target summary
* test plot
* test inference
* feature ranking
* manual inspection
* test patient별 outcome 출력

## 3.13 Dry run 계획

Dry run은 production cohort를 제한하는 것이 아니라 코드가 작동하는지 확인하기 위한 별도 engineering 절차다. `first N`은 사용하지 않고 고정 seed로 무작위 추출한다.

### Dry run 1 — Synthetic

* API 없음
* manifest schema
* resume
* failure log
* guard test

### Dry run 2 — Metadata-only 25 cases

* 전체 inventory에서 고정 seed 무작위 표본
* first-25 금지
* metadata parsing 및 alias 확인

### Dry run 3 — Signal 25 cases

* BIS·rate 다운로드
* 파일 크기
* 다운로드 시간
* failure pattern
* signal quality runtime 측정

### Dry run 4 — 100-case 무작위 integration

* legacy first-100과 다른 무작위 표본
* end-to-end audit만 수행
* prediction model 학습 금지
* scientific 결과로 사용 금지

### Production

* 전체 metadata audit
* metadata candidate 전부 signal download
* full signal-quality audit
* final cohort freeze

## 3.14 예상 시간과 저장 공간

현재는 candidate 수, track 해상도, 다운로드 실패율, API 속도를 확인하지 않았으므로 신뢰할 수 있는 숫자를 제시할 수 없다.

25-case 및 100-case 무작위 dry run 후 다음 방식으로 산출한다.

### 저장 공간

[
\text{Expected storage}
=======================

N_{\text{candidate}}
\times
\text{median bytes per case}
]

보수적 예약 공간:

[
\text{Reserved storage}
=======================

N_{\text{candidate}}
\times
P_{90}(\text{bytes per case})
\times 1.2
]

### 실행 시간

[
\text{Expected wall time}
=========================

\frac{N_{\text{candidate}}
\times
\text{median seconds per case}}
{\text{concurrent workers}}
]

보고할 값:

* median case download time
* 90th percentile download time
* median bytes per case
* 90th percentile bytes per case
* failure and retry rate
* signal-quality processing time
* 예상 전체 시간 범위
* 필요 저장 공간 범위

실측 없이 과거 100-case runtime을 전체 audit 예상 시간으로 선형 확장하지 않는다.

## 3.15 Audit 완료 조건

다음이 모두 충족되어야 한다.

* 6,388개 case가 metadata manifest에 존재
* 중복 case 0
* 누락 case 0 또는 누락 사유 명시
* candidate 전부 download manifest에 존재
* 모든 실패 case에 사유가 있음
* first-N guard 통과
* old 98 overlap flag 생성
* quality criteria hash 생성
* final cohort manifest 생성
* exclusion flow와 이유별 수가 일치
* cohort fingerprint 생성
* split 전에 cohort가 동결됨
* test seal 활성화
* full model 및 PPO 실행 이력 없음

이 세 문서는 기존 98-case 결과를 최종 결과로 전환하지 않고, 새 연구가 어떤 절차로 처음부터 다시 구축되는지를 정의한다. 원본 인수인계 문서가 요구한 “full model보다 먼저 protocol·migration·eligibility audit을 작성한다”는 순서를 따른 것이다.

