# Frozen protected-cache acceptance diagnostic

## Identity and scope

Base: 3996629a9cce7a7421fe000d1008a60c5dc430b6 on
codex/onedrive-create-safety-audit; clean source and expected production artifact
verified before implementing this uncommitted diagnostic. Production artifact:
C:/Users/Public/Documents/TraceSync-Gate-A-3996629/TraceSync.exe
SHA-256: 95b3553265a23e4018b9e03a88525b5f74f4692a008e85f121d6a293a719dbbe.

Gate A: both frozen processes directly verified as test normal user, session 2,
non-elevated, Medium integrity RID 8192; user reported startup, folder restoration,
saved pairs and local copying/replacement working. That is not cloud replacement
acceptance. The original 88c5ff9e restoration build is historical; current artifact
was rebuilt from clean 3996629. Retained older/current Python archives match, with
only base_library.zip entry ordering different in the compared package payloads.

Production main.py, TraceSync.spec, requirements and authentication/sync logic
remain unchanged. This is a distinct acceptance artifact, not a production update.

## Implementation

- acceptance/cache_runtime_hook.py always exits before main.py; no ordinary mode.
- acceptance/cache_support.py requires an explicit canonical UUID-named direct
  child of the current user's TEMP, rejects traversal/reparse points, and requires
  a fresh directory for write or matching marker for subsequent cases. No cleanup
  or adoption of existing case directories. Token APIs require non-elevated Medium.
- acceptance/cache_diagnostic.py uses the actual OneDriveTokenStore with explicit
  cache paths and synthetic account entries, never tokens. No default cache access.
  Real locked MSAL modify/search APIs perform the round trip. Internal persistence
  type inspection is diagnostic evidence, not a new production dependency.
- An audit hook rejects socket, process/browser launch events; MSAL client
  construction and plaintext FilePersistence.save are separately blocked. These
  guards apply only to the diagnostic process and are not an OS security sandbox.
- Failure output contains fixed categories, case names and process identity, never
  raw exception messages, tracebacks, cache content or command-line arguments.
- scripts/build_cache_acceptance.py clones the unchanged spec into a new external
  directory. Differences: absolute input paths, diagnostic runtime hook, distinct
  executable name and console output. It verifies source checkpoint, unchanged
  production inputs and exact approved tool versions. Production spec stays intact.
- acceptance/Run-Cache-Diagnostic.cmd checks the artifact checksum and invokes all
  eight cases as separate processes, with a fresh UUID root and isolated child
  environment. Only sanitized outputs are saved under public Results; synthetic
  cache bytes stay in the test user's TEMP. It never changes system/user environment.

## Commands and executed source validation

Interpreter: C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-builder-5292753/venv/Scripts/python.exe.
Working directory: C:/Users/Administrator/.codex/worktrees/tracesync-onedrive-create-safety.

```powershell
python -B -m unittest tests.test_cache_acceptance tests.test_onedrive_auth -q
python -B -m unittest discover -s tests
git diff --check
python -B scripts/build_cache_acceptance.py --output C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-builder-5292753/gateb-20261019
```

PASS: 19 focused tests; 249 full tests, no failures/skips. Changed Python files
compiled with compile(source, filename, 'exec'); diff check passed. Existing Tk
ThemeChanged teardown diagnostics remain; unittest OK. Logs: gateb-focused.log,
gateb-full.log beneath the external builder. Source tests include real Windows
DPAPI and separate-process round trips but simulate integrity in the CLI regression;
they are explicitly not frozen standard-user evidence.

PASS: build with existing Python 3.11.5 AMD64, PyInstaller 6.22.3, hooks 2026.7,
setuptools 78.1.1. No downloads, installations or upgrades. Production runtime pins
unchanged (MSAL 1.39.0, MSAL Extensions 1.3.1, Requests 2.34.2).
External gateb-20261019/BUILD-INFO.json records source/spec hashes and versions;
gateb-20261019/build.log records the actual build.

