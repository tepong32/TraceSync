# Saved Server Folder restoration validation

## Source and cause

Branch codex/onedrive-create-safety-audit, HEAD
5292753873beed89a49daee03f83123772baa634 (parent 0de6aa2).
Started clean, no upstream configured. This report describes an uncommitted fix.

MainWindow._build_ui registers write traces on local_var/server_var before
_load_saved_folders. The fallback startup path set local_var, firing
_on_folder_value_changed -> _sync_folder_pair_selection_from_paths. That copies
both field values into self.settings, including the still-blank Server field.
The next statement read that erased value. Configuration loading, path validation
and Tk binding were not the cause. Local restored; active named local pairs read
from their separate pair dictionary and were unaffected. Even an absent Local
value triggered the write trace. Startup alone did not rewrite the disk file,
but a later settings save could persist the erased in-memory value.

The fix captures both fallback settings values before setting either variable.
No callback, sync, cloud, pair-management or persistence policy changes.
Nonexistent and non-directory paths remain visible for correction; comparison
rejects them. Absent settings start blank. No folder is created automatically.

## Reproduction and regression evidence

Six new tests in tests/test_main_window_startup.py exercise actual MainWindow
startup with disposable settings and LOCALAPPDATA: saved endpoints, initial blank
setup, missing/file destination, active named pair, Browse/save/restart, and
Server-only configuration. Before the fix: 6 tests, 5 assertion failures (including
two subtest failures); after the fix all pass in the suites below.

Use the existing isolated builder interpreter:
`C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-builder-5292753/venv/Scripts/python.exe`.
Run from the active repository worktree; logs live under that external builder.

```powershell
python -B -m unittest tests.test_main_window_startup -v
python -B -m unittest tests.test_main_window_startup tests.test_settings_service tests.test_folder_pair_manager tests.test_main_window_filters tests.test_onedrive_main_window tests.test_onedrive_transfer tests.test_synchronization -q
python -B -m unittest discover -s tests
python -m pip check
git diff --check
```

PASS: focused 82 tests; full 239 tests, no failures/skips. Existing Tk ThemeChanged
teardown diagnostics remain; unittest reports OK. PASS changed-file compilation
and diff check; pip check reports no broken requirements. Evidence:
startup-before.log, startup-focused.log and startup-full.log. Full suite selected
because shared startup/settings behavior affects endpoint and pair workflows.

## Rebuilt executable and actual restart smoke

Same Python 3.11.5 isolated builder, PyInstaller 6.22.3, hooks 2026.7 and
setuptools 78.1.1. No installations, dependency-pin changes or spec changes.
Original acceptance executable and evidence retained separately.

```powershell
$env:PYINSTALLER_CONFIG_DIR='C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-builder-5292753/pyinstaller-cache'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m PyInstaller --noconfirm --clean --distpath C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-builder-5292753/restoration/dist --workpath C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-builder-5292753/restoration/work TraceSync.spec
```

PASS build; log restoration-build.log. Artifact:
`C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-builder-5292753/restoration/dist/TraceSync.exe`.
SHA-256: `88c5ff9ef9f0f4d84f1ae80edaa8e7ec507d885be30aaf2de0cd6ddd564bb419`.
Built from HEAD above plus the uncommitted ui/main_window.py fix, not an exact
clean-commit artifact. External restoration/artifact-manifest.json records source
hashes. Documentation/tests are not bundled by the spec.

PASS actual packaged restart, separately from unit tests: launched with explicit
cwd restoration/smoke and LOCALAPPDATA restoration/smoke/appdata; removed OneDrive
client/tenant variables from child environment. Initially only Local was saved.
Selected restoration/smoke/server using the actual Server Browse dialog; inspected
the disposable settings.json to confirm persisted server_folder. Closed through
the window close button, relaunched same executable/cwd/environment. Server field
restored the path (inspected both beginning and end), Local remained populated,
workflow guide offered comparison. Closed normally after verification.

## Remaining gates and boundaries

NOT RUN - OUT OF SCOPE: frozen protected-cache/OneDrive lifecycle and real-account
acceptance; no real token cache accessed or cloud mutations performed. Standard-user
acceptance remains unverified; this session has an elevated token. This narrow
restart check does not establish full packaged acceptance. Create-only restrictions,
unknown-outcome handling, ancestor TOCTOU and post-crash accounting limits unchanged.
No commits, integration, pushes, tags, publication or releases. Historical SFTP and
separate dirty pair-management worktrees preserved. Next: review/checkpoint this fix
only with separate authorization; remaining acceptance gates need their own scope.
