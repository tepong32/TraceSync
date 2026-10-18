# OneDrive create-only mission validation

Checkpoint note: the historical audit below preceded local source commit
`0de6aa23987a5661b0578ea40b83f5082abedb32`, parent `4ddfd55`. The safety
patch is committed; its references to uncommitted work describe the audit date.
Runtime dependency integration and current acceptance status are recorded in
[ONEDRIVE_ENVIRONMENT.md](ONEDRIVE_ENVIRONMENT.md). No integration or release
is implied.


Date: 2026-10-18. Branch: codex/onedrive-create-safety-audit.
Base and unchanged HEAD: 4ddfd55e2874fecb76e6cf1e054fc971b03bbb41 (v0.15.0),
a verified descendant of requested v0.14.0 (8ffb2d0). Remote master was fetched and
matched this base. Implementation remains uncommitted; no merge/push/build.
The separate dirty pair-management worktree and historical SFTP workspace were
preserved. This audit does not include their uncommitted features.

## Evidence and decisions

- [driveItem instance attributes](https://learn.microsoft.com/en-us/graph/api/resources/driveitem#instance-attributes)
  documents fail/replace/rename and placing conflictBehavior in the URL. PUT
  defaults to replace, so empty new-file content requests explicitly specify fail.
- [Content upload](https://learn.microsoft.com/en-us/graph/api/driveitem-put-content)
  documents the new-file parent/name route, binary body and returned driveItem.
  Empty bytes use that route; completion requires 201 plus matching native ID,
  parent, name, file facet and size zero. This documented composition is locally
  tested, not proof that a real personal account honors it for empty bodies.
- [Folder creation](https://learn.microsoft.com/en-us/graph/api/driveitem-post-children)
  documents POST children, folder facet, conflict behavior and created metadata.
  Use fail instead of its rename example. Validate the returned parent/name/type;
  reject shortcuts, deleted items and contradictory facets. Optional returned
  driveId must match. No replace/rename fallback or remote cleanup is used.
- [Upload sessions](https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession)
  remain the nonempty-file path, with conflict failure, exact ranges and confirmed
  completion. Signed upload URLs receive no bearer token; redirects/retries disabled.

The immutable per-file folder plan includes the selected root ID, scanned ancestor
IDs and expected absence for missing ancestors. It survives selection filtering
and passes through TransferPrecondition; changed or omitted evidence blocks the
provider before mutation. Preview warnings derive from this plan and are rebuilt
for selected files. Only selected file ancestors can be created. Compare/select
perform GETs only. Root/ancestor IDs and parent links are refreshed before creation
and again before file publication. Permissions are enforced by the server request;
listing access is never treated as proof of write permission.

Known server rejections (including 403) are definite failures, 409/412 are conflicts,
and timeout/malformed replies/ambiguous server responses remain unknown without
retry. Known created directories and uncertain folder paths are added to each
file's terminal history message, including failure/skip outcomes. Counts remain
file counts; created folders are not misreported as copied files. Cancel is checked
between files, allowing the in-flight file to finish. No automatic directory deletion.

## Local validation

PASS: targeted, 44 tests:
`C:/Users/Administrator/Desktop/GH/TraceSync/.venv/Scripts/python.exe -m unittest tests.test_onedrive_transfer tests.test_synchronization tests.test_onedrive_main_window -q`

PASS: full suite, 226 tests, no failures/skips:
`C:/Users/Administrator/Desktop/GH/TraceSync/.venv/Scripts/python.exe -m unittest discover -s tests`
Log: .tmp-mission-tests.log. Existing Tk ThemeChanged teardown diagnostics appear;
all test results pass. Full suite chosen for shared provider/preview/runner changes.

PASS: `python -m compileall -q core models ui tests` (same interpreter above).
PASS: `git diff --check`.

Initial affected run failed because the fake did not implement the new root-ID
lookup; updated the deterministic Graph fake with native-root lookup and correct
per-parent child listings. Targeted and full reruns pass. No known regressions.

| Required case | Evidence in tests/test_onedrive_transfer.py unless noted |
| --- | --- |
| Single/nested missing folders | folder failure/partial tests; nested shared-parent upload test |
| Existing destination folder | existing_parent_is_verified_and_never_created |
| Concurrent folder creation | parent_appearing_after_review; folder creation conflict |
| Permission denied | permission_denied_is_definite_failure_not_unknown |
| Parent removed/replaced/moved | missing_changed_or_moved_parent; new_parent_disappearing |
| Zero-byte/nonzero source | empty_upload; confirmed_upload; nested empty/nonempty siblings |
| Existing file / overwrite attempts | overwrites excluded and forged preview runner protection |
| Provider conflict | empty creation conflict; final upload collision |
| Interrupted/unknown upload | unknown_upload modes; invalid empty response; uncertain folder |
| Source changes after review | changed_source_before_upload; source_changed_during_download |
| Cancellation/partial completion | selection_cancellation; cancel_after_first_file; partial_folder history |
| History and summary | runner/history counts and per-file reasons/messages asserted |
| Forged/stale preview | forged_folder_plan_and_rescanned_parent_state; forged overwrite |
| Select/compare without mutation | test_onedrive_main_window activation/compare/cancel asserts GET only |

## Remaining gates and limits

NOT RUN - ENVIRONMENTAL: live personal-account OAuth/Graph acceptance; no disposable
account/registration. NOT RUN - ENVIRONMENTAL: actual Windows protected-token cache
acceptance. NOT RUN - OUT OF SCOPE: packaged executable/build/portfolio publication.
Optional cloud SDK packaging/dependency validation is still open.

Graph operations target native parent IDs: another actor moving that same parent
after the last check may move the resulting new file with it. There is no documented
atomic lock on the whole ancestor chain. We never switch to a replacement parent
ID or overwrite an occupied filename; do not describe ancestry checks as atomic.
On process termination before terminal history persistence, the existing durable
in-progress run becomes interrupted; exact folders created immediately before the
crash cannot be reconstructed from that record. Compare again, inspect OneDrive,
and do not infer rollback or retry. Terminal reports contain observed side effects,
not a transactional folder journal. No standalone empty-directory mirroring,
scheduling, deletion mirroring, replacements or additional providers were added.


# Post-implementation integration gate review

Review date: 2026-10-18. Recommendation after corrections: **eligible for an
explicit source-checkpoint/integration authorization**, not a production release.
No authorization has been acted on. All work remains uncommitted; no commit,
merge, push, tag or executable publication occurred during this review.

## Exact revision and scope

Worktree: C:/Users/Administrator/.codex/worktrees/tracesync-onedrive-create-safety.
Branch: codex/onedrive-create-safety-audit. Base, HEAD, v0.15.0 and live remote
master: 4ddfd55e2874fecb76e6cf1e054fc971b03bbb41. Live remote identity reproduced
with git ls-remote origin refs/heads/master refs/tags/v0.15.0. Committed divergence:
0 ahead / 0 behind against origin/master. No upstream tracking branch is configured
for this local branch. Worktree is dirty with the original patch plus corrections.

Original inventory: 15 modified tracked files and this untracked report. Corrective
work adds core/local_storage_provider.py to that inventory (16 tracked + report).

| Changed files | Scope |
| --- | --- |
| core/onedrive_provider.py | Folder plans/checks, run-owned state, uncertainty barriers, validated completion and typed errors |
| core/storage_provider.py | Default no-op run lifecycle, folder-plan and transfer-note hooks |
| core/sync_service.py | Attach folder evidence and derive review warnings |
| core/sync_job_runner.py | Enforce operation/evidence consistency, pass folder plans, preserve terminal notes |
| core/local_storage_provider.py | Reject direct replacement requests from create-only sources |
| models/sync_preview.py; models/transfer_precondition.py | Immutable folder evidence and selection-derived warnings |
| tests/test_onedrive_transfer.py; tests/test_onedrive_main_window.py | Provider/runner/adversarial coverage and GET-only setup/compare check |
| AGENTS.md; CHANGELOG.md; CONTINUE.md | Durable constraints, changes, immediate handoff |
| docs/ARCHITECTURE.md; docs/BRANCH_WORKFLOW.md; docs/CLOUD_STORAGE.md; docs/ROADMAP.md | Contracts, scope, state and gate links |
| docs/ONEDRIVE_CREATE_VALIDATION.md (untracked) | Original evidence plus this independently reproduced review |

No SFTP files, saved-pair edit/delete implementation, auth implementation, SDK
requirements, release metadata or executable artifacts are changed. Other dirty
worktrees/stashes/backups were preserved. Complete source/docs diffs and the
untracked report were inspected before corrections. Audit commands did not modify
source. Tests use temporary data; compileall generates only ignored bytecode.

## Reproduced commands

Interpreter prefix below: C:/Users/Administrator/Desktop/GH/TraceSync/.venv/Scripts/python.exe

| Command | Before correction | After correction |
| --- | --- | --- |
| -B -m unittest tests.test_onedrive_transfer tests.test_synchronization tests.test_onedrive_main_window -q | PASS 44 tests | PASS 51 tests |
| -B -m unittest discover -s tests | PASS 226 tests | PASS 233 tests, no failures/skips |
| -m compileall -q core models ui tests | PASS | PASS |
| git diff --check | PASS | PASS |

Post-correction full log: .tmp-post-review-tests.log. The existing Tk ThemeChanged
teardown diagnostics remain; unittest reports OK. These are not cloud acceptance.

## Findings and corrections

1. **Critical, corrected: inconsistent forged operation could replace locally.**
   An offline probe supplied overwrite=False plus non-null destination metadata,
   then materialized a matching external file between runner validation and provider
   entry. The original runner reported one copied file; external bytes became remote
   content and backup_id was None. The runner now rejects inconsistent operation/
   evidence before provider entry. LocalStorageProvider also rejects replacement
   preconditions from create-only sources. Regression tests: forged_absence_flag
   and direct_cloud_to_local_replacement. This was a real bypass, not merely a
   theoretical ancestry race. Local-only accepted overwrite behavior is unchanged.
2. **Gate failure, corrected: malformed success metadata lost uncertainty.**
   parentReference=None/list/string caused AttributeError after a successful
   creation reply, producing unexpected_error instead of transfer_outcome_unknown.
   The shared validator now checks dict structure, string ID, facet, parent/drive
   and integer size before dereferencing. Both empty and nonempty completion paths
   use it. Folder uncertainty notes remain available. Test: malformed_create_metadata.
3. **Gate failure, corrected: 403 on nonempty upload became unknown.**
   TransferFailed was caught by the generic upload exception handler. It is now
   propagated as a definite failure; test nonempty_upload_permission_rejection.
4. **Gate failure, corrected: run ownership and implicit folder retries.**
   Run-created IDs survived into a later run; an unresolved folder action could
   also be reattempted by a sibling file. A no-mutation begin_transfer_run hook
   resets run-owned IDs/notes. Unknown folder paths remain blocked until comparison
   refreshes evidence. Tests: unknown_shared_folder and run_owned_folder_ids.

## Adversarial scenario evidence

Test names below are abbreviated; full methods are in tests/test_onedrive_transfer.py.
Inspection evidence is explicitly distinguished from executable fault injection.

| Scenario | Path and observed evidence | Residual risk |
| --- | --- | --- |
| Ancestor replaced after review | _ensure_parent rejects ID mismatch; missing_changed_or_moved_parent passes | Replacement after last check remains a timing window; native IDs prevent adopting a different parent |
| Link changes between check/mutation | Offline probe changed sub's parent immediately after GET; sub/deep was created, second chain check skipped file and recorded partial folder | Cannot prevent that intermediate mutation or atomically lock ancestry; must not claim race freedom |
| Concurrent folder creation | _item fresh lookup and POST conflict fail; parent_appearing and folder_creation_conflict tests pass | No adoption/rename/replace fallback; creation after GET is server-enforced conflict |
| Folder created but response lost | success_then_lost_response commits fake folder then raises; UNKNOWN, one mutation, notes retained | Sibling files are blocked; real remote contents require comparison/inspection |
| Crash after folder before result persisted | SyncHistoryService durable initial run and _as_interrupted; existing test_interrupted_recovery_marks_pending_files_unknown passes | No folder write-ahead journal: exact created paths are lost on process termination; explicitly accepted/documented |
| Later folder/file fails | partial_folder_creation_then_failure and new_parent_disappearing tests preserve known folder notes, file failure/skip and counts | No rollback; directories may remain. Abrupt process death has preceding limit |
| Empty upload meets existing file | Fresh get_record/absence checks; overwrite/forged preview and empty conflict tests pass | Commit-time fail option is the protection, not the GET; live provider acceptance remains open |
| Upload committed but reply lost | success_then_lost_response commits fake file then raises; UNKNOWN, one mutation | No automatic retry or assumption of failure; manual recompare required |
| Missing/malformed/inconsistent completion | Validator rejects invalid structure/parent/type/size; malformed_create_metadata and invalid_empty_success tests pass | Provider returning plausible but false metadata cannot be disproved by mocks |
| Source changes after confirmation | Runner snapshot evidence and provider staged-source check; changed_source_before_upload passes | Local metadata is not a cryptographic byte identity; staged snapshot is what uploads |
| Stale/forged preview | Runner operation/evidence consistency, cloud create-only checks, immutable folder-plan match; new bypass regressions and forged_folder_plan tests pass | Preview objects are internal data, not signed authorization; arbitrary in-process code is not a security boundary |
| Permission vs uncertain outcome | Known HTTP rejections remain definite; transport/malformed success stays UNKNOWN; 403 tests now pass for folder and nonempty file | A server/proxy lying about an outcome is outside what local tests prove |
| Cancel after mutation | cancel_after_first_file preserves copied result and marks remaining file not attempted; selection_cancellation makes no unapproved trees | Cancellation is between files, not rollback or an abort of in-flight requests |

## Trace through the normal workflow

SyncService.create_preview snapshots per-file folder evidence. The confirmation
UI displays warnings; MainWindow.prepare_sync starts only confirmed selected files.
SyncPreview.with_selected_items retains evidence and rebuilds folder warnings.
HistoryService writes IN_PROGRESS before worker start. Runner validates consistency,
create-only policy and source/destination state, then constructs TransferPrecondition.
OneDrive rejects a changed folder plan, stages the source, refreshes the ancestor
chain, creates only required missing parents with fail-on-conflict, refreshes again,
and uploads. Native IDs remain the mutation targets. Runner consumes observed
notes into terminal per-file history and accurate file counts. UNKNOWN is a reason
code on a failed file, not copied success. Interrupted recovery marks uncertainty;
it does not resume or retry. Account-matched token suppliers/cache references,
Graph identity checks, signed-URL credential separation and settings allowlists are
unchanged; auth regressions passed in the full suite.

## Minor findings and accepted limitations

- Selection warnings are recomputed on the selected preview; the open confirmation
  dialog initially shows the broader plan. Execution creates only selected ancestors.
- No-op lifecycle and terminal-note hooks extend the shared provider interface;
  all local regressions pass. The original patch has been expanded only to close
  reproduced integration-gate failures.
- Preflight GETs cannot lock permissions or ancestry. Write permissions are decided
  by the actual mutation. Native-ID moves after final validation remain possible.
- Folder details reach durable terminal history only on normal finalization;
  interrupted runs honestly report unknown, without exact folder accounting.
- Live personal-account, Windows protected-cache and packaged acceptance remain
  outstanding. No production/readiness claim follows from these mocked tests.

All reproducible critical findings above have corrective regression coverage.
Source integration can be considered only after explicit user authorization of
this corrected diff. No publication/integration action was performed.
