# TraceSync

TraceSync is a Windows desktop utility for safely comparing and synchronizing two folders. It is designed for office and shared-file environments where users must understand a copy operation before it changes a file.

Current release: **v0.9.0**

This release includes the completed v0.7 selective-synchronization improvements, the v0.8 planning-only provider and result-table usability work, and v0.9 Synchronization History & Auditability. The application version is read from the canonical `VERSION` resource in both source and packaged runtimes.

## Workflow

```text
Compare -> Review results -> Select direction -> Preview -> Confirm -> Synchronize -> Summary -> Review history
```

TraceSync only performs one-way synchronization. It does not automatically resolve conflicts or schedule background runs.

## Features

- Recursive folder scanning and relative-path comparison.
- Clear statuses: Local Newer, Server Newer, Same, Local Only, and Server Only.
- Color-coded and filterable result list, with file details on double-click.
- Result-row context actions for opening file details and copying a relative path.
- Local -> Server and Server -> Local synchronization previews.
- Optional per-file selection in the synchronization confirmation preview.
- Explicit confirmation showing new files, replacements, and warnings.
- Background file copying with responsive progress, elapsed and estimated remaining time, and safe cancellation between files.
- File-level error reporting; recoverable errors do not stop other approved copies.
- Metadata validation immediately before each copy. Files changed after confirmation are skipped and require a new comparison.
- Durable synchronization history with structured run and per-file outcomes, interrupted-run recovery, and a newest-500-run retention limit.
- History review and selected-run CSV export, including spreadsheet formula-injection protection.
- A lightweight operating-system lock that permits only one active synchronization per user profile.
- JSON settings that retain the selected folders and can accommodate future provider-specific settings.
- Planning-only provider selections and status messaging; these do not connect to or move data through remote services.

## Safety model

TraceSync never starts a synchronization job until the user confirms the complete preview and the initial `in_progress` history record is safely persisted. Existing destination files are identified before confirmation. The job preserves timestamps where the local filesystem supports them and creates missing destination directories.

If the final history update fails after copying, TraceSync preserves the real synchronization result and warns the user. The durable record remains `in_progress`; on a later launch it is honestly classified as `interrupted` because completion cannot be proven from the history store.

No rollback, backup, automatic synchronization, active cloud provider, or bidirectional conflict-resolution feature is included in v0.9.0.

## Architecture

```text
MainWindow
  -> SyncService
     -> StorageScanner -> StorageProvider
     -> comparer -> ComparisonResult
     -> SyncPreview -> SyncJobRunner -> SyncJob
     -> SyncHistoryService -> JsonSyncHistoryStore
```

`LocalStorageProvider` is the only concrete provider. The provider abstraction keeps scanning and synchronization independent of the local filesystem API, ready for later storage backends without changing the UI workflow.

See [Architecture](docs/ARCHITECTURE.md) for the module responsibilities and [Roadmap](docs/ROADMAP.md) for deferred work.

## Running locally

TraceSync requires Python 3 and Tkinter.

```powershell
python main.py
```

Run the automated synchronization tests with:

```powershell
python -m unittest discover -s tests -v
```

## Project layout

```text
core/       comparison, providers, synchronization execution, history, and CSV export
models/     lightweight comparison, synchronization, and history dataclasses/enums
ui/         Tkinter window and dialogs, including history review
utils/      settings and application-version utilities
tests/      synchronization, persistence, export, and UI behavior tests
docs/       vision, roadmap, architecture, backlog, and icebox
```
