# Provider completion validation — 2026-10-21

## Source and scope

Both local provider completion branches start at
`ec009ffb3a06f7218b0e9563f91e96befa5d977a` (accepted Gate B source checkpoint),
descended from saved-folder fix `3996629` and published source v0.15.0 `4ddfd55`.
This report records pre-checkpoint validation. A later user-authorized source-only
preparation checkpoint preserves this patch; no merge, push, tag, executable build
or publication was performed. Tests were not rerun after checkpointing.
Production executables and the accepted safety worktree remain unchanged.

OneDrive work covers saved-pair edit/delete, public build identity, per-user
settings migration, reserved Windows names, personal MSAL account binding,
reviewed backup materialization, download modification time and Windows temporary
cleanup. Cloud replacement stays disabled. Google selectively imports its adapter
from `8cec558` onto this foundation and adds standard desktop PKCE, account-scoped
Windows credentials, native folder/pair setup and reviewed downloads with history.
Legacy provider-side credential reopening and duplicate folder browsing were
removed; GoogleDriveAuth/GoogleDriveSetupService own those responsibilities.
Google upload and replacement stay disabled. See PROVIDER_COMPLETION.md.

## Reproduced results

| Branch | Focused suite | Full suite | Compilation | Diff |
| --- | --- | --- | --- | --- |
| codex/onedrive-provider-completion | PASS — 120 tests | PASS — 285 tests, 17.415s | PASS — 104 Python files and spec | PASS — git diff --check |
| codex/google-drive-provider-completion | PASS — 164 tests | PASS — 329 tests, 19.034s | PASS — 114 Python files and spec | PASS — git diff --check |

Existing builder Python (3.11.5, unchanged):
`C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-builder-5292753/venv/Scripts/python.exe`.
Google SDK isolated Python (3.11.5):
`C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-cloud-tests-20261021/Scripts/python.exe`.
The latter contains the reviewed Google pins and existing MSAL runtime pins;
`python -m pip check` passes. No existing environment was modified. Exact installed
versions are retained in the external freeze. Repository build-tool pins were not
modernized; a future authorized build must use the documented isolated toolchain.

Run from the corresponding worktree, assigning `$py` to its exact interpreter:

```powershell
& $py -m unittest tests.test_onedrive_auth tests.test_onedrive_setup tests.test_onedrive_setup_dialog tests.test_onedrive_main_window tests.test_onedrive_transfer tests.test_onedrive_backup_content tests.test_onedrive_windows_names tests.test_cache_acceptance tests.test_provider_config tests.test_settings_storage tests.test_onedrive_timestamps tests.test_sync_summary_notes -q
& $py -m unittest discover -s tests -q
```

For Google's focused command, insert these modules before `-q`:
`tests.test_google_drive_auth tests.test_google_drive_setup tests.test_google_drive_provider tests.test_google_drive_transfer tests.test_google_drive_safety tests.test_google_drive_dialog`.
The complete suite is warranted by shared auth, settings, transfer staging and UI
changes. Compilation used `compile(path.read_bytes(), str(path), 'exec')` for every
Python source and TraceSync.spec, without building or generating binaries.

Logs and exact snapshot evidence:
`C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-provider-completion-20261021`.
Use `onedrive-timestamp-ui-focused.log`, `google-timestamp-ui-focused.log`,
`onedrive-timestamp-ui-full.log`, `google-timestamp-ui-full.log`,
`static-checks.json`, `preservation.json`, and the final snapshot manifests/patches.
Tk teardown emits historical ThemeChanged messages; unittest exits 0 and reports
OK. Earlier Google environment runs failed because MSAL dependencies were missing;
those logs are retained and the isolated environment was corrected before these
successful runs. Do not report the initial run as a pass.

## Evidence that exercises actual installed libraries/Windows

- Real MSAL SerializableTokenCache/PublicClientApplication account representation
  reproduces the personal tenant UUID versus consumers-realm binding defect. The
  regression failed before correction; the fixed selector still requires unique
  local identity and, when returned, the exact home ID. No discovery or sign-in.
