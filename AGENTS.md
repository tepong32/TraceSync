# TraceSync Development Guide

This document defines the development standards, architectural decisions, and coding conventions for TraceSync. All contributors (human or AI) should follow these guidelines unless a change is intentionally approved.

---

# Project Vision

TraceSync is a lightweight Windows desktop application that helps users safely compare and synchronize folders.

Primary goals:

* Simplicity
* Reliability
* Predictability
* Safety

The application is intended for non-technical users, particularly office environments where accidental overwrites must be prevented.

When making implementation decisions, prioritize clarity and maintainability over cleverness.

---

# Development Philosophy

## Build Small

Every commit should represent one logical feature or improvement.

Avoid mixing unrelated work into the same commit.

Good examples:

* feat: add File Details dialog
* feat: implement Treeview sorting
* refactor: move dialogs into dedicated package

Avoid commits like:

* misc fixes
* updates
* changed stuff

---

## MainWindow is the Conductor

`MainWindow` should coordinate the application.

It should NOT become responsible for every piece of application logic.

As features grow, move responsibilities into dedicated modules.

Examples:

Dialogs

* FileDetailsDialog
* FolderPairManagerDialog
* AboutDialog

Menus

* ResultsContextMenu

Utilities

* Treeview sorting
* Formatting helpers

Services

* Folder comparison
* Synchronization
* Backup and restore
* Settings

---

# Separation of Responsibilities

Business logic belongs inside Services.

UI logic belongs inside UI classes.

Dialogs display information.

Dialogs should never perform folder scans or synchronization.

Models should remain lightweight dataclasses.

---

# Modularization Rule

If a feature:

* exceeds roughly 100 lines,
* has its own responsibility,
* or can be reused,

consider moving it into its own module.

Avoid growing `main_window.py` unnecessarily.

---

# UI Guidelines

The interface should resemble a modern Windows desktop utility.

Prefer:

* clear labels
* predictable layouts
* Explorer-like behavior
* minimal surprises

Avoid unnecessary animations or visual clutter.

---

# Results Table

The Treeview is the primary workspace.

Features should improve usability without making the interface confusing.

Examples:

* column sorting
* context menus
* double-click actions
* keyboard shortcuts

---

# File Operations

Safety takes priority over speed.

Never overwrite files silently.

Every destructive action should require explicit confirmation.

Future synchronization features should always support backup or recovery where practical.

---

# ComparisonResult

ComparisonResult should preserve enough information to avoid rescanning the filesystem.

Prefer storing references to FileRecord objects instead of repeatedly querying the disk.

---

# Versioning

Features should be developed in milestone branches.

Example:

v0.4.3-synchronization

Commits should remain focused and descriptive.

---

# Code Style

Prefer readable code over compact code.

Favor explicit variable names.

Keep functions focused on one responsibility.

Avoid deeply nested logic where possible.

---

# Future Architecture

Target structure:

ui/
dialogs/
menus/
widgets/
utils/

core/
scanner.py
comparer.py
sync_service.py
storage_provider.py
local_storage_provider.py
storage_scanner.py
sync_job_runner.py
backup_service.py
backup_store.py

models/

utils/

---

## Project Workflow

Every feature should follow this workflow:

1. Plan the feature.
2. Identify affected modules.
3. Update AGENTS.md if architecture changes.
4. Implement one logical feature per commit.
5. Review for duplication and maintainability.
6. Update CHANGELOG and README when appropriate.

---

## Milestone-Based Development

Development is organized around milestones rather than version numbers.

Each milestone should have one primary objective.

Examples:

* Results Exploration
* Synchronization
* Explorer Polish

Do not introduce unrelated features into an active milestone.

---

## Documentation Rules

Update documentation whenever:

* architecture changes
* folder structure changes
* public features change
* setup instructions change
* user-visible behavior changes

Internal refactoring alone usually does not require README updates.

---

## Project Hygiene

Avoid leaving TODO comments in released code.

Instead:

* create a roadmap item
* create an issue
* schedule the work for a future milestone

Released code should represent completed functionality.

---

# AI Assistant Guidelines

