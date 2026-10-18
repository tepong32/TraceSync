# TraceSync continuation

Updated 2026-10-18. Active implementation is in the isolated worktree
C:/Users/Administrator/.codex/worktrees/tracesync-onedrive-setup on
codex/onedrive-account-folder-pairs, based on e5678b2. Setup is captured by source checkpoint v0.13.0.
The next implementation branch is codex/onedrive-reviewed-copy; do not treat
this source checkpoint as a new packaged or live-accepted cloud release.

## Completed documentation checkpoint

The shared version manager (through scripts/vm_release.py) created the actual
v0.12.0 documentation checkpoint. It was fast-forwarded into master and pushed;
remote master and v0.12.0 both verified as e5678b2db108ece94ab28eaf22354c961c3f5372.
Historical version references were preserved. This is not a new executable;
the portfolio's downloadable application remains v0.11.0.

Read AGENTS.md, docs/CLOUD_STORAGE.md, docs/ROADMAP.md and docs/BRANCH_WORKFLOW.md
before every provider/settings/UI change. OneDrive personal first, Google Drive
next. SFTP is off the consumer roadmap; Dropbox is a later candidate. Runs remain
manually initiated and reviewed. Cloud safe overwrite is a separate milestone.

## Setup source checkpoint v0.13.0

- Separate OneDrive setup dialog: Connect account -> browse/select folder ->
  choose local folder/name -> save pair. Network/auth work runs off the Tk thread.
- Read-only Graph gateway with personal-drive validation, pagination, native IDs,
  no redirect following, foreign paging URL rejection and sanitized errors.
- Existing Folder Pair collection extended with allowlisted server_endpoint data.
  No tokens or cloud-path coercion; local selectors cannot activate cloud pairs.
  Local edits preserve cloud records and reserve their names.
- Settings writes stage/flush and atomically replace JSON; failure preserves the
  prior file. This is not a concurrent-writer settings lock.
- Personal public-client MSAL adapter with explicit account choice and protected
  cache boundary. Only this auth scaffold was imported from the prior branch.

## Validation

PASS: initial settings/local UI compatibility tests: 25 tests.
PASS: setup/gateway/dialog plus settings/local UI targeted run: 40 tests.
PASS: full `C:/Users/Administrator/Desktop/GH/TraceSync/.venv/Scripts/python.exe
-m unittest discover -s tests`: 179 tests before two final UI regressions.
PASS: final `python -m unittest tests.test_onedrive_setup_dialog -v`: five tests,
including minimum-size reachability and preservation of cloud pairs by local edits.
PASS: final full-suite rerun: 181 tests, no failures or skips; log .tmp-setup-final.log.
PASS: git diff --check; review confirmed setup does not construct a transfer provider.
Existing Tk ThemeChanged teardown diagnostics persist; they did not fail tests.
Scope: shared settings and UI integration justified the full local suite.

NOT RUN - ENVIRONMENTAL: live OAuth/Graph/DPAPI acceptance; no app registration or
disposable cloud account. Optional SDKs remain uninstalled and unpinned.
NOT RUN - OUT OF SCOPE: binary build, portfolio publication, live transfer tests,
manual desktop acceptance. No SFTP code was imported or modified in this worktree.

## Remaining work / next branch

Setup is an offline-tested preview, not a usable cloud sync release. Before the
next reviewed-copy milestone: cloud pair reopen/edit/delete and activation, exact
account matching and silent renewal/reconnect/sign-out, optional SDK packaging,
provider conflict/unknown-outcome tests, empty-file and nested-folder support,
comparison/review/history integration, then explicit disposable-account acceptance.
Do not enable copy/overwrite just because setup or local tests succeed.

The canonical GH/TraceSync workspace on codex/cloud-sftp-resume still preserves
unfinished SFTP/cloud work, stash and file backup. Its 260-test result belongs to
that mixed workspace. Continue new work here, not in the preserved mixed tree.
