# TraceSync continuation

Updated 2026-10-18: documentation-only cloud direction checkpoint.

## Source versus published application

The public downloadable application remains v0.11.0 (local/mapped folders,
guided workflow and backup recovery). This checkpoint changes plans/instructions
only; the version-manager source tag is not a new executable or portfolio release.
No cloud or SFTP feature is enabled by this checkpoint.

## Accepted direction

Everyday users; OneDrive personal first, Google Drive second; Dropbox later.
SFTP is removed from the consumer roadmap with unfinished work preserved.
Manual compare-review-confirm-sync remains mandatory. Safe cloud overwrite has
its own future milestone; local overwrite limitations are not transferable.

Read AGENTS.md, docs/CLOUD_STORAGE.md, docs/ROADMAP.md and docs/BRANCH_WORKFLOW.md
before changing code. The next branch is codex/onedrive-account-folder-pairs:
connect account -> choose folder -> save Folder Pair, using local fake-based tests.
Do not activate cloud transfers or claim live acceptance during that slice.

## Preserved development

Canonical workspace: C:/Users/Administrator/Desktop/GH/TraceSync on
codex/cloud-sftp-resume, based on 378bad8, with unreleased SFTP/cloud work.
Stash: TraceSync pre-pull SFTP workspace 2026-10-18.
Backup: C:/Users/Administrator/.codex/worktrees/tracesync-resume-backup-20261018.
Its prior suite ran 260 tests (256 passed, four SFTP tests skipped). Those results
belong to that workspace, not primary-branch cloud capabilities. Preserve it.

## Validation and limitations

PASS: documentation diff/relative-link checks; source scope review confirms no
application code changes. Required branch/ruleset checks inspected: primary is
unprotected and no rulesets were returned. No bypass was used.
NOT RUN - OUT OF SCOPE: application suite/build for documentation-only changes.
NOT RUN - ENVIRONMENTAL: live OAuth/cloud acceptance; no app registration or test
endpoint. Continue offline scaffolding and tests as the user requested.
