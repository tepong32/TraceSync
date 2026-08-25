# TraceSync Roadmap

> **Simple. Safe. Predictable.**

TraceSync is developed in focused milestones. A milestone is complete only when its user-facing workflow, documentation, and validation are complete.

The repository is the authoritative source of truth for the current implementation and release state.

> **Current status: v0.10 Folder Pair Workflow release candidate.**
>
> v0.10 is the active milestone. Backlog and icebox entries remain unscheduled unless explicitly promoted into this document.

---

## Current Release Candidate

| Item      | Value                                               |
| --------- | --------------------------------------------------- |
| Version   | **v0.10.0**                                         |
| Milestone | **Folder Pair Workflow**                            |
| Status    | **Implementation complete; release review pending** |

---

## Development Status

| Item      | Value                                         |
| --------- | --------------------------------------------- |
| Milestone | **v0.10 Folder Pair Workflow**                |
| Baseline  | **Merged v0.9.1**                             |
| Status    | **Release candidate prepared for validation** |

`VERSION` and the application title report v0.10.0. Folder Pairs add saved endpoint selection without changing the compare → review → confirm → synchronize workflow. The v0.9.1 provider-planning section remains hidden by default.

The detailed historical reconciliation, including release-numbering irregularities and superseded early plans, is in [RETROSPECTIVE_V0.1_V0.9.1.md](RETROSPECTIVE_V0.1_V0.9.1.md).

## Documentation Hierarchy

```text
ROADMAP       Committed development direction
BACKLOG       Evaluated future work with plausible product value
ICEBOX        Speculative or long-term possibilities
RETROSPECTIVE Historical record of what actually happened
VISION        Why TraceSync exists and what principles guide it
```

Only ROADMAP items are development commitments. A backlog item is not an implied commitment, and a retrospective entry is not a future requirement.

---

# Active Milestone

## v0.10 — Folder Pair Workflow (Release Candidate)

Core promise: recurring Local ↔ Server folder relationships can be selected quickly without turning the main comparison workflow into a multi-job workspace.

- Select a named Folder Pair above the existing Local and Server fields.
- Create, edit, rename, and delete saved relationships through a dedicated manager.
- Offer a useful pair-name suggestion based on the selected folder names.
- Persist the active pair while keeping `local_folder`, `server_folder`, and legacy `recent_pairs` settings compatible.
- Keep manual folder entry and Browse behavior intact; manual changes do not modify saved relationships.
- Invalidate stale comparison results and disable synchronization whenever either endpoint changes.
- Preserve one comparison at a time and the existing preview, confirmation, validation, execution, and history safeguards.
- Keep planning-only provider controls hidden by default; no remote/cloud transport or authentication is added.

Release review requires the full automated suite, Folder Pair UI coverage, compile validation, and a clean final diff.

---

# Completed Milestones

## Foundation and Results Exploration

Completed foundational capabilities:

* Recursive folder scanning.
* Relative-path-based file comparison.
* Difference classification.
* Summary statistics.
* Filterable comparison results.
* Folder selection persistence.
* File details dialog.
* Double-click file inspection.
* Clear comparison status presentation.

---

## v0.3.x — Synchronization

Completed synchronization foundation:

* One-way Local → Server synchronization.
* One-way Server → Local synchronization.
* Synchronization candidate selection.
* Immutable synchronization previews.
* Explicit synchronization confirmation.
* Create, replace, and warning counts.
* Background synchronization jobs.
* Progress and elapsed/remaining time reporting.
* Safe cancellation.
* File-level error handling.
* Completion summaries.
* Just-in-time source and destination validation.
* StorageProvider abstraction.
* LocalStorageProvider implementation.

---

# v0.4.x — Smart Synchronization

The v0.4 milestone focused on making TraceSync smarter about which files should participate in comparison and synchronization while keeping the normal office workflow simple.

## v0.4.1 — Ignore Engine Foundation

Completed.

* Centralized `IgnoreRuleEngine`.
* `IgnoreRule` model.
* `RuleSource` enumeration.
* Built-in ignore rules for common system, temporary, and development-generated files.
* Ignore filtering integrated into `StorageScanner`.
* Ignored files excluded from:

  * comparison
  * synchronization preview
  * synchronization execution

The ignore evaluator remains centralized so individual storage and synchronization components do not need to understand ignore rules.

---

## v0.4.2 — Project Ignore Support

Completed.

* Added project-level `.tracesyncignore` support.
* Added `ProjectIgnoreLoader`.
* Added `IgnoreLoader` for centralized rule collection.
* Added configured ignore-engine construction through `create_ignore_engine()`.
* Preserved built-in ignore rules alongside project-defined rules.
* Kept pattern matching centralized inside `IgnoreRuleEngine`.
* Integrated project rules into the existing synchronization pipeline.
* No additional UI complexity was introduced.

Project ignore patterns automatically affect:

* comparison
* synchronization preview
* synchronization execution

