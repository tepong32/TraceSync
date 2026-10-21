# Provider completion plan

Approved 2026-10-21: finish the planned cloud workflows on separate provider
branches, then provide an exact owner setup checklist before standalone packaging.
This plan extends the accepted OneDrive-first direction; it does not authorize
publishing, real-account access, background sync, deletion mirroring or silent
replacement. Tests may use dummy public client IDs; a dummy build must never be
represented as usable cloud authentication.

## Branches and preserved work

- `codex/onedrive-provider-completion`, worktree
  `C:/Users/Administrator/.codex/worktrees/tracesync-onedrive-completion`, starts
  at local Gate B checkpoint `ec009ffb3a06f7218b0e9563f91e96befa5d977a`.
- `codex/google-drive-provider-completion` uses its own worktree at
  `C:/Users/Administrator/.codex/worktrees/tracesync-google-drive-completion` from
  this reviewed foundation. Import
  only reviewed provider-specific changes from remote Google checkpoint `8cec558`;
  do not merge its obsolete settings, UI, dependency or version history wholesale.
- Preserve the original dirty SFTP and pair-management worktrees. Reuse the four
  saved-pair implementation/test files from pair management after checking their
  base compatibility; do not copy its stale handoff or release metadata.
- Dropbox remains a later candidate in CLOUD_STORAGE.md, not an implemented or
  accepted provider. Reassess it after the two committed provider milestones rather
  than advertising a placeholder connector. SFTP is outside consumer scope.

## Required outcomes

1. OneDrive: connect, choose folder, save/reopen/edit/delete pairs, exact-account
   renewal and disconnect, comparison, reviewed transfers, cancellation and honest
   partial/unknown history. Finish packaged public app configuration without
   secrets or environment-variable setup for ordinary users.
2. Keep create-only operations safe. Conditional replacement plus verified backup
   and recovery remains an explicit product requirement, requiring separate
   implementation/evidence; the current disabled replacement is not its completion.
   Do not enable it based on an offline success or a preflight metadata check.
3. Google: reconcile the existing read/download implementation with the newer
   provider/service/UI foundation, validate actual supported desktop authorization
   and folder access, account-scoped protected credentials, pairs and reviewed
   transfers. Resolve full-folder scope and duplicate-name/create semantics. An
   empty or partial scan must not be presented as a complete folder sync.
4. Tests must cover offline services, UI, auth, failure/cancel/conflict and shared
   synchronization/history/settings regressions. Keep live Windows/cloud/package
   evidence distinct. No fake credential, silent broadening of consent or mocked
   API response can satisfy these operational acceptance gates.
5. Produce owner instructions with exact public registration values, local config
   paths, portal steps, consent/scope choices and disposable-account test steps.
   Never request passwords, access/refresh tokens, private keys or client secrets
   in chat. The owner signs in through the system browser only.

## Completion gate

Remaining engineering work, owner setup, live acceptance and packaging are distinct
columns in the final readiness report. Do not claim that app IDs are the only
remaining inputs while code/design/test gaps remain. Standalone packaging follows
provider integration and required acceptance; no executable or public release is
authorized by this development plan alone.

## Standalone settings readiness

Use per-user APPDATA/TraceSync/settings.json so starting from an installed or
read-only working directory does not require elevation. Preserve the existing
atomic save operation. Load an existing legacy working-directory settings file
only when no per-user file exists; save to the new location without deleting or
rewriting the legacy file. Explicit test settings paths must never adopt a real
legacy configuration. This is a shared standalone prerequisite on both branches.

## Recovery preparation before remote replacement

Implement read-only OneDrive backup materialization through the existing local
BackupService, sharing the verified download path and rejecting changed metadata
or wrong size. This does not enable replacements, advertise conditional transfer,
or claim that remote restore works. Final commit-time protection and cloud recovery
remain separate gates; no fictitious preconditions or speculative retries.

## Remaining transport decisions

OneDrive's upload-session If-Match at session creation is not evidence that a
later final write is conditional. The documented explicit commit example includes
If-Match but addresses a parent path; prove the intended existing-item binding,
personal-account behavior and verified backup/restore path before enabling
replacement. Do not add a check-then-write substitute. Unknown final outcomes
remain unknown and are never blindly retried. No live account is available here.

Google pre-generated IDs prevent a repeated create from producing another item
with that same ID; they do not reserve a name against another client. Folder-path
absence therefore cannot be represented as atomic conditional create. Keep uploads
disabled until the product's identity/conflict contract is explicitly resolved.
Google Workspace documents, shortcuts and Windows-name collisions currently block
the comparison rather than disappearing from a supposedly complete scan.

Downloads preserve reviewed modification time on staged content. OneDrive upload
client time and round-trip comparison now have offline coverage for empty and
nonempty files; see the active timestamp slice below. Live server precision and
behavior still need acceptance. Equal timestamp alone is not a content-integrity
guarantee.

These are engineering gates, not requests for owner secrets. Offline tests cannot
prove endpoint semantics. Residual parent-link TOCTOU, local backup-protected
replacement limitations and post-crash remote-folder accounting remain documented.

References checked 2026-10-21:
- https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/resources/filesysteminfo?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/resources/driveitemuploadableproperties?view=graph-rest-1.0
- https://developers.google.com/workspace/drive/api/guides/create-file
- https://developers.google.com/workspace/drive/api/guides/manage-uploads

## Active upload timestamp slice

Use OneDrive fileSystemInfo.lastModifiedDateTime (client time) for comparison,
keeping eTag as the source change identity. Supply reviewed client time in upload
session metadata. For the existing zero-byte create-only PUT, update only the
newly returned item ID's client timestamp with its returned eTag in If-Match;
never update by path, retry, or mutate when a version is unavailable. A failed or
uncertain metadata update after confirmed content creation must remain a copied
file with an honest history note, not a failed/unknown byte transfer. This is not
content replacement or remote restore. Preserve 100-nanosecond RFC3339 precision
rather than silently truncating NTFS timestamps to Python datetime microseconds.
Exercise this with fake Graph and native filesystem fixtures; live behavior remains
an acceptance gate. See the Graph update and fileSystemInfo references below.

- https://learn.microsoft.com/en-us/graph/api/driveitem-update?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/resources/filesysteminfo?view=graph-rest-1.0

Confirmed-copy notes are also displayed in the ordinary sync summary in an amber,
read-only scrolling area. They do not increment failed-file counts or disappear
behind a successful summary; durable per-file history retains the same notes.

## Preparation checkpoint and pause

The user authorized local non-release source checkpoints on 2026-10-21 and a pause
until returning tomorrow. These are preparation, not completed provider/release
milestones. Existing write restrictions and acceptance gates remain unchanged.
CONTINUE.md is the resume entry point. No integration, push, tag or build.
