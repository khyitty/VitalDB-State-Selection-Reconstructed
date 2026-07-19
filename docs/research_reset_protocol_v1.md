# 1. Research Reset Protocol v1

## 1.1 문서 상태

* 문서명: `Research Reset Protocol v1`
* 연구 유형: 새로운 환자 코호트(cohort)를 사용하는 확인적 연구(confirmatory study)
* 기존 연구의 지위: 98-case 개발·탐색 연구
* 새 연구 저장소: `khyitty/VitalDB-State-Selection-Reconstructed`
* 원칙: 새 코호트, 새 분할, 새 전처리 통계, 새 후보 상태, 새 PPO 프로토콜을 생성한다.
* 시작 제한: 이 프로토콜과 eligibility audit 기준이 동결되기 전에는 예측 모델 전체 학습이나 PPO 학습을 시작하지 않는다.

## 1.2 연구 질문

### 주 연구 질문

> 전체 VitalDB 6,388개 case를 대상으로 사전에 정한 포함·제외 기준을 적용해 환자 수준 코호트를 구축하고, 30초 후 BIS 예측에 유용한 시뮬레이터 호환 특징(simulator-compatible feature)을 선택한 뒤, 공개된 PK-PD 식으로 재구성한 공통 PPO 환경에서 상태 표현만 변경했을 때 propofol 제어 성능과 안정성이 어떻게 달라지는지 평가한다.

### 하위 질문

1. 현재 BIS를 그대로 미래값으로 사용하는 지속성 기준선(persistence baseline)보다 30초 후 BIS를 더 정확히 예측할 수 있는가?
2. 예측에서 좋은 상태가 PPO 제어에서도 좋은가?
3. BIS history, drug rate, recent dose, cumulative dose, plasma concentration(Cp), effect-site concentration(Ce) 가운데 어떤 정보가 필요한가?
4. 작은 상태가 전체 상태와 비슷한 성능을 내면서 학습 안정성과 행동 부드러움을 개선하는가?
5. 상태 순위가 PK-PD 초기값, reward, action bound 같은 재구성 환경 설정을 바꿔도 유지되는가?

## 1.3 연구 범위

### 포함

* VitalDB 실제 수술 기록을 이용한 30초 후 BIS 예측
* 환자 단위 Elastic Net 안정성 선택(stability selection)
* GRU 기반 후보 상태 검증
* Attention-GRU의 보조적 재현성 분석
* Schnider propofol 및 Minto remifentanil PK 모델
* 공개된 식을 바탕으로 재구성한 PK-PD 시뮬레이터
* 동일 PPO 환경에서 상태 표현 비교
* 환자 수준 통계 분석

### 제외

* 실제 환자 투약 권고
* 임상 안전성 주장
* 교수님 논문의 원 코드 재현
* 교수님 논문과의 직접적인 성능 우월성 비교
* 인과적 특징 발견 주장
* VitalDB 외 병원으로의 일반화 주장
* 실제 임상 controller 개발 주장

## 1.4 원 논문 재현에 대한 공식 입장

교수님 원 코드는 제공되지 않으므로 다음 표현은 사용하지 않는다.

* “원 논문을 정확히 재현했다.”
* “교수님 알고리즘을 그대로 구현했다.”
* “원 논문보다 개선했다.”

사용 가능한 표현은 다음과 같다.

> 공개된 PK-PD 식과 논문에 보고된 설정을 바탕으로 재구성한 비임상 simulation environment에서 상태 표현의 상대적 효과를 비교하였다.

논문에 공개되지 않은 reward, action bounds, 초기화, noise, remifentanil schedule 등은 저장소에서 정의한 설정임을 밝히고, 모든 상태 조건에 동일하게 적용한다.

## 1.5 기존 98-case 연구 처리

기존 98-case는 전체 eligible population에서 추출된 코호트가 아니라, 정렬된 case ID 중 앞의 100개를 다운로드한 뒤 98개가 남은 개발 표본이다. 따라서 해당 코호트에서 나온 prediction, feature selection, internal test, PPO pilot 및 full PPO 결과는 최종 연구 결과로 사용할 수 없다. 

