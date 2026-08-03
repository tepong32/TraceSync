# Changelog
## [0.3.4] - 2026-08-03
### ✨ Added
Smart Synchronization Phase 1 (Ignore Engine Foundation)

- Introduced the IgnoreRuleEngine as the centralized component for evaluating synchronization ignore rules.
- Added the IgnoreRule model and RuleSource enumeration to support extensible rule management.
- Implemented built-in ignore patterns for common system, temporary, and development-generated files.
- Enhanced the StorageScanner to filter ignored files before entering the comparison pipeline.
- Integrated the IgnoreRuleEngine into SyncService using dependency injection while preserving separation of concerns.
- Established the architectural foundation for future .tracesyncignore support, user-defined ignore rules, and include/override capabilities.
- Adopted the project design principle: TraceSync prioritizes office workflows over technical workflows, keeping synchronization simple for non-technical users.

## [0.3.3] - 2026-07-31
### ✨ Added
- Release v0.3.3: synchronize folders safely with reviewed previews, background progress, cancellation, and provider-ready storage services.

## [0.3.2] - 2026-07-30
### Added
- Completed the reviewed synchronization workflow: preview, confirmation, background job, progress, cancellation, and completion summary.
- Added provider-based storage abstractions and a local filesystem provider for future storage backends.
- Added reusable synchronization preview and job models, plus filesystem-level synchronization tests.
- Added just-in-time source and destination validation so files changed after confirmation are skipped instead of copied over silently.

### Changed
- SyncService now orchestrates storage providers and generates an immutable copy plan before a job starts.
- Updated the main window synchronization buttons from placeholders to safe one-way copy actions.

## [0.3.0] - 2026-06-26
### ✨ Added
Finished results exploration enhancements:
- Added File Details dialog for inspecting comparison results
- Implemented double-click support to open file details from the Results list
- Added human-friendly status descriptions for comparison results
- Displayed detailed Local and Server file information (path, modified date, file size)
- Added automatic formatting for file sizes (B, KB, MB, GB)
- Added automatic formatting for file modification timestamps
- Added graceful handling of missing Local/Server files in the details dialog
- Added Copy Path functionality for Local and Server file paths
- Refactored dialog population into reusable helper methods for improved maintainability
- Improved dialog architecture by using ComparisonResult directly without additional filesystem access
- Added keyboard shortcut (Esc) to quickly close the File Details dialog
- Removed development-only Test Dialog after integration

## [0.2.0] - 2026-06-17
### ✨ Added
feat(ui): complete v0.1.5 layout refresh and UX improvements

- add side-by-side folder selector panels
- add settings persistence and folder restoration
- add active filter highlighting
- improve compare button visibility
- add comparison progress feedback
- reorganize workflow layout
- add results section header
- add synchronization action bar foundation
- improve usability for non-technical users

## [0.1.4] - 2026-06-16

### ✨ Added
feat: remember last selected folders

- Added SettingsService
- Added settings.json persistence
- Local folder selection now persists between sessions
- Server folder selection now persists between sessions
- Folder paths automatically restore on startup

## [0.1.3] - 2026-06-16
### ✨ Added
feat: improve comparison results UX

- Added color-coded Treeview rows based on CompareStatus
- Added filter buttons for comparison statuses
- Added persistent filter state across comparisons
- Added status bar showing current filtered view
- Refactored Treeview population into reusable helper
- Improved navigation of large comparison result sets

## [0.1.2] - 2026-06-10
### ✨ Added
TraceSync v0.1.2 progress

- Added CompareStatus enum as centralized status source
- Migrated comparison engine from string statuses to enums
- Updated ComparisonResult typing to use CompareStatus
- Fixed Treeview display labels after enum migration
- Added summary statistics bar showing:
  - Local Newer
  - Server Newer
  - Same
  - Local Only
  - Server Only
- Established foundation for filtering, row colors, and future reporting

## [0.1.1] - 2026-06-10
### ✨ Added
- working comparer + gui window with folder selection option now working

## [0.1.0] - 2026-06-10
initial commit
### ✨ Added
- FileRecord model
- Recursive folder scanner
- Folder comparison engine
- SyncService
- Initial Tkinter GUI
- Results Treeview