- Google SDK generates a real S256 PKCE challenge offline. A new regression failed
  before bounded AuthorizedHttp setup and passes with the real transport timeout
  set to 120 seconds; no network is used by that test. Loopback login is limited to
  300 seconds. These are per-request/flow bounds, not total-job deadlines.
- Real Windows Credential Manager writes synthetic data in a new randomized
  `TraceSync.Acceptance.Google.<UUID>` namespace; a second Python process reads it,
  and the parent removes the entry and verifies absence. No production credential
  enumeration, real tokens or account use. This is source-mode evidence in the
  current session, not frozen or standard-user acceptance.
- Real Windows sharing locks reproduced cleanup failures. Ignoring errors only
  while cleaning owned temporary directories prevents a completed copy from being
  falsely recorded as failed. Read-only verified OneDrive backup bytes are stored
  durably through the actual local JsonBackupStore. Remote I/O uses fake Graph.
  Locked disposable temporary data can remain; no automatic recovery is claimed.

## Offline adversarial coverage

| Boundary | Evidence | Result and limit |
| --- | --- | --- |
| Wrong/ambiguous account, renewed identity, client/scope/token endpoint mismatch | test_onedrive_auth, test_google_drive_auth | Exact identity checked; no first-account/email fallback or implicit browser renewal. Live claims still need acceptance. |
| Pair editing/deletion, stale definitions, local repair, duplicate names | test_onedrive_setup/dialog, test_google_drive_setup/dialog | Definitions only; files and sign-in retained on delete. Stored local paths are absolute. Settings writes are not cross-process compare-and-swap. |
| Destination appears after confirmation; forged replacement | test_onedrive_transfer, test_google_drive_transfer/safety and shared transfer tests | Create-only protection remains at execution, existing files preserved; no cloud overwrite capability enabled. |
| Changed source, ancestor identity/link, incomplete listings, ambiguous names | test_google_drive_provider/safety, test_onedrive_transfer | Refuses incomplete/changed evidence. Checks are not atomic locks; external moves can still race. |
| Empty uploads, created parents, lost/malformed completion, permission/unknown distinction, partial history/cancel | test_onedrive_transfer and existing runner suites | Prior create-only contract retained; no blind retry. Post-crash remote folder accounting remains unresolved. |
| Google empty/nonempty bytes, forged replacement, cancellation and post-copy comparison | test_google_drive_transfer/provider | Real local publication/history with injected SDK media transport; reviewed modification time retained. No live Drive evidence. |
| Protected persistence failure/logging | test_google_drive_auth and existing Gate B tests | Sanitized failures, no selected plaintext fallback, callback URLs suppressed. Injected failures do not prove all native failure modes. |
| Standalone public identity/settings | test_provider_config, test_settings_storage, test_cache_acceptance | Public fields only, missing build IDs refused, per-user atomic settings and nondestructive legacy fallback. Spec execution is mocked, not packaging acceptance. |

## Preservation and remaining gates

`preservation.json` compares HEAD/status/raw dirty file hashes with the earlier
checkpoint snapshot: canonical SFTP, canonical Version Manager and original pair
management are unchanged. Gate B, old Google and Version Manager checkpoint
worktrees are clean at their expected commits. New provider indexes are empty.
Master and origin/master remain `4ddfd55e2874fecb76e6cf1e054fc971b03bbb41`.
Retained production SHA-256 remains
`95b3553265a23e4018b9e03a88525b5f74f4692a008e85f121d6a293a719dbbe`;
Gate B artifact remains
`53b82f286ccb4e8bbc73257046858f523c7f886e0ace8efb4cc5ef58e04064ad`.
No remote state was changed by this work; no new fetch was needed for these checks.

