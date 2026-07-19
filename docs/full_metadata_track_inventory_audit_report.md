# Phase 5A Full Metadata and Track Inventory Audit

## Interpretation boundary

This is an outcome-blind source and metadata inventory, not an eligibility
decision or scientific result. Only the VitalDB `/cases` and `/trks` endpoints
were queried. No raw time-series signal was downloaded.

Legacy 98-case IDs were not read, extracted, copied, or compared. Legacy overlap,
TIVA classification, volatile exposure, drug-rate units, quality thresholds, and
final eligibility remain pending human review.

## Source snapshots

| Endpoint | Status | Rows | Bytes | SHA-256 |
|---|---:|---:|---:|---|
| `/cases` | complete | 6388 | 2199564 | `d74684b4794b5095c32ca607ab5d6b1f8d04f888a607f4fd48470c8ffe885a0b` |
| `/trks` | complete | 486449 | 30565770 | `82b31333be20ca912ded93f46bf3ae42db281da40515a9945acc57749da9ffd0` |

## Complete case accounting

| Measure | Count |
|---|---:|
| Manifest rows | 6388 |
| Duplicate manifest case IDs | 0 |
| Missing manifest case IDs | 0 |
| Audit-complete rows | 6388 |
| Explicit failed rows | 0 |
| Clinical metadata unavailable | 0 |
| Track inventory unavailable | 0 |

## Metadata missingness

| Field | Missing cases |
|---|---:|
| age | 0 |
| sex | 0 |
| height | 0 |
| weight | 0 |
| bmi | 0 |
| asa | 133 |
| subjectid | 0 |
| anesthesia_type | 0 |
| operation_type | 0 |
| emergency_status | 0 |
| anesthesia_start | 0 |
| anesthesia_end | 0 |
| operation_start | 0 |
| operation_end | 0 |

## Approved exact-track combinations

Only `BIS/BIS`, `Orchestra/PPF20_RATE`, and `Orchestra/RFTN20_RATE`
were resolved. No other name was assigned a concept.

| Exact availability combination | Cases |
|---|---:|
| `bis=0|propofol_rate=0|remifentanil_rate=0` | 249 |
| `bis=0|propofol_rate=0|remifentanil_rate=1` | 103 |
| `bis=0|propofol_rate=1|remifentanil_rate=0` | 2 |
| `bis=0|propofol_rate=1|remifentanil_rate=1` | 167 |
| `bis=1|propofol_rate=0|remifentanil_rate=0` | 1310 |
| `bis=1|propofol_rate=0|remifentanil_rate=1` | 1214 |
| `bis=1|propofol_rate=1|remifentanil_rate=0` | 54 |
| `bis=1|propofol_rate=1|remifentanil_rate=1` | 3289 |

## API and parsing failures

| Failure type | Count |
|---|---:|
| none observed | 0 |

## Unapproved alias candidate report

The inventory contains 193 unapproved
track names. Every item below remains `pending_human_review`; frequency does
not imply semantic equivalence or unit validity.

