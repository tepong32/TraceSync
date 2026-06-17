# TraceSync

## Overview

TraceSync is a Windows desktop utility designed to help users safely compare, review, and synchronize files between Local and Server folders.

Unlike traditional synchronization tools that immediately copy or overwrite files, TraceSync prioritizes visibility, review, and user control before any changes occur.

The application was created to address a common problem in government offices and shared-file environments:

> Users often know that files are different, but they do not know which version is newer, what changed, or whether copying a file will overwrite important work.

TraceSync provides a safer workflow that allows users to compare folders, review differences, and make informed synchronization decisions.

---

## Key Features

### Folder Comparison

* Recursive folder scanning
* Relative-path-based file matching
* Local vs Server comparison workflow
* Difference classification using modification timestamps

### Difference Detection

TraceSync identifies:

* Local Newer
* Server Newer
* Same
* Local Only
* Server Only

### Results Review

* Color-coded comparison results
* Summary statistics
* Quick filtering by status
* Active filter highlighting
* File-by-file review workflow

### User Experience

* Side-by-side Local and Server folder selectors
* Automatic restoration of previously selected folders
* Settings persistence
* Comparison progress feedback
* LGU-friendly workflow and terminology

### Safety-First Design

TraceSync intentionally follows:

Compare → Review → Confirm → Copy

before any synchronization actions occur.

---

## Why TraceSync Exists

Many synchronization tools focus on automation.

TraceSync focuses on confidence.

The goal is not to synchronize files as quickly as possible.

The goal is to help users understand:

1. What changed?
2. Which copy is newer?
3. What will happen if I copy?
4. Is it safe to proceed?

This approach helps reduce accidental overwrites and makes file synchronization easier for non-technical users.

---

## Current Status

Current Version: v0.2.0 (Development)

### Implemented

#### Core Engine

* FileRecord model
* Recursive folder scanner
* Relative-path comparison engine
* ComparisonResult model
* CompareStatus enum
* SyncService orchestration layer

#### User Interface

* Desktop GUI (Tkinter)
* Results Treeview
* Summary statistics bar
* Status bar
* Row color highlighting
* Quick filters
* Active filter highlighting
* Results section header
* Improved comparison workflow

#### Configuration

* SettingsService
* JSON-based settings persistence
* Automatic folder restoration
* Defensive settings handling

#### Layout Refresh

* Side-by-side Local and Server folder panels
* Dedicated comparison action area
* Synchronization action placeholders
* Improved spacing and workflow organization

---

## Comparison Statuses

| Status       | Meaning                                   |
| ------------ | ----------------------------------------- |
| Local Newer  | Local file has a newer modification date  |
| Server Newer | Server file has a newer modification date |
| Same         | Both copies match                         |
| Local Only   | Exists only in Local folder               |
| Server Only  | Exists only in Server folder              |

---

## File Identity Model

Files are matched using their relative path.

Example:

Finance/
└── Reports/
└── June.xlsx

and

Finance/
└── Reports/
└── June.xlsx

are treated as the same file identity even if timestamps differ.

Relative path serves as the source of truth during comparison.

---

## Architecture

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
│   ├── settings.py
│   └── backup.py
│
├── VERSION
│
└── requirements.txt
```

---

## Roadmap

### v0.2.x — Results Exploration

#### Planned

* File details dialog
* Double-click file inspection
* Local timestamp display
* Server timestamp display
* File size display
* About dialog
* Column sorting

---

### v0.3.x — Safe Synchronization

#### Planned

* Copy selected files
* Copy all differences
* Synchronization confirmation dialogs
* Dry-run preview
* Copy result summaries

#### Safety Features

* Automatic backup before overwrite
* Restore from backup
* Synchronization error reporting

---

### v0.4.x — Productivity Features

#### Planned

* Search and filtering enhancements
* Hide Same Files toggle
* Export comparison reports
* Recent folder history
* Open containing folder
* Open selected file

---

### v0.5.x — Advanced File Inspection

#### Planned

* Excel workbook comparison
* Changed worksheet detection
* Changed row detection
* Changed cell detection
* Difference review dialog

Example:

Workbook: Budget.xlsx

Changed Sheets:

* Payroll
* Expenses

Potential Future Enhancements:

* Cell-level value comparison
* Change summaries
* Review-focused conflict inspection

This feature is intended to help users identify where changes occurred without manually reviewing entire workbooks.

---

## Future Considerations

The following features are intentionally deferred:

* Real-time synchronization
* Automatic synchronization
* Background file watchers
* Hash-based verification
* Manifest databases

TraceSync will continue prioritizing transparency and user confidence over aggressive automation.

---

## Design Goals

* Windows-first experience
* LGU-friendly workflow
* Minimal learning curve
* Safe synchronization practices
* Prevent accidental overwrites
* Clear comparison results
* Simple and maintainable architecture

---

## Long-Term Vision

TraceSync began as a standalone utility for comparing Local and Server folders.

The long-term goal is to evolve it into a review-first synchronization platform that helps organizations understand file changes before synchronization occurs.

Future versions may integrate with TracePoint and other document management workflows where auditability, visibility, and safe synchronization are critical.
