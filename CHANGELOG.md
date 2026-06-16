# Changelog
## [0.1.4] - 2026-06-16
### ✨ Added
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
