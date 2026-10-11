# TraceSync continuation

Updated 2026-10-11 for v0.11.0, Guided workflow and recovery.
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

## Next work

Continue SFTP in its preserved development workspace, reconciling the release UI
fixes before integration. Its explicit disposable endpoint and packaged credential/
host-trust gates remain outstanding. Do not claim atomic existing-file replacement.