Acceptance artifact:
C:/Users/Public/Documents/TraceSync-Gate-B-3996629/TraceSync-Cache-Acceptance.exe
SHA-256: 53b82f286ccb4e8bbc73257046858f523c7f886e0ace8efb4cc5ef58e04064ad.
Source identity: base commit above plus the uncommitted diagnostic files. It is not
the exact production binary; results apply to this acceptance-only build.

PASS frozen refusal checks: missing explicit invocation exits 1 with sanitized
invalid_invocation; elevated Administrator invocation exits 1, reports High RID
12288/elevated true, creates no run directory. No GUI appeared. Evidence:
gateb-20261019/refusal-checks.json. This does not pass DPAPI under a normal user.

## Standard-user execution and case interpretation

From test normal user, run the public Run-Cache-Diagnostic.cmd normally. Each call:

```text
TraceSync-Cache-Acceptance.exe --cache-acceptance --directory <TEMP>/TraceSync-cache-acceptance-<new-UUID> --case <case>
```

| Case | Required evidence | Nature |
| --- | --- | --- |
| write | Actual FilePersistenceWithDataProtection plus PersistedTokenCache; synthetic modify writes disk | Real Windows DPAPI |
| read | New process recovers the exact synthetic account through cache.search | Real Windows DPAPI, same user |
| plaintext | Marker absent in UTF-8, UTF-16LE/BE and UTF-16 bytes | Supporting file observation, not standalone proof of encryption |
| unencrypted | Configuration error before cache construction, no file | Injected negative backend |
| persistence | File used as parent makes initialization fail, no alternate file | Real filesystem failure |
| encryption | Injected protect OSError becomes PersistenceEncryptionError, no file/fallback | Injected negative DPAPI call |
| decryption | Corrupted synthetic DPAPI file raises PersistenceDecryptionError and remains unchanged | Real invalid-data DPAPI failure |
| offline | Socket creation, MSAL client construction, browser open all blocked | Deliberate guard probes, no actual network/auth |

Every successful result includes actual user, PID, elevation=false, integrity RID
8192, run ID and artifact SHA-256. Compare all eight results: same root/hash/user,
separate PIDs, PASS and exit 0. Launcher stops at first failure. Results do not
contain cache data. Directly inspect process tokens too if a process remains open.

PASS: actual standard-user frozen run, independently inspected all eight JSON
records and confirmed the launcher completed with the user. All cases ran as
test normal user with elevated=false, Medium integrity RID 8192 and the exact
diagnostic hash above. Same run ID, eight distinct application PIDs. Write PID
31564 and read PID 22788 establish separate-process recovery. Remaining PIDs:
plaintext 10832, unencrypted 15304, persistence 35752, encryption 14204,
decryption 1708, offline 47424. Each result records its identity via Windows token
APIs before executing; no integrity simulation is used in this frozen build.

Evidence: public Results/f1d5ec46-8b32-491b-a9a9-7ea9182ea49d.jsonl;
external gateb-20261019/standard-user-validation.json checks exact case order,
eight PASS records, distinct PIDs, common run/user/hash and unchanged production
inputs/artifact. Synthetic cache data remains only in that user's disposable
TEMP/TraceSync-cache-acceptance-f1d5ec46-8b32-491b-a9a9-7ea9182ea49d directory.
No cache contents are included in results or this report.

Interpretation: protected backend, cross-process recovery and plaintext-absence
checks passed using genuine frozen Windows persistence. Negative-case PASS means
the expected error was observed with no alternate cache write; it does not mean
the injected backend/error models prove real-account behavior. Audit probes were
rejected before socket/browser/authentication activity could start.

## Limits and boundaries

No real account, OAuth, existing cache, Graph request or cloud mutation is used.
This proves neither live consent/renewal/disconnect nor complete production cloud
acceptance. Diagnostic console/runtime-hook differences must be kept explicit;
future production builds still need their own relevant acceptance. No additional
cross-user/cache-concurrency or full Windows matrix claim follows from these cases.

Create-only cloud restrictions, unknown-outcome handling, ancestor TOCTOU and
post-crash folder-accounting limitations remain unchanged. No commit, merge, push,
tag, signing, release or publication is authorized. Original production artifact,
canonical unfinished SFTP and separate pair-management worktrees are preserved.

