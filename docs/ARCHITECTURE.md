# TraceSync Architecture

TraceSync separates comparison, planning, execution, and presentation so that a user-approved plan is the only input to a synchronization run.

```text
MainWindow -> SyncService.compare() -> StorageScanner -> StorageProvider
           -> SyncService.create_preview() -> SyncPreview
           -> SyncService.start_job() -> SyncHistoryService.begin_run()
                                      -> SyncJobRunner -> BackupService
                                                       -> StorageProvider.transfer_from()
                                      -> SyncHistoryService.finalize_run()
           -> SyncJob -> progress and summary dialogs
MainWindow -> FolderPairManagerDialog -> SettingsService
MainWindow -> SyncHistoryDialog -> SyncHistoryService -> JsonSyncHistoryStore
                                -> BackupService -> JsonBackupStore
```

## Storage providers

`StorageProvider` is the boundary between synchronization logic and a storage backend. Providers advertise capabilities and implement scanning, safe location resolution, and conditional transfer. `LocalStorageProvider` supports ordinary local folders and mapped/network filesystem paths today. Future providers should implement this interface rather than adding provider-specific conditions to `SyncService`.

Every approved operation carries an immutable `TransferPrecondition` containing the reviewed source and destination `StorageLocation` and `ComparisonMetadata` values. Missing destination metadata means the destination was absent during review. Source providers expose reviewed content through `open_transfer_content`, which may yield a direct local path or a verified temporary materialization. A destination advertising `CONDITIONAL_TRANSFER` must enforce the preconditions as part of its create or replacement operation. A state mismatch is reported separately from an operational transfer failure and is never automatically retried.

## Synchronization safety

`SyncPreview` contains every proposed action, including source, destination, direction, comparison status, overwrite flag, and explanation. The confirmation dialog reads this preview before a job is created. `SyncJobRunner` catches file-level failures and continues with remaining files. Cancellation is applied between files, never by terminating an in-progress copy.

Immediately before each transfer, the runner verifies that the source and destination still match the metadata captured in the preview. The same reviewed snapshots are then passed to the provider as the transfer precondition, so the provider can reject a later change at its create or replacement boundary. A changed source or destination is skipped and reported, requiring the user to compare again before proceeding.

For an overwrite, `SyncJobRunner` requires `BackupService` to create and verify a durable copy of the existing destination before replacement. The source and destination are checked again after the backup, then the provider performs its final validation. Local replacement has the concurrency limitation below. Backup failure is a per-file hard stop: that destination is not overwritten. New-file copies bypass backup creation.

`LocalStorageProvider` validates the transfer precondition before staging, copies content to a temporary sibling file, flushes it, and validates the reviewed source and destination again immediately before publication. New files use non-overwriting Windows rename (POSIX exclusive hard-link creation); an occupied target is a safe skip. Existing files use `os.replace` with the limitation below. A failed precondition or copy therefore leaves the prior destination intact rather than exposing a partial file.

## Backup and restore