NOT RUN — ENVIRONMENTAL: real-account lifecycle (registration/disposable sign-in
not supplied), source cloud mutation, real permission/revocation/quota behavior.
NOT RUN — OUT OF SCOPE: new frozen packaging, frozen Google credential persistence,
non-elevated cloud acceptance, publication. Historical Gate A/B do not prove these.
Engineering remains: safe OneDrive conditional replacement/recovery; Google upload
and replacement identity/name/write-consent contract. Live OneDrive timestamp
precision/round-trip acceptance is a separate account-dependent gate. Dropbox is later candidate work; SFTP remains preserved/parked.
Owner inputs and exact portal/source paths are in CLOUD_OWNER_SETUP.md. Public IDs
alone do not finish the synchronization objective. Keep TOCTOU, local overwrite
and post-crash folder-accounting limitations visible. No completion claim yet.

## Upload client time and visible copy notes

OneDrive now reads fileSystemInfo.lastModifiedDateTime before the service time,
retains eTag for change detection, supplies reviewed client time in nonempty upload
session metadata, and conditionally updates the confirmed new item ID for empty
uploads using the returned eTag. Missing versions prevent this metadata mutation.
There is no metadata update by path, content replacement or retry. RFC3339 helpers
round once at 100 ns precision; native Windows file stat round trips are tested.

Six tests in test_onedrive_timestamps cover native precision, timezone parsing,
client/service distinction, empty/nonempty round-trip comparisons, and missing
version, permission, concurrent edit, lost response and malformed metadata cases.
The two upload regressions fail against the baseline ec009ff provider loaded into
an isolated module, without changing the worktree; see
onedrive-timestamps-baseline-red.log. The current targeted transfer/backup/time
suite passes 44 tests on both environments. A temporary test-fixture discovery
issue was corrected before these results; it was not a production failure.

After positively confirmed byte creation, metadata failure is a copied outcome
with a durable warning. Three native Tk tests verify those notes appear in an
amber, read-only, scrollable summary without inflating failure counts or
truncating later notes; ordinary copies retain the compact summary. No provider
capability or replacement restriction was relaxed. Packaged UI and live server
precision/metadata responses still require acceptance.

The implementation follows the documented client filesystem facet and conditional
metadata API, checked 2026-10-21:
- https://learn.microsoft.com/en-us/graph/api/resources/filesysteminfo?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/resources/driveitemuploadableproperties?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/driveitem-update?view=graph-rest-1.0

## OAuth timeout hardening follow-up — 2026-10-22

Integrated reviewed commits `b1163b0` and `4d99a04` from
`codex/google-oauth-timeout-hardening`; final source HEAD is
`4d99a0411d87e1a18990f595e45e1ccc91bae399`. The patch is limited to bounded
Google credential refresh (`Request(timeout=120)`) and its focused regression test.

- PASS: reviewed two-commit diff touches only `core/google_drive_auth.py` and
  `tests/test_google_drive_auth.py`.
- PASS: `git diff --check HEAD~2..HEAD` (exit 0).
- NOT RUN — ENVIRONMENTAL: focused and full unittest suites, compilation, and
  `pip check`. The documented isolated interpreter
  `C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-cloud-tests-20261021/Scripts/python.exe`
  is absent. The documented builder interpreter is absent too. System Python 3.13
  was not substituted for the documented Python 3.11.5 environments.
- NOT RUN — ENVIRONMENTAL: Windows executable candidate build. Validation did not
  pass, and the documented isolated builder is unavailable. No build was attempted.
- Local `provider_config.json` was created with the public Google Desktop client ID;
  `.gitignore` ignores it and Git does not track it.

Historical 329-test and earlier compilation results above predate these commits and
are not validation results for this follow-up. No live authentication, remote
writes, release, or publication was performed.
## Google Drive test environment baseline — 2026-10-22

Source HEAD: `4d99a0411d87e1a18990f595e45e1ccc91bae399`. A new isolated Windows AMD64 Python 3.11.9 test environment was established at
`C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/test-envs/google-drive-completion-py3119-20261022`. This is a new baseline, not a reproduction of the unavailable Python 3.11.5 environment.