## Closure and isolation audit — 2026-10-19

Rechecked the public diagnostic and original builder copy against the full
53b82f28...04064ad hash above. All recorded diagnostic source hashes, generated
temporary-spec hash and delivered launcher match the current files. Independently
parsed the eight original result records: exact case order, eight distinct PIDs,
same run/user/hash, Medium RID 8192 and elevated=false. Original result JSONL
SHA-256: 9757d2bb830e3de37aee52d360caf22e6b98d71d600db84739054d8bb8a38617.
These are preserved historical outputs, not new frozen runs or independently
captured historical token handles. Completion also has the user's confirmation.

Static archive inspection confirms no acceptance modules/hook in the existing
production executable; the diagnostic archive contains the hook and modules.
Bundled main and core.onedrive_auth code objects match the production archive.
No acceptance imports/references occur in the production entry point, spec or
core/UI/model/utils source paths. Default production Analysis does not collect
unreferenced acceptance files. Packaging the diagnostic requires the deliberate
temporary-spec builder. No production rebuild was done for this audit.

The reviewed path calls only explicit synthetic cache locations. Socket and
browser/process audit events are blocked, along with MSAL client construction;
the negative probes confirm those managed paths reject activity. This is not a
claim of OS-enforced network impossibility: arbitrary native calls or hostile
in-process code are not contained by Python audit hooks. There is no historical
packet capture. No real-account/cache access or cloud mutation was found in the
reviewed implementation/evidence, and none was performed during this audit.

Temporary build/spec/manifests remain under the external builder's gateb-20261019
directory; the delivered executable/launcher/results remain under the public
Gate B directory. Frozen synthetic data stays under the recorded UUID directory
in the test user's TEMP. The diagnostic performs no automatic cleanup or retries;
all existing evidence was retained. Regression tests clean up only their newly
generated UUID fixtures. Path checks are not a lock against a hostile same-user
filesystem race; these fixtures must remain disposable and isolated.

Reproduced PASS: 19 focused cache/auth tests and 249 full-suite tests; compilation
and git diff --check PASS. Closure logs are gateb-closure-focused.log and
gateb-closure-20261019/full.log beneath the external builder. The new diagnostic
tests cover path ownership, sanitization, refusal, real source DPAPI, injected
failures, offline guards, cross-process CLI and temporary spec isolation. Existing
test_onedrive_auth tests exercise production auth selection/rejection with fakes.
Neither group establishes live-account lifecycle acceptance.

Reproduction limitation: the acceptance builder intentionally requires HEAD to
equal 3996629. It will refuse directly from a later diagnostic checkpoint or VM
release. To reproduce the recorded input after checkpointing, use a new isolated
worktree at 3996629 and overlay only acceptance/, scripts/build_cache_acceptance.py
and the diagnostic tests from the reviewed diagnostic checkpoint, then build with
the recorded environment and a fresh external output directory. Do not reset a
working checkout or weaken the guard. This reconstruction is not executed here.

The established scripts/vm_release.py adapter successfully produced a read-only
patch preview: v0.15.1, subject "Release v0.15.1: test: add isolated OneDrive cache
acceptance diagnostics", generated updates VERSION and CHANGELOG.md, tag v0.15.1.
The tool does not provide a source-only/no-tag checkpoint command. Thus its actual
release would extend the 13-file Gate B scope with two release-metadata files and
a tag. This is a preview, not authorization for those effects. No files were staged
and no release command was executed. A strict 13-file source-only VM checkpoint
remains unsupported by the current tool; agree the intended commit mechanism and
metadata/tag scope explicitly before execution. No plain-Git substitute was used.

All 13 changed/untracked files are diagnostic implementation (6), regression tests
(1), or Gate B documentation/handoff (6). Binaries, synthetic cache files, generated
specs/manifests, results and temporary logs stay outside the commit. No unrelated
change in this worktree needs exclusion; historical dirty worktrees/stash/backups
remain separate. Local machine paths in this report are recorded evidence and
installation locations, not hardcoded diagnostic paths; code uses repo/TEMP paths.
