# 연구실 코드 요청문 초안

교수님, 현재 연구에서는 기존 PPO와 환자 simulator를 새로 구현하기보다 연구실에서 사용한 실행 코드를 최대한 그대로 재사용하려고 합니다. 가능하시다면 아래 자료를 부탁드립니다.

- PPO 학습 및 평가 실행 코드와 기준 commit/version
- requirements, environment 파일 또는 container 설정
- Python, Gymnasium, Stable-Baselines3 등 정확한 package version
- patient simulator와 PK-PD 식·단위 설명
- reward 식과 계수
- propofol action의 정의, 단위, 범위
- PPO hyperparameter와 총 학습 step
- patient sampling 및 remifentanil schedule 규칙
- 종료 조건, checkpoint 형식, example config·command, 예상 output
- 기존 state schema와 normalization 규칙

실제 환자 데이터나 기존 checkpoint·결과 파일은 필요하지 않습니다. 우선 synthetic input으로 reset/step과 forward pass만 확인할 수 있는 최소 실행 package를 주시면, 승인된 Protocol v1.3.1 observation layer와 S0/S1 adapter만 별도로 연결하겠습니다.