---

## v0.4.3 — User-Configurable Ignore Rules

Completed.

* Added persisted `ignore_patterns` settings.
* Added safe normalization of user-provided patterns:

  * trim whitespace
  * ignore blank lines
  * ignore comment lines
  * preserve display order
* Added `RuleSource.USER`.
* Extended ignore loading to merge:

  1. built-in rules
  2. project `.tracesyncignore` rules
  3. user-configured rules
* Kept `IgnoreRuleEngine` matching behavior unchanged.
* Injected user ignore patterns into comparison-time rule construction.
* Added a simple Ignore Settings dialog.
* Added plain-language help and examples.
* Added user-facing feedback when custom ignore rules are actively skipping files.
* Preserved the existing:

  * Compare
  * Review
  * Preview
  * Confirm
  * Run
    workflow.
* Added regression coverage for user-rule normalization, rule merging, and comparison filtering.

### v0.4 Milestone Result

The Smart Synchronization milestone is complete.

TraceSync now supports three ignore-rule sources:

```text
Built-in Rules
      +
Project Rules
(.tracesyncignore)
      +
User Rules
(Settings)
      ↓
IgnoreLoader
      ↓
IgnoreRuleEngine
      ↓
StorageScanner
      ↓
Comparison / Preview / Synchronization
```

Advanced include/override behavior is intentionally deferred.

The current ignore system should remain simple unless a real office workflow demonstrates a need for additional rule complexity.

---

# Development Milestones Included in v0.9.1

## v0.9 — Synchronization History & Auditability (Completed)

Core promise: after a synchronization, the user can inspect what TraceSync did, what it did not do, and why.

- Persist an initial `in_progress` record before file copying can begin.
- Record structured terminal run and per-file outcomes without changing synchronization candidate selection or copying behavior.
- Mark abandoned `in_progress` records as `interrupted` on a later launch instead of claiming success.
- Keep the real synchronization outcome distinct from a final history-write failure.
- Enforce one active synchronization with a lightweight operating-system file lock.
- Store one atomic, versioned JSON document per run and retain the newest 500.
- Review the newest 100 runs, inspect details, filter issues, clear history with confirmation, and warn about unreadable individual records.
- Export only the selected run to formula-hardened CSV with one row per approved file.
- Keep all remote/cloud provider work architectural; no transport or authentication is included.

## v0.8 — Remote and Cloud Preparation (Completed)

This milestone is architectural and planning-focused. No remote provider transport, authentication, or cloud synchronization is implemented.

### Completed in v0.8.4

- Clarify the planning status of remote/cloud synchronization from the main result screen.
- Preserve the local-first workflow while keeping the new remote/cloud planning panel as passive documentation.
- No comparison/synchronization behavior changes.

### Completed in v0.8.5

- Add a lightweight result-row context menu with quick access to file details and relative path copy.
- Preserve existing compare → review → confirm → sync workflow and keep all remote/cloud planning behavior unchanged.

### Completed in v0.8.1

- Introduce a dedicated remote/cloud onboarding surface for future provider-backed synchronization.
- Keep existing Local ⇄ Local folder workflow unchanged while this milestone is planning-focused.
- Preserve `StorageProvider` abstraction boundaries so future providers can be added without rewriting `SyncService`.
- Add roadmap-traceable settings/metadata placeholders only (no provider transport or auth logic).

### Completed in v0.8.2

- Persist provider profile selections (`Source provider` and `Destination provider`) in user settings.
- Restore provider selections on launch for faster, continuity-friendly continuation of the office workflow.

### Completed in v0.8.3

- Add explicit provider connection-status messaging for the onboarding panel.
- Clarify that the current source/destination provider controls are planning-focused and not yet active.

## v0.7 — Selective Synchronization (Completed)
### Completed in v0.7.1

- Added optional per-row selection in the confirmation workflow.
- Kept compare → preview → confirm → sync workflow unchanged.
- Preserved existing safety checks while allowing users to run selected copies only.

### Completed in v0.7.2

- Human-Friendly File Identification.

  - Replace technical file type identifiers with office-friendly labels.
  - Keep this a presentation-focused improvement and avoid changing comparison or sync logic.

## v0.6 — Synchronization Transparency (Released)

### Completed in v0.6.1

- Surface the existing recommendation reason in the confirmation workflow.
- Add optional access to decision context from selected compare rows.
- Keep the decision engine unchanged; this phase is about clarity and explanation.

### Completed in v0.6.2

- Add one narrow needs-attention review affordance to surface low-confidence items for user review.
- Reuse existing decision confidence data for discoverability, without changing comparison or sync logic.

### v0.6.3 — Stale-Item UX: **OPTIONAL / PARKED**
  - Not required at this time.
  - Existing stale-file safety and messaging are present.
  - Keep this phase on the shelf as a narrow office-user presentation refinement if future feedback shows confusion around stale-file outcomes.


## v0.5 - Synchronization Confidence (Completed)

