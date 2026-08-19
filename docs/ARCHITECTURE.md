# TraceSync Architecture

TraceSync separates comparison, planning, execution, and presentation so that a user-approved plan is the only input to a synchronization run.

```text
MainWindow -> SyncService.compare() -> StorageScanner -> StorageProvider
           -> SyncService.create_preview() -> SyncPreview
           -> SyncService.start_job() -> SyncHistoryService.begin_run()
                                      -> SyncJobRunner -> StorageProvider.copy_from()
                                      -> SyncHistoryService.finalize_run()
           -> SyncJob -> progress and summary dialogs
MainWindow -> SyncHistoryDialog -> SyncHistoryService -> JsonSyncHistoryStore
```

## Storage providers

`StorageProvider` is the boundary between synchronization logic and a storage backend. Providers advertise capabilities and implement scanning, safe path resolution, and copying. `LocalStorageProvider` supports ordinary local folders and mapped/network filesystem paths today. Future cloud providers should implement this interface rather than adding provider-specific conditions to `SyncService`.

## Synchronization safety

`SyncPreview` contains every proposed action, including source, destination, direction, comparison status, overwrite flag, and explanation. The confirmation dialog reads this preview before a job is created. `SyncJobRunner` catches file-level failures and continues with remaining files; it does not roll back completed copies. Cancellation is applied between files, never by terminating an in-progress copy.

Immediately before each copy, the runner verifies that the source and destination still match the metadata captured in the preview. A source or destination that changed after confirmation is skipped and reported, requiring the user to compare again before proceeding.

## Settings compatibility

Settings remain a JSON dictionary so existing `local_folder` and `server_folder` entries continue to work. New provider-specific settings can be added as nested keys without changing the current UI contract.

## Synchronization history

`SyncHistoryService` observes synchronization execution; it never copies files. A run begins only after the user confirms a non-empty preview and an initial `in_progress` record is atomically stored. One JSON document per UUID-named run is stored under `%LOCALAPPDATA%\TraceSync\history\runs\`. Each record carries a schema version, the application version obtained from `VERSION`, safe provider endpoint snapshots, UTC timestamps, counts, and a structured outcome for every approved file.

`JsonSyncHistoryStore` writes a temporary document beside the target, flushes and `fsync`s it, then uses `os.replace`. Records are loaded independently, so one corrupt document is reported and skipped without hiding valid history. Successful writes trigger conservative retention of the newest 500 runs. Clear History is explicit and confirmed in the UI.

Provider endpoint snapshots may include provider type, display name, and a safe locator. They must never contain passwords, tokens, authentication headers, or credential-bearing URIs. Future providers are responsible for producing a safe snapshot through `StorageProvider.describe_endpoint()`.

### Finalization and interruption semantics

A failed final history write does not change or falsify the synchronization result. TraceSync warns the user and leaves the last durable record as `in_progress`; it does not persist a competing `finalization_failed` run outcome. At the next startup, an abandoned `in_progress` record becomes `interrupted`, and unresolved per-file outcomes become `unknown`. This records only what TraceSync can prove after a crash or persistence failure.

An operating-system file lock in the TraceSync local-data directory is acquired before the initial history write and held through terminal finalization. A second synchronization attempt fails before copying, providing a lightweight single-active-sync guarantee across application processes. History recovery and clearing use the same lock so they cannot race an active run.

### History presentation and export

The history UI initially requests the newest 100 records from the service. It provides run details, issues-only filtering, a non-blocking corrupt-record warning, and confirmed clearing. CSV export is limited to the selected run and writes one row per approved file. Export uses the standard `csv` module, includes the relevant run metadata on every row, and prefixes formula-like string values before spreadsheet software can interpret them.
