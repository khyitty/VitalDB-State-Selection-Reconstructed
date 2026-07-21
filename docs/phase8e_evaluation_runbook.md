# Phase 8E Evaluation Runbook

First run the test-input verifier. It checks both private stores, Phase 8B/8C roots, partial paths, and Shard A metadata without loading a model:

```powershell
$env:PYTHONPATH='src'
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8e_test_inputs.py --stage verify-only
```

After all four final-condition directories are locally available, use the evaluation runner in its safe default mode:

```powershell
.\.venv-phase7h\Scripts\python.exe scripts\run_phase8e_final_evaluation.py --models-root data/processed/phase8d_final_training_v1 --test-runtime-root data/processed/phase8e_test_runtime_inputs_v1 --expected-training-sha b782b5e4a9d418f6b907a87d046c4e9789a3e5f0 --seed 42 --verify-only
```

The command must refuse execution while either Shard B model is absent. Actual episodes require a later, explicit `--execute --output-root data/processed/phase8e_evaluation_outputs_v1` authorization. Phase 8E readiness does not grant that authorization.
