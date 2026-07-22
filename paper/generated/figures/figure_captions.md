# Phase 8F confirmatory figure captions

All panels show latent-BIS simulator outcomes for the 483 sealed-test subjects. Interaction figures show condition means in the fixed P0S0, P1S0, P0S1, P1S1 design order. Forest figures show paired subject-level mean differences and 2,000-replicate subject-level bootstrap 95% confidence intervals in the five prespecified contrast directions. Time and BIS-point-time values labeled in minutes use a visualization-only division by 60; source CSV values remain in seconds. The meaning of a positive or negative contrast depends on the metric direction. No figure ranks conditions or selects a best condition.

## Main interaction figure

`figure_main_interaction` shows the 2 × 2 preprocessing-by-state interactions for mean absolute BIS deviation, time in BIS 40–60, cumulative propofol amount, and action-change magnitude. Point labels are the corresponding condition means.

## Main paired-contrast forest figure

`figure_main_contrast_forest` shows the five prespecified paired contrasts for the four main metrics. Points are mean paired differences, horizontal intervals are bootstrap 95% confidence intervals, and the dotted vertical line is zero.

## Standalone MAE interaction figure

`figure_mae_interaction` shows mean absolute BIS deviation for the four conditions, with condition means labeled to three decimal places.

## Supplementary accuracy interaction and forest figures

`figure_supp_accuracy_interactions` and `figure_supp_accuracy_forest` show mean absolute deviation, root mean squared deviation, integrated absolute BIS error, and maximum absolute deviation as condition means and prespecified paired contrasts, respectively.

## Supplementary range and safety interaction and forest figures

`figure_supp_range_interactions` and `figure_supp_range_forest` show time in BIS 40–60, time below BIS 40, and time above BIS 60. Seconds are divided by 60 only for visualization.

## Supplementary control interaction and forest figures

`figure_supp_control_interactions` and `figure_supp_control_forest` show cumulative propofol amount, mean propofol infusion rate, action-change magnitude, and cumulative episode reward as condition means and prespecified paired contrasts, respectively.