Dependency scope is source runtime plus the complete offline test suite. Eight direct requirements are hash-locked: google-api-python-client 2.201.0, google-auth-httplib2 0.4.4, google-auth-oauthlib 1.5.0, keyring 25.7.0, msal 1.39.0, msal-extensions 1.3.1, pywin32-ctypes 0.2.3, and requests 2.34.2. All project-defined pins are unchanged from requirements.txt; google-auth-httplib2 is separately pinned because application code imports it directly. Tests use standard-library unittest; no separate test framework package was needed. Thirty-seven direct and transitive distributions are pinned with verified SHA-256 wheel hashes in the external lock. PyInstaller and builder packages were excluded. Python 3.11.9 ensurepip supplied pip 24.0 and setuptools 65.5.0; setuptools was then removed from this test environment. Bootstrap wheel hashes and all environment metadata are recorded externally.

Commands and results on the final test environment:

- PASS: `py -3.11 -m venv <environment>\venv`; created Python 3.11.9 x64 venv.
- PASS: install from `https://pypi.org/simple` using `--only-binary=:all: --require-hashes -r requirements-google-test.lock`; all 37 locked distribution hashes were accepted.
- PASS: `python -m pip check` — “No broken requirements found.” (exit 0).
- PASS: `python -m unittest tests.test_google_drive_auth -v` — 13 tests, including bounded refresh regression (exit 0).
- PASS: `python -m unittest discover -s tests -q` — 330 tests, `OK` (exit 0). Tk emits known `ThemeChanged` teardown diagnostics after destroyed widgets; they did not affect the suite result.
- PASS: compilation of all 114 Python sources and `TraceSync.spec` (exit 0). The first inline compile attempt failed due PowerShell quote stripping (exit 1); rerunning via the external `compile_sources.py` script passed.
- PASS: `git diff --check` and `git diff --check HEAD~2..HEAD` (exit 0).

External environment files include `requirements-google-test.in`, the hash lock, pip resolution/install reports, `installed-packages.json`, `environment.json`, `bootstrap-wheels.json`, `ENVIRONMENT.md`, and per-command JSON logs. No app credentials or tokens are stored there. This task did not build with PyInstaller or perform live authentication/Drive acceptance.

## Windows builder environment baseline — 2026-10-22

Source HEAD: `4d99a0411d87e1a18990f595e45e1ccc91bae399`. A separate Windows AMD64 builder venv is established at
`C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/venv`.
It uses Python 3.11.9 and pip 24.0. This is a new baseline, not a reproduction
of the missing Python 3.11.5 builder.

