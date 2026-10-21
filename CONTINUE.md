# TraceSync continuation

Updated 2026-10-21 for Google Drive provider development on
`codex/google-drive-provider`. The v0.11.0 release remains the current tagged
local-only release; this branch is experimental and has not been released.
Read AGENTS.md, README.md, docs/ARCHITECTURE.md, docs/ROADMAP.md and docs/RELEASE.md.

## Release scope

Material-inspired UI (green next step, pale-green guide, amber review/warnings),
local new-file race fix and regression tests, backup-before-overwrite and history
restore, provider-neutral transfer foundation. Existing-file overwrite/restore
retain the accepted external-writer race documented in architecture.

Release preparation uses codex/ui-release-v011, combining committed foundation
8c00cab with origin/master 2c9c007 and selected local safety/presentation changes.
The original codex/provider-aware-comparison-backup workspace keeps unfinished
SFTP services, setup UI, settings, dependencies, tests and packaging uncommitted.
Do not reset that workspace or release its SFTP work implicitly. The release uses
local-only provider controls and excludes all SFTP modules/dependencies.

## Actual validation

- PASS: `python -m unittest discover -s tests`: 159 tests, no skips. Broad suite
  selected for shared UI/transfer and a public release. Tk ThemeChanged teardown
  diagnostics remain without failures.
- PASS: `python -m unittest tests.test_ui_theme tests.test_sync_history_dialog`:
  17 tests, also passed on the original SFTP development workspace.
- PASS: PyInstaller 6.20.0 / hooks 2026.6, Python 3.11 Windows x64 build using
  `python -m PyInstaller --noconfirm TraceSync.spec`. VERSION resource is 0.11.0.
- PASS: actual executable startup, comparison of six sample files, amber
  low-confidence warning and both directions, explicit preview, two sample copies
  (one overwrite), durable v0.11.0 history and backup, confirmed backup restore;
  destination bytes verified after copy and restore. Isolated settings/folders/
  LOCALAPPDATA only. Packaged screenshots are in docs/images/v0.11.0/.
- FAIL - CAUSED BY CURRENT WORK, corrected: increased row spacing exposed footer
  starvation in history details. Reserve button space before the expanding tree;
  regression checks compact geometry. Retain Counts StringVar so counts render.
- PASS: VM preview through scripts/vm_release.py changes only VERSION/CHANGELOG;
  historical v0.10 product-tour text and images remain unchanged.
- PASS: git diff --check.
- NOT RUN - ENVIRONMENTAL: real mapped-drive/alternate-DPI acceptance and real
  SFTP server validation. SFTP is excluded, not declared accepted.

## Build artifact

Unsigned portable Windows x64 executable, 12,805,215 bytes.
SHA-256: 1205D84AE619D395B42D367F01901388E4185355AA01879285CDA1E63F37810C
Portfolio destination: https://tepong32.github.io/assets/downloads/TraceSync-v0.11.0.exe
Keep historical downloads. Verify master/tag push and portfolio Pages deployment
against this checksum; publication outcomes are recorded in the portfolio handoff.

## Current development branches

- `codex/google-drive-provider`: Google Drive read/download integration is now
  wired through desktop Picker OAuth, saved folder endpoints, comparison, review,
  local download execution, and disconnect/revoke. The adapter handles paging,
  shared-drive results, ambiguous/Windows-invalid names, unsupported Workspace
  items, folder-list access checks, source version revalidation, temporary
  downloads, size checks, and MD5 checks. Drive uploads remain disabled because
  Drive cannot enforce the required path-level conditional create. Settings now
  migrate to `%APPDATA%\TraceSync`; refresh credentials stay in Windows
  credential storage. PyInstaller packaging requires `TRACESYNC_GOOGLE_CLIENT_ID`
  and embeds that public client ID, not a secret or user token. Validation:
  - PASS: `python -m unittest discover -s tests`: 178 tests, no skips. Drive
    transfer tests cover materialization, checksum/size validation, pre-transfer
    source-version failure, rechecks, and temporary-file cleanup. Reserved
    Windows device suffixes are covered too.
  - PASS: `python -m compileall -q` on changed Python modules and `git diff --check`.
  - PASS: PyInstaller 6.20.0 / hooks 2026.6, Python 3.11.9 Windows x64 build
    with `TRACESYNC_GOOGLE_CLIENT_ID=packaging-test.apps.googleusercontent.com`.
    Replacing `dist/TraceSync.exe` failed with WinError 5 twice (a TraceSync
    process was present on the first attempt; none was present on the second).
    The successful build used `--distpath dist-google-smoke` and is now
    `dist/TraceSync-google-smoke.exe`, 37,940,373 bytes.
  - PASS: fixed PyInstaller's missing Windows Credential Manager backend by
    explicitly including `keyring.backends.Windows`. The full TraceSync archive
    contains that backend plus `pywin32-ctypes` modules.
  - PASS: frozen Keyring probe stored, read, and deleted a disposable credential
    through Windows Credential Manager. A separate bundled TraceSync launch
    reached the Tk event loop with isolated app data. These smoke checks do not
    establish live OAuth or Drive transfers.
  - NOT RUN - ENVIRONMENTAL: real sign-in, consent, `drive.file` subtree access,
    packaged app OAuth, and downloads. The owner must provide the public
    Desktop OAuth client ID, enable Drive API and Picker API, configure the
    consent screen/test users, and provide a disposable account/folder. No real
    client ID or live Google account has been supplied.
- `codex/onedrive-provider`: sibling branch from the shared cloud foundation;
  integration has not started. Add MSAL delegated sign-in and secure token
  storage, OneDrive folder selection, settings/provider/UI wiring, Graph scan and
  download behavior with IDs/eTags, and create-only upload sessions using fail
  conflict behavior. Keep overwrite unsupported. Validate account/tenant support,
  pagination, upload interruption/unknown outcomes, packaged credentials, and
  live sign-in/transfers with a disposable Microsoft account. Client/app
  registration values remain configuration placeholders until supplied.
- `codex/sftp-provider-workflow`: provider work remains preserved in the stash
  `WIP SFTP provider foundation`. Restore only on that branch. Disposable endpoint
  and packaged credential/host-trust gates remain outstanding; do not claim
  atomic existing-file replacement.

For the Google scaffolding commit, the VM adapter needed repair: the shared
version manager checkout is a single `version_manager.py` module, not the
`version_manager.documentation` package the adapter previously imported. The
adapter now loads that module directly and suppresses automatic edits to
versioned documentation, preserving the release workflow's VERSION/CHANGELOG
only boundary. No tests were run for this scaffolding or adapter repair.
