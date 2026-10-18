# TraceSync continuation

Updated 2026-10-18. Active branch: codex/onedrive-reviewed-copy, worktree
C:/Users/Administrator/.codex/worktrees/tracesync-onedrive-reviewed-copy.
Base: d18f494e549ba44088f2e3fa35df1cff4a18a0b2. Reviewed-copy integration is being checkpointed as source v0.14.0; no binary release.

## Published source checkpoint

The user-requested setup vm-commit is complete. The shared version manager,
invoked through scripts/vm_release.py after preview, created source tag v0.13.0
and commit d18f494. It was fast-forwarded into master and pushed atomically with
the setup branch and tag. Remote master, codex/onedrive-account-folder-pairs and
v0.13.0 were verified at the same full commit above. No rulesets were returned;
master was unprotected. The setup checkpoint passed all 181 tests before commit.
No binary was built or published; the portfolio executable remains v0.11.0.

## Plan and current slice

Before changes read AGENTS.md, docs/CLOUD_STORAGE.md, docs/ROADMAP.md and
 docs/BRANCH_WORKFLOW.md. OneDrive personal first, Google Drive next; SFTP remains
preserved but off the consumer roadmap. Keep manually initiated review/confirmation.

The reviewed-copy branch includes the identity prerequisite:
- Saved pairs can reopen in setup after verifying local-folder access and native
  Graph account, drive and folder IDs. Old UI selections are cleared on failure.
- An optional non-secret auth_account_id references one MSAL home account. Explicit
  sign-in derives it only from a unique cache entry matching token claims.
- Silent renewal targets that exact account, never the first cached account.
  Missing/ambiguous/expired credentials require explicit Reconnect; no silent
  browser launch or account fallback. Graph identity is independently verified.
- Successful explicit reconnect can upgrade a legacy pair's cache reference only
  after Graph checks and checking the saved definition has not changed.
- Disconnect removes only that account's cache entries, preserving other accounts,
  saved pairs and cloud files. It does not revoke browser/server-side sign-in.
- Dialog workers pass results through a queue without retaining the Tk dialog;
  callbacks run on Tk's thread. Closing discards UI results, not a browser sign-in
  or cache refresh already in progress.

Verified saved pairs now activate main-window comparison and confirmed new-file
uploads/downloads through the existing preview, runner and history. Graph requests
renew the exact account token; uploads fail on conflicts and uncertain completion
is recorded without retry. Downloads check source metadata around staging.
Overwrites are blocked in both directions. Nonempty uploads require existing cloud
parent folders; empty uploads and missing parent folders are excluded with warnings.
Empty downloads work. No scheduling, folder-creation or replacement is added.

## Validation

PASS: setup commit gate: 181 tests, .tmp-setup-commit-tests.log in setup worktree.
PASS: first compatibility run of auth/setup/dialog: 22 tests.
FAIL - CAUSED BY CURRENT WORK / test interaction, corrected: extended UI tests
exposed collection of destroyed Tk fixtures on a worker and a hidden-window
geometry assertion. Workers no longer capture the dialog, fixtures collect on
the Tk thread, and geometry checks explicitly map the window. All reruns pass.
PASS: final `C:/Users/Administrator/Desktop/GH/TraceSync/.venv/Scripts/python.exe
-m unittest discover -s tests`: 212 tests, no failures/skips; log
.tmp-copy-suite.log. Existing ThemeChanged teardown diagnostics persist.
PASS: git diff --check and review of account-scoped persistence and failure paths.
PASS: targeted provider/main-window suite: 15 tests. Covers read-only comparison,
confirmation cancellation, durable history, source changes, conflicts, truncated
downloads, unknown upload outcomes, chunk ranges and blocked replacements.
Scope: auth, shared settings, synchronization and UI changes warrant the full
local regression suite.
NOT RUN - ENVIRONMENTAL: live OAuth/Graph/DPAPI acceptance; no test account or
registration. Optional SDKs are not installed or pinned in release requirements.
NOT RUN - OUT OF SCOPE: executable build/upload and manual desktop acceptance.

## Next work on this branch

1. Define reviewed nested-folder creation and empty-file upload semantics. Do not
   silently create unreviewed paths or weaken expected-absence guarantees.
2. Complete saved-pair edit/delete UX, SDK/packaging and disposable-account checks.
   Offline tests are not live acceptance. Safe replacement is a separate branch.
3. Continue empty-file and reviewed destination-folder creation on a dependent
   milestone branch after publishing this integration. Public executable remains v0.11.0.

Preserved mixed workspace: C:/Users/Administrator/Desktop/GH/TraceSync on
codex/cloud-sftp-resume, with SFTP/cloud work, stash and backup intact. Do not
resume feature work there or merge its unfinished history into this branch.