Builder tools are PyInstaller 6.22.3, pyinstaller-hooks-contrib 2026.7 and
setuptools 78.1.1. These match versions recorded for earlier successful project
builds. Repository `requirements.txt` remains unchanged at PyInstaller 6.20.0
and hooks 2026.6; the external builder input overrides those tool versions only.
PyInstaller 6.22.3 includes the 6.22.1 fix for
[GHSA-9fxf-4qw3-ghmr](https://github.com/pyinstaller/pyinstaller/security/advisories/GHSA-9fxf-4qw3-ghmr).
The existing Google/OneDrive runtime pins are shared with the test environment;
all 37 overlapping locked distributions match exact versions. The builder lock
adds nine runtime/UI/build packages. Its 46 Windows binary distributions have
verified SHA-256 hashes; lock SHA-256 is
`8a728ab9e605567094ee4737365e0ddecd003c7e3dd6bf6c3715a64681e678b9`.
The direct input, full lock, resolver/install reports, installed package list,
version comparison, and command results are stored under the external builder
directory in `ENVIRONMENT.md`.

- PASS: hash-locked installation from `https://pypi.org/simple`, binary wheels
  only; 46 distributions installed (exit 0).
- PASS: lock inventory comparison; all 46 versions match, with only pip 24.0
  outside the lock as the Python ensurepip bootstrap.
- PASS: builder `pip check` (no broken requirements, exit 0); exact PyInstaller,
  hooks, and setuptools versions verified.
- PASS: minimal one-file PyInstaller capability smoke build and execution
  (both exit 0); output is outside the repository.
- PASS: existing Python 3.11.9 test environment remains unchanged: lock SHA-256
  `7f1aaecd7a66773e62bd040678640163da242b6830ae94d6238e3e041406fc9a`, 38
  installed packages, and `pip check` exit 0.

At the builder-environment setup checkpoint, `TraceSync.spec` was inspected but
not invoked. It analyzes `main.py`, includes assets, `VERSION`, and generated
public provider configuration, and declares the Windows keyring backend as a
hidden import. The smoke build did not validate the actual spec, its optional
UPX behavior, frozen credentials, or provider acceptance. The subsequent
candidate build and its bounded launch check are recorded below. No live
authentication, Drive operation, release, or publication was performed. Tk
teardown diagnostics from the test suite remain recorded; their cause has not
been established.

## Google Drive Windows candidate — 2026-10-22

Source branch `codex/google-drive-provider-completion`, HEAD
`4d99a0411d87e1a18990f595e45e1ccc91bae399`; only the existing handoff and
validation documentation were modified. `git diff --check` passed. The ignored
root `provider_config.json` was read without displaying or editing it. Its
public Google client ID was passed only in the build process environment with
`TRACESYNC_BUILD_PROVIDERS=google_drive`; the generated and archived
`provider_config.json` was compared by equality to the local public config.

Working directory: Google completion worktree. Exact command:

```powershell
C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --distpath C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/candidate-google-drive-4d99a0411d87-20261022/dist --workpath C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/candidate-google-drive-4d99a0411d87-20261022/work TraceSync.spec
```

The isolated `PYINSTALLER_CONFIG_DIR` pointed to the candidate directory;
`PYTHONDONTWRITEBYTECODE=1`. The public client ID value is not recorded in
command logs. Python was 3.11.9, PyInstaller 6.22.3, hooks 2026.7, setuptools
78.1.1, pip 24.0. Build exit 0 in 38.406 seconds. UPX was not installed.
Although the spec sets `upx=True`, this PyInstaller version disables UPX when
it is unavailable; no spec change or extra tool installation was made.

Candidate:
`C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/candidate-google-drive-4d99a0411d87-20261022/dist/TraceSync.exe`.
Size 38,731,475 bytes; SHA-256
`1391ce7f07f82704720695d9f74952a46c4facb2961b9c75f35aef98ee6efff6`. It is
outside the repository. `pyi-archive_viewer` and `CArchiveReader` confirmed the
Google auth, setup, provider, OAuth flow, Google transport, Windows keyring
backend and `win32ctypes` credential fallback modules. `VERSION`, the icon, and
`provider_config.json` are present; the archived public config matches the local
Google ID. No settings, token, token-cache or credential data files were found.
Google API discovery JSON documents are static SDK package data; `msal.token_cache`
entries are Python modules, not user token files.

Build output contains two WARNING lines: PyInstaller could not resolve hidden
imports `pycparser.lextab` and `pycparser.yacctab` from delayed `cffi.cparser`
imports. Those table files are absent from the installed `pycparser` package.
The Analysis `warn-TraceSync.txt` has 101 unresolved import entries, including
platform-specific and optional modules (for example POSIX modules and optional
SDK integrations). Required Google and Windows fallback modules listed above
are present. These warnings were preserved, not suppressed; frozen cloud/auth
paths were not exercised. No missing declared spec data files were observed.

PASS: launched the candidate as a non-elevated process under isolated
`APPDATA`, `LOCALAPPDATA`, `USERPROFILE`, and `TEMP` directories. The visible,
responding window was `TraceSync v0.15.0`. `CloseMainWindow` closed the GUI, the
one-file bootstrap exited 0, and no candidate process remained. Settings/history
side effects stayed under the candidate's isolated launch profile (one empty
history lock file remained). No Google sign-in, browser flow, token access,
Drive listing or Drive mutation was performed. Startup and close passing do not
establish OAuth or Drive acceptance.

The full manifest, build stdout/stderr, `warn-TraceSync.txt`, archive listing,
module/data checks, launch result and isolated profile are under the candidate
directory. The Python 3.11.9 test lock remains SHA-256
`7f1aaecd7a66773e62bd040678640163da242b6830ae94d6238e3e041406fc9a`, its 38
package inventory is unchanged, and test-environment `pip check` still passes.
No merge, release, tag, publication or remote write occurred.

