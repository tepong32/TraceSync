# TraceSync Roadmap

> **Simple. Safe. Predictable.**

TraceSync is developed in focused milestones. A milestone is complete only when its user-facing workflow, documentation, and validation are complete.

The repository is the authoritative source of truth for the current implementation and release state.

---

## Current Release

| Item      | Value                     |
| --------- | ------------------------- |
| Version   | **v0.5.0**                |
| Milestone | **Smart Synchronization** |
| Status    | **Completed**             |

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

## v0.3.x â€” Synchronization

Completed synchronization foundation:

* One-way Local â†’ Server synchronization.
* One-way Server â†’ Local synchronization.
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

# v0.4.x â€” Smart Synchronization

The v0.4 milestone focused on making TraceSync smarter about which files should participate in comparison and synchronization while keeping the normal office workflow simple.

## v0.4.1 â€” Ignore Engine Foundation

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

## v0.4.2 â€” Project Ignore Support

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

## v0.4.3 â€” User-Configurable Ignore Rules

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
      â†“
IgnoreLoader
      â†“
IgnoreRuleEngine
      â†“
StorageScanner
      â†“
Comparison / Preview / Synchronization
```

Advanced include/override behavior is intentionally deferred.

The current ignore system should remain simple unless a real office workflow demonstrates a need for additional rule complexity.

---

# Next Milestone

## v0.5 - Synchronization Confidence (In Progress)

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

### Planned in v0.5

- Optional preview reason drill-down before synchronization.

Before beginning v0.5 development:

1. Review the current backlog and deferred features.
2. Identify the most valuable office workflow problem.
3. Define the milestone goal.
4. Select a small number of cohesive features.
5. Establish the milestone boundary before implementation.
6. Implement one feature or phase at a time.
7. Validate the complete user-facing workflow before release.

---

# Product Direction

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

# Future Storage Providers

The current architecture intentionally preserves the `StorageProvider` abstraction so TraceSync can eventually work with storage beyond local and mapped filesystem folders.

Potential future storage providers may include:

* remote server storage
* network storage
* SFTP/SSH-based storage
* WebDAV
* cloud storage services

These are future capabilities and are not part of the current v0.5.0 release.

---

# Future Remote and Cloud Synchronization

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
    â†“
StorageProvider
    â†“
Remote Provider
    â†“
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

# Long-Term Direction

TraceSync should evolve from:

```text
Safe folder comparison
        â†“
Safe local/server synchronization
        â†“
Smart synchronization rules
        â†“
Improved synchronization safety
        â†“
Additional storage providers
        â†“
Secure remote/cloud synchronization
```

The priority remains:

> **Reliability before breadth.**

TraceSync should become more capable without becoming more complicated for the people who use it.


