# Phase 8F confirmatory plot generation report

- Source commit SHA: `71156050465e64892032b475974787b196eb2c3f`
- Python: `3.11.9`
- pandas: `2.0.3`
- matplotlib: `3.7.2`
- numpy: `1.23.5`
- Renderer: Python/Matplotlib, used because the local R 4.5.2 base initialization path crashed before plotting code
- Condition source: `paper/generated/tables/condition_metrics.csv` (`9e452bd0ab58228b23aba1cc4052d491564f89944aa64c0caf17fd2dea6675ca`)
- Contrast source: `paper/generated/tables/paired_contrasts.csv` (`67bedc0a92017adaa07393e5ba31446698ffc3dfc4e3e43592f4085343b585fe`)
- Frozen aggregate checksum: `2939f9580a992ef8f43d9f57bc2c7c5a1159b147d3739a6a8809932ac81fcae1`
- Frozen statistics checksum: `681926cb34830cf11391994dbc7d7c14352e94527c2f36549a6fe86547def6ff`
- Source rows: 44 condition-metric rows and 55 paired-contrast rows
- Analysis unit: 483 subjects
- Condition order: P0S0, P1S0, P0S1, P1S1
- Plotting-only transformations: time-in-range, below-range, above-range, and integrated BIS-point-time values divided by 60 when labeled in minutes
- Private, case-level, subject-level, or event-level input rows used: 0
- Evaluation/training/simulator reruns: 0
- Bootstrap/permutation reruns: 0
- Scientific value modifications: 0
- Condition ranking or best-condition selection: 0

## Generated figures

All PNG outputs were requested at 600 dpi. PDF outputs use the Matplotlib vector PDF backend.

| Figure | Dimensions (in) | PNG SHA-256 | PDF SHA-256 |
|---|---:|---|---|
| `figure_main_interaction` | 7.2 × 5.6 | `15eed2a3d2e81377b139920cdf73dd72db51d0085731d573b378ac380b776cf7` | `b23361950dd7e2c67b454700ec509957d49cc39e0ab2ad252c83b067bc8b9c70` |
| `figure_main_contrast_forest` | 7.2 × 6.4 | `bbc2fe9c988ea691bb4d8e470cff7e89fda084713331cf91c42b0aad3011f9c1` | `68e8654ce7376b10d19d14bc148d428ce0b0566e7b1e79e1878834db76af08c3` |
| `figure_mae_interaction` | 3.5 × 3.0 | `a0a3b0ee93d49bbde2759f152b28dff70e3b22f81b93ed53cbe0bcb67d26fd0c` | `950fad5d8451994fe0145a8131c40546e52e655552b8898e262b24488fbcd852` |
| `figure_supp_accuracy_interactions` | 7.2 × 6.0 | `71cdc318ea66f6743d17e8413328d6129fabbec3c70b93c252321ae7f9bd95e0` | `1f2356728b7f2908c01319af816550b6b9d12aca49f4b1a148dc630f5b6c220d` |
| `figure_supp_range_interactions` | 7.2 × 5.6 | `062edd9099c9e9ee494a8610fb4a5cea9e7b3f72672e6a7f2432293941122d81` | `fb93561bb27c313da6b7d9afeacfbd8e994868bd6cf66f9bbc0ddee444aa828b` |
| `figure_supp_control_interactions` | 7.2 × 6.0 | `eafa530e499a9353bd1ef28725c85fd76525c944f57f03c98b667391056ef76b` | `be7750f09fb49515d64a929e62598cddf47f4a7c56556298f0a4974e5950675e` |
| `figure_supp_accuracy_forest` | 7.2 × 6.4 | `55414fbb717132debd49cccacb45e075f060b235b6d78011a942004f383be572` | `c19e2983d58c37dae6947c06e143c7dfcb85ed06e8e83fafc896a8bba09ab076` |
| `figure_supp_range_forest` | 7.2 × 6.4 | `457f4c6f65d3668dca8dcd27f573d90f967802111f2233c3e3170b89c7042ed5` | `8bb66f93d98f8553252e15d4e9b6d421807488c7b981823827724fbb48a119cc` |
| `figure_supp_control_forest` | 7.2 × 6.4 | `fc1a85b0b37bcb04737ce337fc69e68538bc3cc01021648be6f546c92d4e699b` | `f1e5ecadd81013bbdf56f80e86d5568cfd0d51626ec3eb54571e37e637acde6f` |

## Numeric verification

The source tables passed exact display-value checks for the four MAE condition means, four action-change condition means, the three named MAE component contrasts, and the MAE interaction estimate and confidence interval. All interval lower bounds were less than or equal to their means and all means were less than or equal to their upper bounds.