## Live Google acceptance preflight — 2026-10-22

No live sign-in was started. The candidate path/hash supplied for this preflight
did not match the retained artifact path/hash: the supplied path is absent. The
retained candidate is the `dist/TraceSync.exe` under
`C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/candidate-google-drive-4d99a0411d87-20261022`,
and its verified SHA-256 is
`1391ce7f07f82704720695d9f74952a46c4facb2961b9c75f35aef98ee6efff6`, matching
the build evidence above. The ignored local public client ID was checked without
displaying it and matches the ID included in the candidate.

Source review confirms standard desktop loopback OAuth at 127.0.0.1 on an
ephemeral port, browser launch, a 300-second callback wait, SDK-generated S256
PKCE, and SDK state validation when parsing the callback response. The only
requested Drive scope is `drive.readonly`. Consent therefore authorizes reading
the account's Drive files; the selected folder restricts TraceSync's workflow,
not the OAuth grant itself. The callback logger is suppressed during sign-in.
Credential JSON is stored in Windows Credential Manager under an app/account
derived target; no plaintext fallback is used. The app's Disconnect action
removes this saved local sign-in, but does not revoke Google's grant.

An environment-variable-only profile does not isolate Credential Manager.
Acceptance should use a dedicated Windows user profile (separate Windows user
credential vault) and a dedicated Google OAuth test account containing only
synthetic files. Settings/history are per-profile; history can retain account,
folder, local-path and synthetic relative filenames. Test only the intended
folder, save a pair, compare, and copy one selected synthetic Drive file to a
new local destination through `Copy from Server -> Local`. Do not use the local
to server action. Review history, then use Google Drive setup's Disconnect
action; separately revoke the app grant in that test Google account if desired.
After exiting, remove only the disposable Windows profile's TraceSync settings,
history and temporary data. No existing Windows user's credential store should
be inspected or touched. This preflight identifies the required isolation; live
acceptance remains pending user operation and has not been claimed.

### User acceptance checklist — verified artifact, not yet run

- Candidate: `C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/candidate-google-drive-4d99a0411d87-20261022/dist/TraceSync.exe`.
  Independently rechecked SHA-256: `1391ce7f07f82704720695d9f74952a46c4facb2961b9c75f35aef98ee6efff6`.
  Source: `4d99a0411d87e1a18990f595e45e1ccc91bae399`, branch
  `codex/google-drive-provider-completion`; Python 3.11.9, PyInstaller 6.22.3,
  hooks 2026.7, setuptools 78.1.1. The alternate path/hash in the request is
  absent/mismatched; do not use it.
- Use a dedicated non-elevated Windows user, an OAuth test account holding only
  synthetic Drive items, one disposable Drive folder, and a new empty local
  destination inside that Windows profile. APPDATA override alone does not
  isolate that user's Windows Credential Manager.
- Launch the verified executable. Select **Google Drive setup...** →
  **Connect account**. Confirm the browser shows the designated test account and
  requests only read-only Drive access. Source calls standard loopback OAuth on
  `127.0.0.1` with an ephemeral port, system browser, 300-second callback,
  S256 PKCE, SDK state validation and callback URL log filtering.
- In **Google Drive Folder Pair**, select the disposable folder, choose the empty
  local destination and synthetic pair name, then **Save pair with current cloud
  folder**. Choose **Use saved pair**. Compare; confirm only expected synthetic
  files appear. Select one server-only item and use **Copy from Server -> Local**.
  The confirmation should show one Create, zero Replace existing, and the chosen
  synthetic filename. Start it only after checking those values. Compare local
  byte length and SHA-256 against the locally held synthetic source fixture;
  inspect history for outcome, endpoint and relative filename without exporting
  or sharing account data.
