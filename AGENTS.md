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
* AboutDialog

Menus

* ResultsContextMenu

Utilities

* Treeview sorting
* Formatting helpers

Services

* Folder comparison
* Synchronization
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

v0.2.1-results_exploration

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
