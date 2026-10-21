# Scoped milestone branches

Adapted from TraceForge's Ground, Align, Plan, Act, Verify, Capture, Handoff
lifecycle and its engineering judgment/continuity rules. Branch names below are
TraceSync's concrete application of that methodology, not a quoted TraceForge rule.

Before each change read AGENTS.md, CONTINUE.md, docs/CLOUD_STORAGE.md and the active
ROADMAP milestone; inspect Git status/history and affected tests. State scope,
owners, compatibility, exclusions and completion evidence before implementation.
Record deliberate direction changes in the plan instead of silently expanding it.

| Branch | Responsibility | Dependencies |
| --- | --- | --- |
| codex/cloud-plan-checkpoint | Documentation and roadmap baseline | Current primary |
| codex/onedrive-account-folder-pairs | Personal account connection, folder browser, credential-free saved pairs and offline tests | Plan checkpoint |
| codex/onedrive-reviewed-copy | Pair activation, refresh/reconnect, reviewed create-only transfers and history | Reviewed setup branch |
| codex/onedrive-create-folders-empty | Empty uploads and reviewed parents required by selected files | Published reviewed-copy source v0.14.0 |
| codex/onedrive-create-safety-audit | Mission audit: reviewed folder evidence, partial history and failure coverage | Published v0.15.0; preserve dirty pair-management separately |
| codex/onedrive-safe-replacement | Conditional commit and recoverable replacement | Validated create-only workflow |
| codex/google-drive-workflow | Google scope/Picker and provider-specific workflow | Shared setup boundaries validated |

Use one branch per coherent milestone, not one per file. Keep worktrees under
C:/Users/Administrator/.codex/worktrees. Start from current primary or explicitly
record a dependency branch. Import only necessary scaffold files and name their
source commits. Never merge unfinished SFTP history to obtain shared files.

Review the diff for safety, duplication, secrets and accidental scope. Run affected
tests, then dependent regressions; broad shared/settings/UI changes warrant the
full suite. Offline tests do not establish OAuth/server/packaged acceptance.
Update handoff and plan with actual outcomes and remaining gates. Merge only the
scoped, validated milestone, subject to repository checks and user authorization.
Use vm-commit when requested; preview with the shared adapter, integrate primary,
push and verify remote identities. Do not publish a binary for a docs checkpoint.

Preserved work: the canonical cloud-sftp-resume workspace, its pre-pull stash and
file backup remain intact until independently reconciled. SFTP is off the consumer
roadmap. New cloud work must not depend on its settings, authentication or UI.

## Local provider completion work — 2026-10-21

OneDrive and Google completion use separate branches from local ec009ff:
`codex/onedrive-provider-completion` and `codex/google-drive-provider-completion`.
The latter selectively includes shared OneDrive fixes, not a merge of unfinished
history. Record shared file hashes before eventual integration and reconcile once;
do not merge an entire dirty/historical provider worktree. These changes are
preserved in local source preparation checkpoints. The user's current local-only restriction overrides the universal
vm-commit integration/push default. No build, release or live sign-in is authorized.
See PROVIDER_COMPLETION.md and PROVIDER_COMPLETION_VALIDATION.md.
