# Windows OneDrive dependency environment

## Current scope

Safety implementation checkpoint: 0de6aa23987a5661b0578ea40b83f5082abedb32,
parent 4ddfd55e2874fecb76e6cf1e054fc971b03bbb41, branch
codex/onedrive-create-safety-audit. The safety patch is committed locally, not
merged or published. This dependent requirements/documentation change is uncommitted.
No synchronization/auth/cache/provider logic or PyInstaller spec is changed.

requirements.txt now adds exactly msal==1.39.0, msal-extensions==1.3.1 and
requests==2.34.2 to the existing pins. No unrelated upgrade or transitive pin was
added. The previously validated external candidate manifest contains the same
package/version entries as the resulting requirements.txt.

## Dependency rationale

| Package | Role and compatibility evidence |
| --- | --- |
| msal 1.39.0 | Public-client authentication; Python >=3.9; Requests >=2,<3; PyJWT[crypto] >=1,<3; cryptography >=2.5,<51 |
| msal-extensions 1.3.1 | Encrypted persistence/file locking; Python >=3.9; MSAL >=1.29,<2 |
| requests 2.34.2 | Graph transport; Python >=3.10; urllib3, certifi, charset-normalizer, idna are declared by Requests |

Sources: [MSAL metadata](https://pypi.org/project/msal/1.39.0/),
[Extensions metadata](https://pypi.org/project/msal-extensions/1.3.1/),
[Requests metadata](https://pypi.org/project/requests/2.34.2/).
Installed metadata and pip check agree. Python 3.11.5 AMD64 is the validated
interpreter; other Python/Windows combinations are not accepted by these results.
MSAL already declares cryptography/PyJWT and Requests declares its HTTP/TLS
requirements. They were not previously listed directly, but normal dependency
resolution covers them; duplicating their pins here is unnecessary. Broker and
portalocker extras are not required by this code. Extensions has a built-in
file-lock fallback when portalocker is absent.

Direct pins are not a complete reproducible transitive lock. Preserve a resolved
manifest and wheel hashes per acceptance environment. Resolve transitive versions
again only deliberately, and record any differences. Do not copy test-only tokens,
cache files or private configuration into environment artifacts.

## Isolated Windows setup

Do not install into the established project environment. From the worktree root,
use a fresh external path (inspect it first; do not overwrite an existing venv):

```powershell
$envRoot = 'C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-onedrive-test-NEW-RUN'
& C:/Users/Administrator/Desktop/GH/TraceSync/.venv/Scripts/python.exe -m venv "$envRoot/venv"
$testPython = "$envRoot/venv/Scripts/python.exe"
& $testPython -m pip --isolated --disable-pip-version-check install --index-url https://pypi.org/simple --only-binary=:all: --report "$envRoot/install-report.json" -r requirements.txt
& $testPython -m pip check
& $testPython -m pip freeze --all | Out-File -Encoding utf8 "$envRoot/resolved-all.txt"
& $testPython -B -m unittest tests.test_onedrive_transfer tests.test_synchronization tests.test_onedrive_main_window -q
& $testPython -B -m unittest discover -s tests
& $testPython -m compileall -q core models ui tests
git diff --check
```

These are offline-regression preparation commands, not an approved release-tool
recipe. Check each exit code before proceeding. Use reviewed bootstrap versions
before any acceptance build; the security findings below must not be ignored.
Binary-only installation avoids source-build paths, but is not a blanket security
guarantee. For exact reproduction, reuse the reviewed resolved pins and matching
wheel hashes, and record Python, pip/setuptools, OS/architecture and requirements
SHA-256. Repository requirements alone leave transitive selection flexible.

Installing packages neither creates an app registration nor enables sign-in by
itself. Future live acceptance needs a separately authorized public-client
registration accepting personal accounts, appropriate desktop redirect settings,
TRACESYNC_ONEDRIVE_CLIENT_ID and the intended consumers authority, disposable
accounts/test folders, and an isolated Windows/browser profile. Do not use a client
secret or put credentials in settings, manifests or logs. Do not launch sign-in or
transfer operations merely to validate installation.

Settings are relative to the working directory; use an isolated writable launch
directory for later manual runs. History and cache use user-profile storage rather
than _MEIPASS. Isolate LOCALAPPDATA for acceptance and isolate browser sign-in too.
Never inspect or manipulate a real user's token cache to prepare tests.

## Actual validation

Reused external environment:
C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-acceptance-0de6aa2-20261018/venv

The resulting repository requirements were installed with that interpreter using
the install command above (external cache-dir and integration-install-report.json).
All dependencies were already satisfied from the prior clean candidate install.
No packages were added to the established project environment; its three cloud
packages remain absent. This environment has Python 3.11.5, pip 23.2.1 and
setuptools 65.5.0. Those bootstrap versions are recorded evidence, not security approval.

PASS: pip check (no broken requirements).
PASS: focused command above, 51 tests, no failures/skips.
PASS: full command above, 233 tests, no failures/skips.
PASS: compilation and git diff --check. Existing Tk ThemeChanged teardown
diagnostics persist, with unittest OK. Full suite selected because runtime
requirements change the environment used by auth/shared UI tests.

Logs outside the repository: integration-install.log, integration-focused.log,
integration-full.log, integration-install-report.json. Resolved manifests and the
prior install-report.json (with wheel hashes) are alongside the venv. No environment
artifact, credentials, generated executable or cache is committed to this repository.

## Material build-tool findings

| Component | Finding and required follow-up |
| --- | --- |
| Existing PyInstaller 6.20.0 | In affected range <6.22.1 of GHSA-9fxf-4qw3-ghmr. The advisory concerns privileged onefile executables and spoofed inherited environment variables. Current spec does not request elevation; that does not approve the toolchain for privileged use. Review a patched version and compatible hooks before authorizing an acceptance/release build. |
| Bootstrap setuptools 65.5.0 | In affected range of GHSA-5rjg-fvgr-3xxf; PackageIndex download path traversal fixed in 78.1.1. Legacy source/download tooling is the relevant path; binary-only pip validation here does not test or exercise that workflow. Do not treat this bootstrap as approved release tooling. |
| Bootstrap pip 23.2.1 | Old inherited bootstrap, not pinned by the repository. Select/review a maintained compatible installer for the future build environment; no exhaustive vulnerability certification was performed. |

Primary evidence:
[PyInstaller advisory](https://github.com/pyinstaller/pyinstaller/security/advisories/GHSA-9fxf-4qw3-ghmr),
[setuptools advisory](https://github.com/pypa/setuptools/security/advisories/GHSA-5rjg-fvgr-3xxf).
The smallest next toolchain task is a targeted patched-PyInstaller/hooks and
bootstrap review. Existing pins were intentionally preserved in this runtime-only
integration. This report is a focused material-advisory check, not a complete
security audit of all dependencies. No PyInstaller analysis or executable build
was necessary or performed here.

## Acceptance boundaries

Offline tests and package installation do not pass real-account, Windows protected
cache, or packaged-executable acceptance. All three gates remain outstanding.
Retain create-only transfers, explicit review/confirmation, exact account matching,
no blind retry and honest unknown/partial history. Ancestor TOCTOU and incomplete
post-crash folder accounting remain documented in ONEDRIVE_CREATE_VALIDATION.md.
No automatic sync, mirroring, replacements or provider expansion is introduced.


## Subsequent isolated builder and startup-fix evidence

The dependency validation and security assessment above are historical. An
external builder was subsequently authorized with PyInstaller 6.22.3, hooks
2026.7 and setuptools 78.1.1, leaving repository pins unchanged. It built and
smoke-tested a local acceptance executable, finding a saved Server restoration
defect. The uncommitted fix and rebuilt packaged restart PASS are documented in
[SAVED_FOLDER_VALIDATION.md](SAVED_FOLDER_VALIDATION.md). Frozen cloud/cache and
standard-user acceptance remain open; no binary publication is authorized.

## Current acceptance evidence

The restoration fix was committed as 3996629. A clean rebuild with the same
isolated toolchain produced the public local acceptance artifact
95b3553265a23e4018b9e03a88525b5f74f4692a008e85f121d6a293a719dbbe.
Gate A passed with directly verified non-elevated Medium execution and user-reported
local workflow checks. The uncommitted acceptance-only diagnostic then passed
Gate B in eight separate frozen processes under test normal user: genuine DPAPI
round trip and injected/real failure cases are distinguished in
[GATE_B_VALIDATION.md](GATE_B_VALIDATION.md). Production spec, runtime pins and
production artifact remain unchanged. Real-account lifecycle and eventual full
production cloud acceptance remain open; no publication is authorized.
