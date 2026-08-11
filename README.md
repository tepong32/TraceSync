# TraceSync

TraceSync is a Windows desktop utility for safely comparing and synchronizing two folders. It is designed for office and shared-file environments where users must understand a copy operation before it changes a file.

Current release: **v0.6.0**

## Workflow

```text
Compare -> Review results -> Select direction -> Preview -> Confirm -> Synchronize -> Summary
```

TraceSync only performs one-way synchronization. It does not automatically resolve conflicts or schedule background runs.

## Features

- Recursive folder scanning and relative-path comparison.
- Clear statuses: Local Newer, Server Newer, Same, Local Only, and Server Only.
- Color-coded and filterable result list, with file details on double-click.
- Local -> Server and Server -> Local synchronization previews.
- Explicit confirmation showing new files, replacements, and warnings.
- Background file copying with responsive progress, elapsed and estimated remaining time, and safe cancellation between files.
- File-level error reporting; recoverable errors do not stop other approved copies.
- Metadata validation immediately before each copy. Files changed after confirmation are skipped and require a new comparison.
- JSON settings that retain the selected folders and can accommodate future provider-specific settings.

## Safety model

TraceSync never starts a synchronization job until the user confirms the complete preview. Existing destination files are identified before confirmation. The job preserves timestamps where the local filesystem supports them and creates missing destination directories.

No rollback, backup, automatic synchronization, cloud provider, or bidirectional conflict-resolution feature is included in v0.6.0.

## Architecture

```text
MainWindow
  -> SyncService
     -> StorageScanner -> StorageProvider
     -> comparer -> ComparisonResult
     -> SyncPreview -> SyncJobRunner -> SyncJob
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
core/       comparison, providers, preview orchestration, and job execution
models/     lightweight comparison and synchronization dataclasses/enums
ui/         Tkinter window and dialogs
utils/      settings persistence
tests/      synchronization behavior tests
docs/       vision, roadmap, architecture, backlog, and icebox
```