`BackupService` coordinates recovery policy; `JsonBackupStore` owns durable backup content and metadata. Content is stored under `%LOCALAPPDATA%\TraceSync\backups\files\`, with one atomic UUID-named JSON manifest under `%LOCALAPPDATA%\TraceSync\backups\records\`. The manifest records the synchronization run, safe destination endpoint snapshot, relative path, timestamp, size, and modified time. Backup content is kept outside synchronized roots so it cannot appear in folder comparisons.

Successful backup IDs are added to their per-file history outcomes without changing the v1 history schema: `backup_id` is an optional, backward-compatible field. Backup manifests also carry the run ID and relative path, allowing the history UI to discover a recovery point if a terminal history write was interrupted before it could persist the per-file link.

Retention is applied after backup creation and restore. `JsonBackupStore` keeps at most two versions for the same provider locator and relative path, no more than 5 GB of valid backup content globally, and no more than 500 valid entries overall. It removes the oldest eligible content first. The backup required by the operation in progress is protected even when that single file exceeds the size ceiling; the limit is therefore a cleanup target rather than permission to discard the only safety copy. Invalid or incomplete entries are never selected for restore.

The history details dialog enables Restore only for a row with a backup ID. Restore is explicit and confirmed. Before replacing the current destination with historical content, `BackupService` creates another safety backup of the current file in the same recovery group and then uses the atomic replacement path. A later Restore from that history row resolves to the newest valid recovery point, so the safety copy remains reachable without rewriting historical audit records. This is recovery from a TraceSync overwrite, not an automatic rollback of an entire multi-file run and not protection against loss of the computer or drive holding `%LOCALAPPDATA%`.

## Settings compatibility

Settings remain a JSON dictionary so existing `local_folder` and `server_folder` entries continue to work. v0.10 adds normalized `folder_pairs` and `active_folder_pair` values for named Local ↔ Server relationships. Existing `recent_pairs` data is accepted as a migration source only when `folder_pairs` is absent.

`FolderPairManagerDialog` owns the editing interaction, while `MainWindow` applies a selected relationship to the current folder fields. Changing either endpoint invalidates stale comparison results before synchronization can be enabled again. Folder Pairs do not introduce another comparison engine, background job queue, multi-job workspace, or provider transport.

## Synchronization history

`SyncHistoryService` observes synchronization execution; it never copies files. A run begins only after the user confirms a non-empty preview and an initial `in_progress` record is atomically stored. One JSON document per UUID-named run is stored under `%LOCALAPPDATA%\TraceSync\history\runs\`. Each record carries a schema version, the application version obtained from `VERSION`, safe provider endpoint snapshots, UTC timestamps, counts, and a structured outcome for every approved file.

`JsonSyncHistoryStore` writes a temporary document beside the target, flushes and `fsync`s it, then uses `os.replace`. Records are loaded independently, so one corrupt document is reported and skipped without hiding valid history. Successful writes trigger conservative retention of the newest 500 runs. Clear History is explicit and confirmed in the UI.

Provider endpoint snapshots may include provider type, display name, and a safe locator. They must never contain passwords, tokens, authentication headers, or credential-bearing URIs. Future providers are responsible for producing a safe snapshot through `StorageProvider.describe_endpoint()`.

### Finalization and interruption semantics

A failed final history write does not change or falsify the synchronization result. TraceSync warns the user and leaves the last durable record as `in_progress`; it does not persist a competing `finalization_failed` run outcome. At the next startup, an abandoned `in_progress` record becomes `interrupted`, and unresolved per-file outcomes become `unknown`. This records only what TraceSync can prove after a crash or persistence failure.

An operating-system file lock in the TraceSync local-data directory is acquired before the initial history write and held through terminal finalization. A second synchronization attempt fails before copying, providing a lightweight single-active-sync guarantee across application processes. History recovery and clearing use the same lock so they cannot race an active run.

### History presentation and export

The history UI initially requests the newest 100 records from the service. It provides run details, backup availability and restore, issues-only filtering, a non-blocking corrupt-record warning, and confirmed clearing. CSV export is limited to the selected run and writes one row per approved file, including any backup ID. Export uses the standard `csv` module, includes the relevant run metadata on every row, and prefixes formula-like string values before spreadsheet software can interpret them.

## Local overwrite limitation

On 2026-10-11 the user explicitly chose to preserve backup-protected local overwrites and existing-file restore rather than disable them. Existing-file transfers still validate metadata and commit staged content using `os.replace`. Replacement is atomic publication of complete content, **not atomic compare-and-swap against the reviewed destination**. Another application or user can change the destination after the last check and before replacement; that latest edit may be overwritten and may not be present in the earlier backup. Restore has the same external-writer limitation. The per-user TraceSync lock does not lock out external writers, and metadata evidence does not establish byte-for-byte identity.

The local provider retains its legacy `CONDITIONAL_TRANSFER` flag for this accepted workflow; this is an explicit exception to the strict provider contract, not proof of race-free conditional replacement. New providers must not inherit the exception. Prefer quiescent source/destination files for local overwrites and restore. The new-file synchronization fix does not claim to resolve concurrent editing of existing files, restore publication, mutable parent paths, or untrusted filesystem/server behavior.

SFTP is excluded from this release and remains unfinished development.

Google Drive and OneDrive provider development is isolated from SFTP on separate
branches. Neither is integrated into the UI or ready for normal users. The
sign-in, folder-selection, provider, token-storage, safety, and remaining
validation work is recorded in [Cloud storage provider plan](CLOUD_STORAGE.md).
Keep the existing compare-review-confirm-sync workflow and require each provider
to declare only the capabilities its own API operations enforce.


## Presentation

`ui/theme.py` centralizes styles; `WorkflowGuide` presents safe next actions in green and copy review in amber. `ScrollablePanel` keeps optional provider controls bounded and keyboard reachable. Styling never authorizes synchronization.