V0.5 focuses on helping office users decide what is safe to copy before approval.

### Completed in v0.5.1

- Rich File Details refresh:
  - Better local/server context in the file inspection dialog.
  - Human-readable size and modification formatting.
  - File type and extension details.
  - Clearer missing-file messaging for one-side differences.
  - Added formatting utilities and tests used by the details dialog.

### Completed in v0.5.2

- Safer difference classification:
  - Added office-friendly recommendation confidence metadata on each comparison row.
  - Added low-confidence detection for equal timestamps + unequal size and close timestamp + size-change cases.
  - Added unit tests for heuristic decision behavior.

### Completed in v0.5.3

- Decision assistance for synchronization previews:
  - Surface recommendation/confidence in sync confirmation rows.
  - Count low-confidence files before execution.
  - Keep explicit uncertainty messaging visible at the approval step.

### Deferred (non-blocking)

- Advanced ignore include/override behavior remains intentionally deferred.

---

# Product Principles (Not an Active Milestone)

TraceSync should continue becoming more capable internally while remaining simple on the surface.

Future development should prioritize:

* synchronization safety
* user confidence
* predictable behavior
* clear previews
* understandable warnings
* reliable recovery
* minimal technical knowledge required from office users

Features should be evaluated against three questions:

1. Does this solve a real office pain point?
2. Does it simplify the user's workflow?
3. Would a typical office employee notice if the feature disappeared?

If the answer is no, the feature should generally remain deferred or belong in an advanced configuration area.

---

# Uncommitted Storage-Provider Direction

The current architecture intentionally preserves the `StorageProvider` abstraction so TraceSync can eventually work with storage beyond local and mapped filesystem folders.

Potential future storage providers may include:

* remote server storage
* network storage
* SFTP/SSH-based storage
* WebDAV
* cloud storage services

These are future capabilities and are not part of v0.10.0.

---

# Uncommitted Remote/Cloud Design Constraints

Remote and cloud synchronization is a longer-term capability.

When this milestone is eventually defined, it must be designed as more than simply adding another copy destination.

The architecture should account for:

### Authentication

* account authentication
* API tokens
* OAuth where appropriate
* SSH keys where appropriate
* session/token expiration

### Authorization

* read permissions
* write permissions
* provider-specific access scopes
* destination restrictions

### Credential Security

* secure operating-system credential storage where appropriate
* no plaintext passwords in project files
* no credentials stored in `.tracesyncignore`
* safe token handling and removal

### Transport Security

* secure communication channels
* protected credential transmission
* provider-specific secure APIs or protocols

### Remote Failure Handling

Remote synchronization must safely handle:

* connection loss
* timeouts
* authentication failures
* permission failures
* partial uploads
* partial downloads
* interrupted transfers
* retry/recovery scenarios

### Remote Conflict Handling

Remote files may change independently of TraceSync.

Future synchronization logic must therefore avoid assuming that:

> "The local timestamp is newer, therefore overwrite the remote file."

Provider-specific metadata, conflict detection, and safer recovery may be required.

### Provider Isolation

Remote authentication, transport, and provider-specific behavior should remain behind the storage-provider boundary.

The goal is:

```text
SyncService
    ↓
StorageProvider
    ↓
Remote Provider
    ↓
Authentication / Authorization / Transport
```

rather than making the synchronization engine understand individual cloud APIs.

---

# Intentionally Deferred

The following capabilities remain candidates for future milestones and should not be implemented merely for completeness:

* Advanced ignore include/override rules.
* Scheduled synchronization.
* Automatic synchronization.
* Real-time folder monitoring.
* Advanced conflict resolution.
* Backup and rollback workflows.
* File version history.
* Hash-based verification.
* Rename detection.
* Differential synchronization.
* Remote/cloud storage providers.
* Provider-specific authentication systems.
* Enterprise collaboration features.
* AI-assisted synchronization features.

These should be promoted into an active milestone only when their user value and implementation scope are clearly defined.

---

# Development Rules

TraceSync development follows these principles:

* One feature at a time.
* Prefer incremental changes over broad rewrites.
* Preserve working architecture.
* Keep responsibilities separated.
* Avoid unnecessary abstractions.
* Keep the normal user workflow simple.
* Test before declaring a phase complete.
* Keep documentation synchronized with implementation.
* Use `version_manager.py` for release bookkeeping.
* Use patch releases for completed phases within a milestone.
* Use minor releases for new roadmap milestones.

The repository remains the authoritative source of truth.

---

# Long-Term Direction (Vision, Not Commitment)

TraceSync should evolve from:

```text
Safe folder comparison
        ↓
Safe local/server synchronization
        ↓
Smart synchronization rules
        ↓
Improved synchronization safety
        ↓
Additional storage providers
        ↓
Secure remote/cloud synchronization
```

The priority remains:

> **Reliability before breadth.**

TraceSync should become more capable without becoming more complicated for the people who use it.
