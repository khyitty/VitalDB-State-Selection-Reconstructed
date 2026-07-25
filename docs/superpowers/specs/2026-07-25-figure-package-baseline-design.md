# Reproducible Manuscript Figure Package Baseline Design

## Scope

Audit, classify, validate, commit, and push only the current manuscript figure
package. Phase 8D/8E/8F scientific results and private outputs remain immutable.
Phase 8G implementation, training, and evaluation remain out of scope.

The user removed the separately produced `paper/figures_skill/` directory from
the repository during the audit. It is outside this baseline and receives no
repository modification, test, provenance record, classification, or commit.

## Classification

Every untracked file is classified as required, optional-but-valuable, or
prohibited. Publication-safe aggregate CSVs must match the checksum-frozen Phase
8F public artifacts. No case-level, subject-level, event-level, trajectory,
private-path, model, checkpoint, or secret material may be committed.

Final manuscript figures, their generation sources, plot-ready public aggregate
data, captions, snippets, manifests, and audit documentation are required.
## Verification

The complete package is also checked for CSV provenance, privacy leakage,
absolute local paths, Python syntax/importability, valid nonempty PDF/PNG files,
snippet references, unintended tracked modifications, and accidental private
file staging.

## Delivery

Only validated figure-package files are staged. The commit is pushed to
`origin/main`, independently fetched and verified, and reported as
`FIGURE_PACKAGE_BASELINE_SHA`. Phase 8G does not begin in this operation.