### v1 결정

* 기존 98명은 **새 confirmatory cohort에서 전부 제외한다.**
* train, validation, test 어디에도 넣지 않는다.
* 기존 98명은 코드 통합 및 engineering regression 확인에만 사용할 수 있다.
* 기존 수치와 순위는 새 후보를 결정하는 근거로 사용하지 않는다.
* 기존 test는 이미 확인되었으므로 pristine test로 표현하지 않는다. 기존 저장소 README도 이를 개발용 test로 규정한다.

## 1.6 코호트 설계

### 1차 포함 기준

* 만 18세 이상
* 전신마취
* TIVA(total intravenous anesthesia, 전정맥마취)
* BIS 기록 존재
* propofol infusion rate 기록 존재
* remifentanil infusion rate 기록 존재
* age, sex, height, weight 존재
* 마취 또는 수술 시간축을 확인할 수 있음
* 분석 가능한 연속 신호 구간 존재

### 1차 제외 기준

* 기존 legacy 98 case
* volatile anesthetic 병용이 확인된 case
* propofol 또는 remifentanil rate의 단위를 확인할 수 없는 case
* 약물 rate 기록 누락과 실제 0 투여를 구분할 수 없는 case
* 필수 demographics 결측
* BIS와 약물 시간축 정렬 불가능
* 신호 다운로드 실패
* 정의된 signal-quality 기준 미달
* PK 파라미터 계산이 불가능한 비정상 demographics
* 명확히 식별 가능한 심폐우회술 또는 두개강 내 신경외과 case는 주분석에서 제외하고 별도 기록

### audit 이후 수치로 동결할 항목

다음 기준은 BIS outcome이나 모델 결과를 보지 않고, metadata와 missingness 분포만 확인한 뒤 `Protocol v1.1`에서 확정한다.

* 최소 usable duration
* 최소 BIS coverage
* 최소 drug-rate coverage
* 허용할 최대 연속 missing gap
* case당 최소 prediction window 수
* forward fill 허용 길이
* Cp/Ce burn-in 시간

즉, 품질 기준은 audit 결과를 이용해 정할 수 있지만, 미래 BIS 예측 성능을 본 뒤 유리하게 바꿀 수는 없다.

## 1.7 Feature universe

### 동적 특징

1. BIS
2. 10초 BIS 변화량
3. Propofol 현재 rate
4. Propofol recent dose
5. Propofol cumulative dose
6. Propofol Cp
7. Propofol Ce
8. Remifentanil 현재 rate
9. Remifentanil recent dose
10. Remifentanil cumulative dose
11. Remifentanil Cp
12. Remifentanil Ce

### 정적 특징

* age
* sex
* height
* weight

`BIS - 50`인 target error는 BIS와 완전히 중복되는 선형 변환이므로 prediction feature selection에는 포함하지 않는다. 다만 고정 목표 BIS를 알려 주는 제어 입력으로 사용할 경우에는 baseline state의 명시적 파생 변수로만 취급한다.

HR, blood pressure, SpO₂, ETCO₂, HRV, BIS SQI 등을 제외하는 이유는 예측력이 없어서가 아니라, 현재 PK-PD 시뮬레이터가 action에 따라 이 신호를 생성하지 못하기 때문이다.

## 1.8 환자 분할 및 test 정책

* 최종 eligible cohort가 완성된 뒤 분할한다.
* 가능하면 환자 ID 단위로 분할한다.
* 환자 ID가 없으면 case ID 단위로 분할하고, 같은 환자의 반복 수술이 섞일 수 있다는 한계를 보고한다.
* 기본 비율: train 70%, validation 15%, test 15%
* 층화(stratification)는 age group, sex, BMI, ASA, operation category 등 metadata만 사용한다.
* window를 만든 뒤 나누지 않는다.
* 각 환자의 모든 window는 하나의 split에만 속한다.
* test case ID와 target은 최종 후보와 분석법을 동결할 때까지 봉인한다.

기존 코드도 환자를 먼저 나누고 그 뒤 window를 생성하는 구조를 사용했으며, 10초 간격, 60초 history, t+30 target을 정의했다. 이 구조적 원칙은 재사용할 수 있지만 기존 split 자체는 재사용하지 않는다.

