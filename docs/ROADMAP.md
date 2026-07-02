# TraceSync Roadmap

> **"Simple. Safe. Predictable."**

This roadmap serves as the primary development tracker for TraceSync.

Development follows **milestone-based planning**. Each milestone focuses on delivering one major user capability before moving to the next.

---

# Current Project Status

| Item              | Value                              |
| ----------------- | ---------------------------------- |
| Current Version   | **v0.3.1**                         |
| Current Branch    | **v0.3.1-sync-confirmation**       |
| Current Milestone | **Synchronization**                |
| Status            | 🚧 In Progress                     |

---

# Development Philosophy

TraceSync is developed around **milestones**, not feature dumps.

Each milestone should deliver one complete capability to the user.

Before moving to the next milestone:

* All planned features should be complete.
* Code should be reviewed.
* Documentation should be updated.
* The application should remain stable.

Avoid introducing unrelated features into an active milestone.

---

# Versioning Strategy

TraceSync follows milestone-based semantic versioning.

## Minor Versions

A **minor version** starts a new roadmap milestone.

Examples:

- v0.2.x — Results Exploration
- v0.3.x — Synchronization
- v0.4.x — Explorer Polish

## Patch Versions

A **patch version** represents a completed, stable phase within the current milestone.

Each patch should:

- implement one complete capability
- keep the application stable
- be safe to merge into master

Example:

v0.3.0
Synchronization milestone begins

↓

v0.3.1
Candidate Selection

↓

v0.3.2
Synchronization Confirmation

↓

v0.3.3
Synchronization Engine

↓

v0.3.4
SyncResult Architecture

↓

v0.3.5
Progress & Auto Refresh

---

# Completed Milestones

## v0.1.0 — Foundation

**Goal**

Build the initial folder comparison application.

### Completed

* [x] Project structure
* [x] Folder scanning
* [x] Recursive comparison
* [x] Comparison engine
* [x] Basic Treeview results
* [x] Compare button
* [x] Initial synchronization service structure

---

## v0.1.1 — Comparison Summary

**Goal**

Provide users with meaningful comparison statistics.

### Completed

* [x] CompareStatus enum
* [x] Summary statistics bar
* [x] Status counting
* [x] Improved comparison presentation

---

## v0.1.2 — Visual Feedback

**Goal**

Make comparison results easier to understand.

### Completed

* [x] Treeview row color highlighting
* [x] Status-based coloring
* [x] Improved readability

---

## v0.1.3 — Filtering

**Goal**

Allow users to focus on relevant comparison results.

### Completed

* [x] Filter buttons
* [x] Active filter highlighting
* [x] Persistent filter after comparison
* [x] Status bar updates

---

## v0.1.4 — Settings Persistence

**Goal**

Remember user preferences between sessions.

### Completed

* [x] SettingsService
* [x] settings.json support
* [x] Restore Local Folder
* [x] Restore Server Folder
* [x] Defensive handling of missing settings

---

## v0.2.0 — Layout Refresh

**Goal**

Improve usability and overall application layout.

### Completed

* [x] Side-by-side folder panels
* [x] Improved spacing
* [x] Results section header
* [x] Compare button prominence
* [x] Action bar placeholders
* [x] Status bar improvements
* [x] README overhaul

---

## v0.2.1 — Results Exploration

**Goal**

Allow users to inspect comparison results before synchronization.

### Completed

- [x] File Details dialog
- [x] Double-click Treeview support
- [x] Friendly status descriptions
- [x] Local/Server file information
- [x] File size formatting
- [x] Timestamp formatting
- [x] Missing file handling
- [x] Copy Path functionality
- [x] Dialog population helper refactoring
- [x] ComparisonResult-based dialog (no filesystem rescans)
- [x] Esc key closes dialog
- [x] Removed development-only testing UI

---

# 🚧 Current Milestone

## v0.3.x — Synchronization

**Goal**

Safely synchronize files while preserving a clean service-oriented architecture.

### Phase 1 — Candidate Selection ✅

- [x] Added SyncService candidate selection helpers.
- [x] Centralized synchronization eligibility rules.
- [x] Added shared candidate collection helper.
- [x] Connected synchronization button availability to SyncService.
- [x] Removed synchronization business logic from MainWindow.

### Phase 2 — Confirmation Dialog

- [ ] Display synchronization direction.
- [ ] Display number of files to synchronize.
- [ ] Display destination folder.
- [ ] Display overwrite warning.
- [ ] Allow user confirmation or cancellation.

### Phase 3 — Synchronization Engine

- [ ] Copy Local → Server
- [ ] Copy Server → Local
- [ ] Preserve timestamps (shutil.copy2)
- [ ] Automatically create destination folders
- [ ] Safe bulk synchronization

### Phase 4 — SyncResult

- [ ] Introduce SyncResult dataclass.
- [ ] Return structured synchronization results.
- [ ] Eliminate primitive synchronization return values.

### Phase 5 — Progress & Refresh

- [ ] Progress indicator.
- [ ] Status bar updates.
- [ ] Automatically rerun comparison.
- [ ] Refresh Treeview.
- [ ] Refresh summary statistics.

---

# Planned Milestones

## v0.4.0 — Explorer Polish

**Goal**

Make TraceSync feel like a polished Windows desktop application.

### Planned

* [ ] Status icons
* [ ] Search/filter by filename
* [ ] Remember column widths
* [ ] Export comparison report (CSV)
* [ ] Drag & Drop folder selection
* [ ] Keyboard shortcuts

---

## v0.5.0 — Intelligent Comparison

**Goal**

Provide deeper file analysis beyond timestamps.

### Planned

* [ ] File hash comparison
* [ ] Detect renamed files
* [ ] Detect identical content
* [ ] Ignore configurable folders
* [ ] Ignore configurable extensions

---

## v0.6.0 — Excel Awareness

**Goal**

Improve comparison of Microsoft Excel files.

### Planned

* [ ] Workbook metadata
* [ ] Worksheet differences
* [ ] Sheet count comparison
* [ ] Workbook summary
* [ ] Preview changed worksheets

---

## v0.7.x — Backup & Recovery

* [ ] TBD

---

## Future Ideas

These are intentionally outside the current roadmap.

Potential future enhancements include:

* Synchronization history
* Automatic scheduled comparisons
* File version history
* Backup browser
* Plugin architecture
* Dark mode
* Multi-folder comparison
* Portable edition
* Installer package
* GitHub Releases automation

---

# Definition of Done

A milestone is complete when:

* [x] All planned features are implemented.
* [x] Code is modular.
* [x] Documentation is updated.
* [x] No unfinished TODOs remain.
* [x] The application is stable.
* [x] The release is ready to tag.

---

*"Good software is not built by adding features endlessly.*

*It is built by completing one meaningful milestone at a time."*