Do not invent models or business logic.

Do not rename existing fields without explicit approval.

Reuse existing services whenever possible.

Prefer extending existing architecture over replacing it.

When introducing new UI features:

1. Check whether the feature deserves its own module.
2. Keep MainWindow focused on orchestration.
3. Avoid duplicate logic.
4. Keep saved-workflow configuration in settings/services rather than embedding persistence rules in dialogs.

For recurring folder workflows, prefer named Folder Pairs over multi-job dashboards. A Folder Pair changes the current comparison endpoints; it must not bypass the existing compare → review → confirm → sync safety flow.

When uncertain, choose the solution that is easier to maintain rather than the one requiring fewer lines of code.

---

# Definition of Done

A feature is considered complete only when:

* implementation is complete
* UI is polished
* edge cases are handled
* code is modular
* naming is consistent
* unnecessary duplication is removed

If a feature feels unfinished, it probably is.

---

Build software that future-you will enjoy maintaining.

## Project context and documentation map

Python Windows desktop folder comparison and synchronization utility. UI orchestrates services; provider-neutral storage models separate planning, approved execution, history, backup and remote transport.

### Durable boundaries

Preserve compare-review-confirm-sync, truthful history, service/UI separation and the safety contracts implemented on this branch. Application owners generate valid backup artifacts; synchronization does not establish restore acceptance. Provider/backup/SFTP developments must be integrated and validated separately before being described as released capabilities.

### Development state

Published master is the v0.10 documentation/product-tour baseline. docs/ROADMAP.md records Backup Before Overwrite as development work; later conditional-provider, backup and SFTP code on development branches is not merged here.

### Read next

- [README.md](README.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)
- [CHANGELOG.md](CHANGELOG.md)
- [Continuation entry point](CONTINUE.md)

### Project validation

Start with affected unittest modules under tests/. Broaden across synchronization, history, settings and UI when shared behavior changes. For future backup/provider/SFTP integration, add corresponding safety and explicit test-endpoint checks; missing environment or credentials is not a pass.

## Repository continuity and proportional testing

- Maintain this root AGENTS.md in version control as portable operational context. Preserve applicable nested instructions. Update it in the same phase as durable architecture, security, integration, major completion/deferral or testing-policy changes.
- Keep this file concise: identity, boundaries, decisions and a documentation map. Replace stale summaries; never append transcripts, line-by-line diaries or duplicate full specifications.
- Before substantial work read AGENTS.md, CONTINUE.md (and its canonical handoff target), the relevant roadmap/architecture/feature documents, recent Git history/status and affected tests. Reconcile stale snapshots against source; do not ask the user to repeat documented context.
- At task completion update the canonical handoff for immediate state, actual validation, blockers and next steps; update the roadmap for agreed direction changes and specialized architecture/feature/audit/testing documents where applicable. Cross-link instead of duplicating them. Do not invent completed phases or new priorities.
- Test the changed area first: direct unit/feature tests, related integration tests and dependent regressions. Expand for shared models/services/utilities, auth/permissions, middleware, schema/migrations, settings/environments, shared UI, cross-app APIs, reporting, jobs or build/deployment changes. Uncertain impact requires broader validation.
- Full suites are appropriate for broad refactors, cross-module/security/infrastructure changes, major milestones and release/production gates, not automatically every isolated edit. Preserve stricter project-specific safety, reachability, hardware and release checks.
- Record relevant commands, scope rationale and outcomes in the handoff or appropriate validation report: PASS; FAIL - CAUSED BY CURRENT WORK; FAIL - PRE-EXISTING (with evidence); NOT RUN - OUT OF SCOPE (with rationale); NOT RUN - ENVIRONMENTAL (with limitation).
- Investigate failures before calling them unrelated. Fix regressions caused by the change and document evidence for pre-existing failures. A skipped test or unperformed human/operational acceptance is never a pass.
- Keep documentation, code and validation evidence sufficient for a fresh session to resume without a conversation transcript.
- Install additional standalone software/tooling under C:/xxx/_INSTALLS/_HERE/_xxx unless the user specifies otherwise.