## 1.9 Prediction protocol

### 입력과 target

* resampling interval: 10초
* history: 60초
* 입력 시점: `t-50, t-40, t-30, t-20, t-10, t`
* target: `t+30`의 raw BIS
* split 후 각 case별로 독립적인 window 생성
* imputation과 normalization은 train에서만 적합

### 비교 모델

1. Persistence baseline
2. Elastic Net
3. GRU
4. Attention-GRU

### 평가 지표

주지표:

* 환자별 MAE를 계산한 뒤 환자에게 동일 가중치를 주는 patient-level MAE

보조 지표:

* patient-level RMSE
* pooled MAE
* pooled RMSE
* out-of-sample (R^2)
* 환자별 MAE 분포
* induction·maintenance·recovery 단계별 성능
* BIS 급변 구간 성능

window 수가 많은 환자가 결과를 지배하지 않도록 pooled metric만으로 결론을 내리지 않는다.

## 1.10 Feature-selection protocol

### 주 방법

환자 수준 Elastic Net 안정성 선택(patient-level Elastic Net stability selection)

### 규칙

* train 환자만 사용한다.
* 환자를 재표집(resampling)하고, window를 개별 독립 표본처럼 bootstrap하지 않는다.
* 내부 교차검증도 환자 그룹을 보존한다.
* 각 feature group의 선택 빈도와 계수 방향을 기록한다.
* validation과 test는 stability selection에 사용하지 않는다.
* Attention weight는 primary selector로 사용하지 않는다.
* 선택 빈도가 높다는 사실과 특징 수가 적다는 사실을 구분한다.

기존 저장소도 train-only Elastic Net을 primary selector로 두고, Attention을 보조 분석으로 제한했다.

### 선택 실패 기준

다음 중 하나면 “희소하고 안정적인 특징 선택에 실패했다”고 보고한다.

* 대부분의 feature가 비슷한 빈도로 선택됨
* seed 또는 patient resampling에 따라 선택 집합이 크게 변함
* validation에서 작은 후보가 full state보다 일관되게 나쁘게 나타남
* 임의 threshold를 사용해야만 원하는 개수의 feature가 나옴

이 경우 임의로 feature 수를 줄여 `selected`라고 부르지 않는다.

## 1.11 PPO 후보 상태

사전에 다음 네 후보를 정의한다.

| 상태                          | 역할                                            |
| --------------------------- | --------------------------------------------- |
| `original_reconstructed_v1` | 공개된 논문에서 확인할 수 있는 개념을 재구성한 기준선                |
| `all_supported_v1`          | simulator-compatible 동적 특징 12개 전체             |
| `bis_history_v1`            | BIS와 BIS 변화량만 사용하는 구조적 최소 기준선                 |
| `selected_v1`               | 새 train cohort에서 정한 feature-selection 규칙으로 생성 |

기존 `selected_control_core`는 새 데이터에서 선택된 상태가 아니므로 가져오지 않는다.

### 최종 control candidate 결정

* PPO validation 결과만 사용한다.
* primary metric은 validation patient-level BIS target MAE다.
* 성능이 가장 좋은 상태와 통계적으로 구분하기 어려운 상태가 여러 개면, 가장 작은 상태를 선택하는 1-standard-error rule을 사용한다.
* numerical failure, 극단적 saturation 또는 비정상 action clipping이 있는 상태는 MAE가 낮더라도 선택하지 않는다.
* 최종 test를 열기 전에 하나의 primary candidate를 확정한다.

## 1.12 PPO 공통 프로토콜

상태 외 다음 항목을 모두 동일하게 유지한다.

* PK-PD simulator
* patient demographics
* remifentanil schedule
* initial state
* episode length
* action space
* action interval
* reward
* policy architecture
* optimizer
* PPO hyperparameters
* training budget
* seed
* evaluation patient
* validation interval
* checkpoint rule

### 실행 순서

