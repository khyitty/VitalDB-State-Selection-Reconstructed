# Phase 7D Excluded Scaffold Backup Verification

The 14 excluded local paths recorded in `docs/phase7c_excluded_scope_changes.md` matched the pre-cleanup Git status exactly: five tracked modifications and nine untracked files, with no unrelated change.

Before cleanup, a non-repository sibling backup was created with identifier `VitalDB-State-Selection-Reconstructed-excluded-scaffold-backup-989dc90`. The backup is intentionally not committed and no local absolute path is recorded here.

Verification evidence:

- source HEAD: `989dc909e7e2380d27c5fb1b3ab8601018ef68f7`
- excluded paths: 14/14 accounted for
- exact working-file copies: 14/14 SHA-256 matched source bytes
- tracked binary patch SHA-256: `2077ca78496b9e4889a8f96a7e310a50e743d66a0a50b727a6a44a81aa752e45`
- backup manifest SHA-256: `2fc1b8e8a0b7b8add946667d39c43c8c62fa6abbe1c77606a29901cee06f603a`
- `git apply --check`: passed on a temporary clean HEAD archive
- tracked reconstruction: 5/5 normalized text contents matched (the archive uses LF while the Windows worktree used CRLF)
- temporary verification tree: removed

The first reconstruction hash comparison expected byte-identical line endings and correctly stopped after detecting the LF/CRLF difference. The backup was strengthened with exact tracked working-file copies, and the final verification then passed. A later manifest-field check also stopped because untracked copy paths were implicit; those relative paths were added and the complete verification passed.

Only the five enumerated tracked paths were selectively restored. Only the nine enumerated untracked files were removed. No `git clean`, reset, branch change, whole-tree checkout, or unrelated deletion was used. The worktree was clean before Phase 7D amendment files were created.
