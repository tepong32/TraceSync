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