1. PK-PD unit test
2. Gymnasium environment test
3. random-action rollout
4. 모든 profile에 대한 공통-policy smoke test
5. 1-seed engineering run
6. 소규모 multi-seed pilot
7. pilot audit
8. protocol 및 hash 동결
9. full multi-seed training
10. validation 분석
11. final candidate 동결
12. test one-time evaluation

Pilot은 오류, runtime, saturation, checkpoint 저장을 확인하기 위한 것이며 winner를 확정하는 실험이 아니다.

## 1.13 PPO 평가 지표

주지표:

* BIS target MAE

보조 지표:

* BIS target RMSE
* integrated absolute BIS error
* BIS 40–60 시간 비율
* BIS >60, <40, <30 시간 비율
* induction settling time
* total return
* total propofol dose
* mean/max infusion rate
* action clipping
* lower/upper saturation
* mean absolute action change
* action smoothness
* oscillation
* numerical failure
* 학습 속도와 sample efficiency
* seed 간 변동성

한 상태가 MAE는 좋지만 action smoothness가 나쁘면 한쪽 결과를 숨기지 않고 trade-off로 보고한다.

## 1.14 통계 분석

독립 분석 단위는 환자다.

### 주 비교

* `selected_v1` 대 `original_reconstructed_v1`

### 보조 비교

* `all_supported_v1` 대 original
* `bis_history_v1` 대 original
* selected 대 all-supported

### 방법

* 동일 환자·동일 scenario에서 paired difference 계산
* seed별 paired result 저장
* 환자를 재표집하고 seed 구조를 유지하는 계층적 bootstrap(hierarchical bootstrap)
* 95% confidence interval
* effect size
* 환자별 개선·악화 비율
* seed win count
* learning curve 평균과 변동성

`환자 × seed` 행을 모두 독립 환자로 취급하지 않는다. 여러 지표에 기계적으로 p-value를 반복 계산하지 않는다.

## 1.15 Sensitivity analysis

주분석을 바꾸지 않고 다음 조건에서 상태 순위가 유지되는지 확인한다.

1. Cp/Ce 초기값 0 대 burn-in 적용
2. burn-in 시간 변화
3. rate gap을 missing으로 처리하는 경우와 제한적 hold 처리
4. action bound 변화
5. reward scaling 변화
6. remifentanil schedule 변화
7. volatile-agent exclusion 정의 변화
8. history 60초 대 120초
9. BIS quality threshold 변화

Sensitivity 결과를 이용해 주분석 protocol을 다시 바꾸지는 않는다.

## 1.16 Test seal

Test를 열기 전에 다음을 동결한다.

* 코호트와 split
* feature order
* scaler와 imputation
* 모델 architecture
* candidate state
* PPO protocol
* seed
* checkpoint rule
* primary metric
* 통계 분석법
* exclusion handling

Test 결과를 확인한 뒤 feature, reward, seed, checkpoint 또는 subgroup 기준을 변경하지 않는다.

## 1.17 중단 규칙

다음 상황에서는 full experiment를 중단한다.

* train·validation·test 환자 중복
* 기존 98 case 유입
* test target 또는 plot 조기 접근
* case 누락 또는 download failure가 기록되지 않음
* rate unit을 확인하지 못함
* Cp/Ce reconstruction 검증 실패
* 상태별 reward, action 또는 PPO 설정이 다름
* 수치적 실패가 반복됨
* validation 결과를 본 뒤 eligibility 기준이 변경됨
* feature selection이 실패했는데 임의 후보를 selected로 지정하려 함

## 1.18 허용 가능한 주장

* 새 코호트에서 특정 상태가 비교 환경 내에서 더 낮은 BIS MAE를 보였다.
* 작은 상태와 전체 상태 사이에 예측·제어 trade-off가 관찰되었다.
* 공개된 식으로 재구성한 환경에서 상태 표현에 따른 차이가 나타났다.
* 결과는 비임상 simulation 결과다.

허용되지 않는 주장:

* 실제 환자에게 안전하다.
* 임상 투약에 사용할 수 있다.
* 특정 feature가 BIS를 인과적으로 변화시킨다.
* 원 논문보다 우수하다.
* 모든 환자와 병원에서 최적이다.

---

