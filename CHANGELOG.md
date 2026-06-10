# Changelog
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
