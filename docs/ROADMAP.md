# TraceSync Roadmap

> **Simple. Safe. Predictable.**

TraceSync is developed in focused milestones. A milestone is complete only when its user-facing workflow, documentation, and validation are complete.

## Current release

| Item | Value |
| --- | --- |
| Version | **v0.3.2** |
| Milestone | **Synchronization** |
| Status | **Release candidate** |

## Completed milestones

### Foundation and results exploration

- Recursive folder scanning and relative-path comparison.
- Status classification and summary statistics.
- Filterable, color-coded results.
- Folder selection persistence.
- File details dialog and double-click inspection.

### v0.3.2 - Synchronization

- One-way Local -> Server and Server -> Local copy workflows.
- Immutable preview created before any file operation.
- Explicit confirmation including create, replace, and warning counts.
- Background job state, responsive progress, elapsed/remaining time, and safe cancellation.
- File-level error handling with a completion summary.
- Just-in-time source and destination validation before each copy.
- StorageProvider abstraction with LocalStorageProvider.

## Next milestone: Explorer Polish

- Search and filename filtering.
- Hide Same Files toggle.
- Column-width persistence and sorting.
- Export comparison report.
- Open selected file or containing folder.

## Intentionally deferred

- Cloud and network storage providers beyond filesystem-backed paths.
- Scheduled or automatic synchronization.
- Bidirectional conflict resolution.
- Backup, rollback, and file version history.
- Hash-based comparison and rename detection.

Longer-term ideas remain in [BACKLOGS.md](BACKLOGS.md) and [ICEBOX.md](ICEBOX.md).