- The UI presents **Copy from Local -> Server**, but source/provider trace shows
  it is disabled for Google: Google `location_for` rejects absent destinations,
  existing destinations are excluded by create-only rules, cloud preview returns
  no items, and the UI gates button availability on a nonempty preview. The job
  runner also requires destination conditional-transfer capabilities that Google
  does not advertise, and Google `transfer_from` always raises unsupported.
  Thus no upload reaches an API. Existing remote files are not replacement
  targets. No remote delete/mirroring action exists: Google auth/setup/provider
  code uses Drive metadata/list/media reads only; the pair **Delete** removes a
  local saved definition, not Drive content. Any enabled local-to-server button,
  replacement/delete prompt for Drive items, or broader OAuth scope is a stop
  condition. These are source-review findings; live behavior remains untested.
- In setup, select the saved pair and **Disconnect**; confirm it removes this
  device's saved sign-in. The stored credential uses Windows Credential Manager
  (`TraceSync.GoogleDrive.v2`, key derived from client/account IDs). This removes
  only the local token entry, not Google's grant or browser session. Separately
  remove the app grant in the test account's [Google Account linked apps](https://support.google.com/accounts/answer/13533235?hl=en-ST).
  After exit, remove only that test profile's `%APPDATA%\TraceSync`,
  `%LOCALAPPDATA%\TraceSync\history`, `%LOCALAPPDATA%\TraceSync\backups`, and
  any remaining `tracesync-drive-*` temp files under its `%TEMP%`. Remove the
  downloaded synthetic local copy if desired; leave Drive content untouched.
- Record source HEAD, exact executable path/hash, Windows/Python app identity
  context (no personal identifiers in shared evidence), OAuth scope shown,
  folder/pair labels (synthetic), compare result, downloaded size/hash, history
  outcome, exit result, errors and non-sensitive logs. Never record tokens,
  authorization callback URLs, secrets or real personal filenames. No live test
  has been performed as part of this preflight.

## Sanitized OAuth failure diagnostics — 2026-10-22

Prepared on branch `codex/google-drive-provider-completion`, source base
`4d99a0411d87e1a18990f595e45e1ccc91bae399`. The existing handoff and validation
documentation already had local changes before this patch; those entries were
preserved. This patch changes only `core/google_drive_auth.py`,
`core/google_drive_setup_service.py`, `tests/test_google_drive_auth.py`,
`tests/test_google_drive_setup.py`, and this validation/handoff documentation.

Interactive sign-in now reports fixed, user-safe messages for a Google OAuth
error returned by the loopback callback (including cancellation and invalid
scope), an invalid/incomplete callback, the five-minute no-callback timeout,
local browser/listener/callback failure, token-exchange failure, and unexpected
local failures. Callback state is checked against the state returned when the
SDK constructs the authorization URL; the SDK's own state validation remains in
place. The existing `drive.readonly` scope, Desktop client configuration,
S256 PKCE generation, ephemeral loopback listener, and bounded refresh behavior
are unchanged. Raw callback data and SDK/network exception strings are never
shown or logged. The Google setup service passes through only this dedicated
sanitized diagnostic type; other exceptions remain generic.

- PASS: `python -m unittest tests.test_google_drive_auth -v` — 18 tests, exit 0.
- PASS: `python -m unittest tests.test_google_drive_auth tests.test_google_drive_setup -v`
  — 28 tests, exit 0.
- PASS: `python -m unittest discover -s tests -q` — 336 tests, `OK`, exit 0.
  Existing Tk `ThemeChanged` teardown messages appeared after destroyed widgets;
  they did not affect the result and remain unexplained.
- PASS: compiled 114 Python sources and `TraceSync.spec`, exit 0.
- PASS: test environment `python -m pip check` — no broken requirements, exit 0.
- PASS: `git diff --check`, exit 0.
- NOT RUN — OUT OF SCOPE: live OAuth, TraceSync launch, and Google Cloud checks;
  this task explicitly prohibited them.
- NOT RUN — OUT OF SCOPE: PyInstaller rebuild. The source patch has not been
  packaged, and the retained candidate still represents the previous source.

These offline tests establish diagnostic classification and redaction only; they
do not identify the cause of Google's earlier `unknownerror`. Verify the consent
audience/test-user access and Drive API configuration separately. The patch is
ready for review and a controlled candidate rebuild, but live acceptance should
wait for review of that rebuilt artifact.