| Track name | Rows | Cases | Distinct TIDs | Status |
|---|---:|---:|---:|---|
| `Solar8000/HR` | 6387 | 6387 | 6387 | pending human review |
| `Solar8000/PLETH_HR` | 6386 | 6386 | 6386 | pending human review |
| `Solar8000/PLETH_SPO2` | 6386 | 6386 | 6386 | pending human review |
| `Primus/CO2` | 6362 | 6362 | 6362 | pending human review |
| `Primus/PAMB_MBAR` | 6361 | 6361 | 6361 | pending human review |
| `Primus/SET_AGE` | 6361 | 6361 | 6361 | pending human review |
| `Primus/AWP` | 6360 | 6360 | 6360 | pending human review |
| `SNUADC/ECG_II` | 6355 | 6355 | 6355 | pending human review |
| `Primus/VENT_LEAK` | 6344 | 6344 | 6344 | pending human review |
| `Primus/ETCO2` | 6339 | 6339 | 6339 | pending human review |
| `Primus/FEN2O` | 6339 | 6339 | 6339 | pending human review |
| `Primus/FIN2O` | 6339 | 6339 | 6339 | pending human review |
| `Primus/INCO2` | 6339 | 6339 | 6339 | pending human review |
| `Primus/MAC` | 6338 | 6338 | 6338 | pending human review |
| `Primus/MAWP_MBAR` | 6338 | 6338 | 6338 | pending human review |
| `Primus/FEO2` | 6335 | 6335 | 6335 | pending human review |
| `Primus/FIO2` | 6335 | 6335 | 6335 | pending human review |
| `Primus/RR_CO2` | 6328 | 6328 | 6328 | pending human review |
| `Solar8000/VENT_MAWP` | 6299 | 6299 | 6299 | pending human review |
| `Solar8000/ETCO2` | 6242 | 6242 | 6242 | pending human review |
| `Solar8000/INCO2` | 6242 | 6242 | 6242 | pending human review |
| `Solar8000/FEO2` | 6239 | 6239 | 6239 | pending human review |
| `Solar8000/FIO2` | 6239 | 6239 | 6239 | pending human review |
| `Solar8000/RR_CO2` | 6177 | 6177 | 6177 | pending human review |
| `SNUADC/PLETH` | 6157 | 6157 | 6157 | pending human review |
| `Primus/SET_FIO2` | 6047 | 6047 | 6047 | pending human review |
| `Primus/SET_FRESH_FLOW` | 6042 | 6042 | 6042 | pending human review |
| `Primus/MV` | 6022 | 6022 | 6022 | pending human review |
| `Primus/TV` | 6018 | 6018 | 6018 | pending human review |
| `Primus/COMPLIANCE` | 6017 | 6017 | 6017 | pending human review |
| `Primus/PIP_MBAR` | 6007 | 6007 | 6007 | pending human review |
| `Primus/PEEP_MBAR` | 5999 | 5999 | 5999 | pending human review |
| `Primus/PPLAT_MBAR` | 5999 | 5999 | 5999 | pending human review |
| `Solar8000/VENT_MV` | 5987 | 5987 | 5987 | pending human review |
| `Solar8000/VENT_RR` | 5987 | 5987 | 5987 | pending human review |
| `Primus/SET_INSP_TM` | 5980 | 5980 | 5980 | pending human review |
| `Primus/SET_INTER_PEEP` | 5980 | 5980 | 5980 | pending human review |
| `Primus/SET_RR_IPPV` | 5980 | 5980 | 5980 | pending human review |
| `Solar8000/VENT_TV` | 5980 | 5980 | 5980 | pending human review |
| `Solar8000/ST_II` | 5978 | 5978 | 5978 | pending human review |
| `Solar8000/VENT_PIP` | 5971 | 5971 | 5971 | pending human review |
| `Primus/SET_INSP_PAUSE` | 5964 | 5964 | 5964 | pending human review |
| `Primus/SET_PIP` | 5964 | 5964 | 5964 | pending human review |
| `Primus/SET_TV_L` | 5964 | 5964 | 5964 | pending human review |
| `Solar8000/VENT_PPLAT` | 5960 | 5960 | 5960 | pending human review |
| `Solar8000/VENT_INSP_TM` | 5939 | 5939 | 5939 | pending human review |
| `Solar8000/BT` | 5935 | 5917 | 5935 | pending human review |
| `BIS/EEG1_WAV` | 5871 | 5871 | 5871 | pending human review |
| `BIS/EEG2_WAV` | 5871 | 5871 | 5871 | pending human review |
| `BIS/SQI` | 5867 | 5867 | 5867 | pending human review |
| `Solar8000/NIBP_MBP` | 5763 | 5763 | 5763 | pending human review |
| `Solar8000/NIBP_DBP` | 5751 | 5751 | 5751 | pending human review |
| `Solar8000/NIBP_SBP` | 5751 | 5751 | 5751 | pending human review |
| `Primus/FLOW_AIR` | 5644 | 5644 | 5644 | pending human review |
| `Primus/FLOW_N2O` | 5644 | 5644 | 5644 | pending human review |
| `Primus/FLOW_O2` | 5643 | 5643 | 5643 | pending human review |
| `BIS/EMG` | 5577 | 5577 | 5577 | pending human review |
| `BIS/SEF` | 5569 | 5569 | 5569 | pending human review |
| `BIS/SR` | 5569 | 5569 | 5569 | pending human review |
| `BIS/TOTPOW` | 5551 | 5551 | 5551 | pending human review |
| `Orchestra/RFTN20_VOL` | 4774 | 4773 | 4774 | pending human review |
| `Orchestra/RFTN20_CE` | 4771 | 4770 | 4771 | pending human review |
| `Orchestra/RFTN20_CP` | 4771 | 4770 | 4771 | pending human review |
| `Orchestra/RFTN20_CT` | 4771 | 4770 | 4771 | pending human review |
| `Solar8000/VENT_SET_TV` | 4253 | 4253 | 4253 | pending human review |
| `Solar8000/ART_DBP` | 3725 | 3725 | 3725 | pending human review |
| `Solar8000/ART_SBP` | 3725 | 3725 | 3725 | pending human review |
| `Solar8000/ART_MBP` | 3724 | 3724 | 3724 | pending human review |
| `Primus/EXP_SEVO` | 3687 | 3687 | 3687 | pending human review |
| `Primus/INSP_SEVO` | 3687 | 3687 | 3687 | pending human review |
| `SNUADC/ART` | 3645 | 3645 | 3645 | pending human review |
| `Orchestra/PPF20_VOL` | 3512 | 3512 | 3512 | pending human review |
| `Orchestra/PPF20_CE` | 3511 | 3511 | 3511 | pending human review |
| `Orchestra/PPF20_CP` | 3511 | 3511 | 3511 | pending human review |
| `Orchestra/PPF20_CT` | 3511 | 3511 | 3511 | pending human review |
| `SNUADC/ECG_V5` | 3390 | 3390 | 3390 | pending human review |
| `Solar8000/GAS2_EXPIRED` | 3097 | 3097 | 3097 | pending human review |
| `Solar8000/GAS2_INSPIRED` | 3097 | 3097 | 3097 | pending human review |
| `Solar8000/ST_III` | 3027 | 3027 | 3027 | pending human review |
| `Solar8000/ST_I` | 3024 | 3024 | 3024 | pending human review |
| `Solar8000/ST_AVF` | 3004 | 3004 | 3004 | pending human review |
| `Solar8000/ST_AVL` | 3004 | 3004 | 3004 | pending human review |
| `Solar8000/ST_AVR` | 3004 | 3004 | 3004 | pending human review |
| `Solar8000/VENT_SET_PCP` | 2745 | 2745 | 2745 | pending human review |
| `Solar8000/VENT_SET_FIO2` | 2212 | 2212 | 2212 | pending human review |
| `Primus/EXP_DES` | 2046 | 2046 | 2046 | pending human review |
| `Primus/INSP_DES` | 2046 | 2046 | 2046 | pending human review |
| `Solar8000/CVP` | 1608 | 1608 | 1608 | pending human review |
| `SNUADC/CVP` | 1586 | 1586 | 1586 | pending human review |
| `Solar8000/RR` | 1294 | 1294 | 1294 | pending human review |
| `EV1000/CI` | 617 | 617 | 617 | pending human review |
| `EV1000/CO` | 617 | 617 | 617 | pending human review |
| `EV1000/SV` | 617 | 617 | 617 | pending human review |
| `EV1000/SVI` | 617 | 617 | 617 | pending human review |
| `EV1000/SVV` | 617 | 617 | 617 | pending human review |
| `EV1000/ART_MBP` | 592 | 592 | 592 | pending human review |
| `Primus/SET_INSP_PRES` | 381 | 381 | 381 | pending human review |
| `Vigileo/CI` | 323 | 323 | 323 | pending human review |
| `Vigileo/CO` | 323 | 323 | 323 | pending human review |
| `Vigileo/SV` | 323 | 323 | 323 | pending human review |
| `Vigileo/SVI` | 323 | 323 | 323 | pending human review |
| `Vigileo/SVV` | 323 | 323 | 323 | pending human review |
| `Orchestra/ROC_RATE` | 281 | 281 | 281 | pending human review |
| `Orchestra/ROC_VOL` | 281 | 281 | 281 | pending human review |
| `EV1000/SVR` | 255 | 255 | 255 | pending human review |
| `EV1000/SVRI` | 255 | 255 | 255 | pending human review |
| `EV1000/CVP` | 235 | 235 | 235 | pending human review |
| `Primus/SET_FLOW_TRIG` | 154 | 154 | 154 | pending human review |
| `Solar8000/FEM_DBP` | 142 | 142 | 142 | pending human review |
| `Solar8000/FEM_MBP` | 142 | 142 | 142 | pending human review |
| `Solar8000/FEM_SBP` | 142 | 142 | 142 | pending human review |
| `Orchestra/PHEN_RATE` | 127 | 127 | 127 | pending human review |
| `Orchestra/PHEN_VOL` | 127 | 127 | 127 | pending human review |
| `SNUADC/FEM` | 127 | 127 | 127 | pending human review |
| `Solar8000/VENT_COMPL` | 114 | 114 | 114 | pending human review |
| `Solar8000/VENT_MEAS_PEEP` | 98 | 98 | 98 | pending human review |
| `Orchestra/FUT_RATE` | 94 | 94 | 94 | pending human review |
| `Orchestra/FUT_VOL` | 94 | 94 | 94 | pending human review |
| `Orchestra/PGE1_RATE` | 90 | 90 | 90 | pending human review |
| `Orchestra/PGE1_VOL` | 90 | 90 | 90 | pending human review |
| `Orchestra/NEPI_RATE` | 88 | 88 | 88 | pending human review |
| `Orchestra/NEPI_VOL` | 88 | 88 | 88 | pending human review |
| `Solar8000/PA_DBP` | 81 | 81 | 81 | pending human review |
| `Solar8000/PA_MBP` | 81 | 81 | 81 | pending human review |
| `Solar8000/PA_SBP` | 81 | 81 | 81 | pending human review |
| `Orchestra/RFTN50_CE` | 69 | 68 | 69 | pending human review |
| `Orchestra/RFTN50_CP` | 69 | 68 | 69 | pending human review |
| `Orchestra/RFTN50_CT` | 69 | 68 | 69 | pending human review |
| `Orchestra/RFTN50_RATE` | 69 | 68 | 69 | pending human review |
| `Orchestra/RFTN50_VOL` | 69 | 68 | 69 | pending human review |
| `Vigilance/CI` | 65 | 65 | 65 | pending human review |
| `Vigilance/CO` | 65 | 65 | 65 | pending human review |
| `Vigilance/BT_PA` | 64 | 64 | 64 | pending human review |
| `Vigilance/SQI` | 63 | 63 | 63 | pending human review |
| `Vigilance/SVO2` | 63 | 63 | 63 | pending human review |
| `Vigilance/SNR` | 59 | 59 | 59 | pending human review |
| `Vigilance/SV` | 55 | 55 | 55 | pending human review |
| `Vigilance/SVI` | 55 | 55 | 55 | pending human review |
| `Vigilance/HR_AVG` | 53 | 53 | 53 | pending human review |
| `Vigilance/EDV` | 49 | 49 | 49 | pending human review |
| `Vigilance/EDVI` | 49 | 49 | 49 | pending human review |
| `Vigilance/ESV` | 49 | 49 | 49 | pending human review |
| `Vigilance/ESVI` | 49 | 49 | 49 | pending human review |
| `Vigilance/RVEF` | 48 | 48 | 48 | pending human review |
| `Invos/SCO2_L` | 33 | 33 | 33 | pending human review |
| `Invos/SCO2_R` | 33 | 33 | 33 | pending human review |
| `Orchestra/DOPA_RATE` | 33 | 33 | 33 | pending human review |
| `Orchestra/DOPA_VOL` | 33 | 33 | 33 | pending human review |
| `Orchestra/NTG_RATE` | 32 | 32 | 32 | pending human review |
| `Orchestra/NTG_VOL` | 32 | 32 | 32 | pending human review |
| `CardioQ/ABP` | 29 | 29 | 29 | pending human review |
| `CardioQ/CO` | 29 | 29 | 29 | pending human review |
| `CardioQ/FLOW` | 29 | 29 | 29 | pending human review |
| `CardioQ/FTc` | 29 | 29 | 29 | pending human review |
| `CardioQ/HR` | 29 | 29 | 29 | pending human review |
| `CardioQ/MD` | 29 | 29 | 29 | pending human review |
| `CardioQ/SD` | 29 | 29 | 29 | pending human review |
| `CardioQ/SV` | 29 | 29 | 29 | pending human review |
| `CardioQ/CI` | 28 | 28 | 28 | pending human review |
| `CardioQ/FTp` | 28 | 28 | 28 | pending human review |
| `CardioQ/MA` | 28 | 28 | 28 | pending human review |
| `CardioQ/PV` | 28 | 28 | 28 | pending human review |
| `CardioQ/SVI` | 28 | 28 | 28 | pending human review |
| `FMS/FLOW_RATE` | 15 | 15 | 15 | pending human review |
| `FMS/INPUT_AMB_TEMP` | 15 | 15 | 15 | pending human review |
| `FMS/INPUT_TEMP` | 15 | 15 | 15 | pending human review |
| `FMS/OUTPUT_AMB_TEMP` | 15 | 15 | 15 | pending human review |
| `FMS/OUTPUT_TEMP` | 15 | 15 | 15 | pending human review |
| `FMS/PRESSURE` | 15 | 15 | 15 | pending human review |
| `FMS/TOTAL_VOL` | 15 | 15 | 15 | pending human review |
| `Orchestra/EPI_RATE` | 9 | 9 | 9 | pending human review |
| `Orchestra/EPI_VOL` | 9 | 9 | 9 | pending human review |
| `Orchestra/DEX2_RATE` | 6 | 6 | 6 | pending human review |
| `Orchestra/DEX2_VOL` | 6 | 6 | 6 | pending human review |
| `Orchestra/MRN_RATE` | 5 | 5 | 5 | pending human review |
| `Orchestra/MRN_VOL` | 5 | 5 | 5 | pending human review |
| `Orchestra/DEX4_RATE` | 4 | 4 | 4 | pending human review |
| `Orchestra/DEX4_VOL` | 4 | 4 | 4 | pending human review |
| `Orchestra/DOBU_RATE` | 3 | 3 | 3 | pending human review |
| `Orchestra/DOBU_VOL` | 3 | 3 | 3 | pending human review |
| `Orchestra/OXY_RATE` | 3 | 3 | 3 | pending human review |
| `Orchestra/OXY_VOL` | 3 | 3 | 3 | pending human review |
| `Orchestra/DTZ_RATE` | 2 | 2 | 2 | pending human review |
| `Orchestra/DTZ_VOL` | 2 | 2 | 2 | pending human review |
| `Orchestra/AMD_RATE` | 1 | 1 | 1 | pending human review |
| `Orchestra/AMD_VOL` | 1 | 1 | 1 | pending human review |
| `Orchestra/NPS_RATE` | 1 | 1 | 1 | pending human review |
| `Orchestra/NPS_VOL` | 1 | 1 | 1 | pending human review |
| `Orchestra/VASO_RATE` | 1 | 1 | 1 | pending human review |
| `Orchestra/VASO_VOL` | 1 | 1 | 1 | pending human review |
| `Orchestra/VEC_RATE` | 1 | 1 | 1 | pending human review |
| `Orchestra/VEC_VOL` | 1 | 1 | 1 | pending human review |
| `Solar8000/ST_V5` | 1 | 1 | 1 | pending human review |

## Prohibited downstream work

No full signal download, threshold finalization, cohort freeze, split,
prediction, feature selection, Cp/Ce reconstruction, or PPO execution was
performed. Phase 5A stops at metadata and track inventory.
