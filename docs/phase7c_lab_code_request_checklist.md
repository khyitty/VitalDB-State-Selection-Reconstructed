# Phase 7C Laboratory Code Request Checklist

| Item | Status | Evidence or request |
|---|---|---|
| Executable PPO training code | partially_available | Legacy SB3 wrapper and smoke entry exist; request the laboratory's actual runnable package and commit SHA. |
| Executable evaluation code | partially_available | Legacy validation evaluator is checkpoint/cohort-coupled; request the exact evaluation entry point. |
| Patient simulator | already_available | Legacy synthetic reset/advance passed; request the laboratory-authoritative simulator version. |
| PK-PD equations implementation | partially_available | Executable legacy Schnider/Minto/Yun candidates exist; request equation provenance and validation suite. |
| Reward coefficients | missing_request_from_lab | Request the exact equation, coefficients, timing, and safety termination treatment. |
| Action definition and units | partially_available | Legacy source uses propofol mg/min every 10 seconds; request authoritative command semantics. |
| Action bounds | missing_request_from_lab | Legacy paper conversion and synthetic bounds are not an approved study contract. |
| PPO hyperparameters | partially_available | Legacy candidates exist; request exact authoritative values and provenance. |
| Training budget | missing_request_from_lab | Request total steps, rollouts, epochs, seeds, stopping rules, and compute target. |
| Patient sampling method | missing_request_from_lab | Request episode patient selection and repeated-patient handling; no split exists yet. |
| Remifentanil schedule | missing_request_from_lab | Request generation/source, units, timing, and whether it is visible to the controller. |
| Termination conditions | partially_available | Legacy fixed horizon exists; request safety and numerical termination rules. |
| State normalization rules | missing_request_from_lab | Request immutable transforms and whether they are fit or fixed. |
| Original environment dependencies | partially_available | Legacy requirements omit Stable-Baselines3 and lack a lock. Request lockfile/container. |
| Expected Python/package versions | missing_request_from_lab | Request exact Python, NumPy, SciPy, Gymnasium, SB3, PyTorch versions. |
| Example command | already_available | Legacy synthetic smoke command exists but is not authorized for this phase. |
| Example config | partially_available | Legacy JSON exists but is a prohibited frozen artifact; request a clean authoritative example. |
| Expected input/output files | missing_request_from_lab | Request schemas, directory contract, checkpoint format, and evaluation artifacts. |

Preferred delivery: a clean repository or archive with source commit SHA, environment lock, license/reuse permission, one synthetic config, and a command that performs a checkpoint-free reset/step/forward probe before any training.