## OAuth diagnostic candidate build — 2026-10-22

Built the diagnostic worktree from branch `codex/google-drive-provider-completion`,
HEAD `4d99a0411d87e1a18990f595e45e1ccc91bae399`, with a dirty working-tree patch.
The exact build-time patch is preserved externally as
`source-working-tree.patch`, SHA-256
`e9d105af4a92ed22b04717162febe6f558e5badf6b4f2538f90637c2ee52fd0b` (41,782
bytes). It covers the six tracked files listed in the candidate manifest; it
includes the diagnostics implementation and the previously pending handoff and
validation text. No ignored configuration or credentials are part of this patch.

The existing hash-locked builder was reused without package installation or
upgrade: Windows AMD64 Python 3.11.9, pip 24.0, PyInstaller 6.22.3,
pyinstaller-hooks-contrib 2026.7, setuptools 78.1.1. The 46-package lock
verifier and `pip check` passed; lock SHA-256 remains
`8a728ab9e605567094ee4737365e0ddecd003c7e3dd6bf6c3715a64681e678b9`.

Exact command, run from the Google completion worktree:

```powershell
C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/venv/Scripts/python.exe -m PyInstaller --noconfirm --clean --distpath C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/candidate-google-oauth-diagnostics-4d99a0411d87-20261022/dist --workpath C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/candidate-google-oauth-diagnostics-4d99a0411d87-20261022/work TraceSync.spec
```

Build exit 0 in 64.521 seconds. Candidate:
`C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/candidate-google-oauth-diagnostics-4d99a0411d87-20261022/dist/TraceSync.exe`.
Size 38,731,979 bytes; independently verified SHA-256
`65c0e21f1327c51dbe3b7e1e410d3be0801b6de00f550141274ebdecf998a6cb`. The
external `build-manifest.json` and `artifact-verification.json` identify this
path, hash, source HEAD and working-tree patch fingerprint. PowerShell
`Get-FileHash` independently agrees with both records. The ignored local public
provider configuration matches the archived config and is not recorded in the
manifest or logs. Both records, build logs, archive inspections and the saved
working-tree patch are under
`C:/Users/TEMP.MARIZ/AppData/Local/TraceSync/builder-envs/google-drive-completion-py3119-20261022/candidate-google-oauth-diagnostics-4d99a0411d87-20261022/`.

- PASS: candidate exists, is non-empty and outside the repository; archive
  contains Google auth/setup/provider, OAuth transport and Windows credential
  backend modules, required assets, VERSION and provider configuration.
- PASS: frozen bytecode contains the new sanitized diagnostic messages and the
  `drive.readonly` scope. Archive data-name verification found no credential,
  token, settings or user-cache data files. The archive listing also names SDK
  Python modules containing `token_cache`/`refresh_token`; these are code modules,
  not persisted user data.
- PASS: archived public provider configuration matches the ignored local config.
- PASS: manifest SHA-256, artifact-verification SHA-256 and independent hash
  agree. The artifact remains outside Git.
- WARNING: PyInstaller emitted the same two unresolved optional hidden imports,
  `pycparser.lextab` and `pycparser.yacctab`. Its analysis warning file has 101
  missing-module entries, including platform-specific/optional imports; all
  required Google and Windows credential modules checked above are present.
  UPX is unavailable, so the spec's optional `upx=True` is not applied.
- NOT RUN — OUT OF SCOPE: no executable launch, interactive UI, OAuth, Drive
  access or mutation was performed. This candidate is not live OAuth acceptance.

Validation was repeated from the actual Google completion worktree after review:

- PASS: `python -m unittest tests.test_google_drive_auth -v` — 18 tests, exit 0.
- PASS: auth plus setup tests — 28 tests, exit 0.
- PASS: full suite — 336 tests, `OK`, exit 0. Existing Tk `ThemeChanged`
  teardown diagnostics appeared and remain unexplained.
- PASS: 114 Python source files and `TraceSync.spec` compiled; test environment
  `pip check` and `git diff --check` passed.
