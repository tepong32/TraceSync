# TraceSync Architecture

TraceSync separates comparison, planning, execution, and presentation so that a user-approved plan is the only input to a synchronization run.

```text
MainWindow -> SyncService.compare() -> StorageScanner -> StorageProvider
           -> SyncService.create_preview() -> SyncPreview
           -> SyncService.start_job() -> SyncJobRunner -> StorageProvider.copy_from()
           -> SyncJob -> progress and summary dialogs
```

## Storage providers

`StorageProvider` is the boundary between synchronization logic and a storage backend. Providers advertise capabilities and implement scanning, safe path resolution, and copying. `LocalStorageProvider` supports ordinary local folders and mapped/network filesystem paths today. Future cloud providers should implement this interface rather than adding provider-specific conditions to `SyncService`.

## Synchronization safety

`SyncPreview` contains every proposed action, including source, destination, direction, comparison status, overwrite flag, and explanation. The confirmation dialog reads this preview before a job is created. `SyncJobRunner` catches file-level failures and continues with remaining files; it does not roll back completed copies. Cancellation is applied between files, never by terminating an in-progress copy.

Immediately before each copy, the runner verifies that the source and destination still match the metadata captured in the preview. A source or destination that changed after confirmation is skipped and reported, requiring the user to compare again before proceeding.

## Settings compatibility

Settings remain a JSON dictionary so existing `local_folder` and `server_folder` entries continue to work. New provider-specific settings can be added as nested keys without changing the current UI contract.
