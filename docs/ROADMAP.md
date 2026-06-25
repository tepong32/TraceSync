# TraceSync Roadmap

> **"Simple. Safe. Predictable."**

This roadmap serves as the primary development tracker for TraceSync.

Development follows **milestone-based planning**. Each milestone focuses on delivering one major user capability before moving to the next.

---

# Current Project Status

| Item              | Value                          |
| ----------------- | ------------------------------ |
| Current Version   | **v0.2.0**                     |
| Current Branch    | **v0.2.1-results_exploration** |
| Current Milestone | **Results Exploration**        |
| Status            | 🚧 In Progress                 |

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

# 🚧 Current Milestone

# v0.2.1 — Results Exploration

**Goal**

Allow users to inspect comparison results before any synchronization actions.

### Progress

* [x] Infrastructure folders
* [x] AGENTS.md
* [x] Project workflow established
* [x] ComparisonResult preserves FileRecord references

### Remaining

* [ ] File Details dialog
* [ ] Double-click row action
* [ ] Results context menu
* [ ] Open Local File
* [ ] Open Server File
* [ ] Open Local Folder
* [ ] Open Server Folder
* [ ] Treeview column sorting
* [ ] Auto-size Treeview columns
* [ ] About dialog
* [ ] VERSION file support

---

# Planned Milestones

## v0.2.2 — Synchronization

**Goal**

Safely synchronize files between folders.

### Planned

* [ ] Copy Local → Server
* [ ] Copy Server → Local
* [ ] Confirmation dialogs
* [ ] Progress dialog
* [ ] Backup before overwrite
* [ ] Synchronization summary

---

## v0.2.3 — Explorer Polish

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

## v0.3.0 — Intelligent Comparison

**Goal**

Provide deeper file analysis beyond timestamps.

### Planned

* [ ] File hash comparison
* [ ] Detect renamed files
* [ ] Detect identical content
* [ ] Ignore configurable folders
* [ ] Ignore configurable extensions

---

## v0.4.0 — Excel Awareness

**Goal**

Improve comparison of Microsoft Excel files.

### Planned

* [ ] Workbook metadata
* [ ] Worksheet differences
* [ ] Sheet count comparison
* [ ] Workbook summary
* [ ] Preview changed worksheets

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
