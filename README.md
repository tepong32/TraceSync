# TraceSync

TraceSync is a Windows desktop utility designed to help users safely compare and synchronize folders without the risks commonly associated with automatic sync tools.

The project focuses on visibility, transparency, and safety before any file copy operations occur.

Instead of immediately syncing files, TraceSync helps users answer three questions:

1. What is different?
2. Why is it different?
3. What will happen if I copy?

---

## Current Status

Current Version: v0.1.3 (Development)

Implemented:

- Folder scanning
- Relative-path-based file matching
- File comparison engine
- Difference classification
- CompareStatus enum
- Basic desktop GUI
- Comparison results Treeview
- Summary statistics bar
- Row color coding
- Quick filter buttons
- Status bar

---

## Core Philosophy

TraceSync is intentionally designed around a:

Compare → Review → Confirm → Copy

workflow.

The goal is to prevent accidental overwrites while remaining simple enough for non-technical users.

---

## File Identity Rule

Files are matched using their relative path.

Example:

Left Folder:

Finance/
└── Reports/
    └── June.xlsx

Right Folder:

Finance/
└── Reports/
    └── June.xlsx

These are considered the same file identity regardless of:

- Modified date
- File size
- Creator information

Relative path serves as the source of truth.

---

## Comparison Statuses

| Status | Meaning |
|----------|----------|
| Local Newer | Local file has a newer modification date |
| Server Newer | Server file has a newer modification date |
| Same | Both files have matching modification dates |
| Local Only | File exists only in Local Folder |
| Server Only | File exists only in Server Folder |

---

## Project Structure

```text
tracesync/
│
├── main.py
│
├── ui/
│   └── main_window.py
│
├── core/
│   ├── scanner.py
│   ├── comparer.py
│   ├── copier.py
│   └── sync_service.py
│
├── models/
│   ├── compare_status.py
│   ├── file_record.py
│   └── comparison_result.py
│
├── utils/
│   └── backup.py
│
├── assets/
│
└── requirements.txt
```

---

## Release History

### v0.1.3

- Added row color highlighting for comparison results
- Added filter buttons for all comparison statuses
- Added status bar with active view information
- Preserved selected filter across comparisons
- Improved comparison result navigation

### v0.1.2

- Added CompareStatus enum
- Migrated comparison engine to enum-based statuses
- Added summary statistics bar
- Established foundation for filtering and row styling

### v0.1.1

- Initial comparison workflow
- Folder scanning
- File matching
- Difference classification
- Desktop GUI


## Roadmap

### v0.1.x — Comparison Experience

#### Completed

- [x] FileRecord model
- [x] Recursive folder scanner
- [x] Comparison engine
- [x] SyncService orchestration
- [x] Desktop GUI
- [x] Results Treeview
- [x] CompareStatus Enum
- [x] Summary statistics bar
- [x] Row color coding
- [x] Quick filter buttons
- [x] Status bar

#### Planned

- [ ] Left / Right folder layout
- [ ] Side-by-side folder selectors
- [ ] Remember last folders
- [ ] File details dialog
- [ ] Column sorting

---

### v0.2.x — Safe Copying

#### Planned

- [ ] Copy selected files
- [ ] Copy all differences
- [ ] Copy confirmation dialog
- [ ] Dry-run preview
- [ ] Copy result summary

#### Safety Features

- [ ] Automatic backup before overwrite
- [ ] Restore from backup
- [ ] Error reporting

---

### v0.3.x — Usability Enhancements

#### Planned

- [ ] Search box
- [ ] Hide Same Files toggle
- [ ] Recent folder history
- [ ] Export comparison report
- [ ] Open containing folder
- [ ] Open selected file

---

## Future Considerations

The following features are intentionally deferred:

- Real-time synchronization
- Automatic synchronization
- Background file watchers
- Hash-based verification
- Manifest databases

These may be introduced in later versions if they can be implemented without compromising safety and transparency.

---

## Design Goals

- Windows-first experience
- LGU-friendly workflow
- Minimal learning curve
- Prevent accidental overwrites
- Prioritize user confidence over automation
- Simple architecture and maintainability

---

## Long-Term Vision

TraceSync began as a standalone utility for comparing local and server folders.

Future versions may integrate with TracePoint and other document management workflows where file visibility, auditability, and safe synchronization are critical.

