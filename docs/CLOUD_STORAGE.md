# Cloud storage provider plan

## Current create-only safety audit

The clean `codex/onedrive-create-safety-audit` branch starts from published source
v0.15.0 (4ddfd55), which already implemented empty uploads and folder creation.
This local audit adds immutable folder evidence, fresh root/parent-link checks,
selected-file folder warnings, definite-failure classification and partial-folder
history notes. 233 offline tests pass after corrective review. No new commit, integration or binary release.
See [validation and provider evidence](ONEDRIVE_CREATE_VALIDATION.md) for exact
commands, the mission test matrix and unverified live/cache/packaged gates.
Both directions remain create-only. Earlier branch snapshots below are historical.


## Active reviewed-copy branch

`codex/onedrive-reviewed-copy` starts from published source checkpoint v0.13.0
(d18f494). The setup branch is integrated into master; no cloud executable has
been published. Public download remains v0.11.0.

The current offline-tested slice adds saved-pair reopening, exact MSAL account
selection for silent renewal, explicit reconnect with independent Graph account/
drive/folder checks, and account-scoped cache removal. Optional auth_account_id is
non-secret persisted identity; old pairs require explicit reconnect before cache
binding. Mismatches, lost access and unavailable local folders block reopening.
Use saved pair activates verified endpoints in the main workspace. Comparison is
read-only and runs off the UI thread. Existing review, confirmation and durable
history now cover new-file uploads/downloads. Each Graph request renews the exact
account token; signed transfer URLs never receive bearer credentials. Upload
sessions explicitly fail on conflicts and validate completion; ambiguous outcomes
are recorded as unknown without retry. Download metadata is checked around staging.

Overwrites are blocked in both directions, including forged previews. Nonempty
uploads require existing cloud parent folders; empty uploads and missing parent
folders are excluded with preview warnings. Empty downloads are supported.
Reviewed folder creation, empty upload semantics, saved-pair edit/delete UX and
live/packaged acceptance remain open. The reviewed-copy milestone is not complete.
No live account was used; local fakes validate contracts, not provider acceptance.

## Setup checkpoint v0.13.0

`codex/onedrive-account-folder-pairs` starts from documentation checkpoint
`e5678b2` (source tag v0.12.0). The public executable remains v0.11.0.
This branch imports only `core/onedrive_auth.py` from the preserved scaffold
(origin/codex/onedrive-provider at 6d21895), then adapts explicit personal-account
sign-in. It does not import the transfer provider or unfinished SFTP code.

Captured in source checkpoint v0.13.0: a dedicated setup dialog, asynchronous browser sign-in and
read-only folder navigation, paginated Graph folder listings, and saved OneDrive
Folder Pairs in the existing settings collection. Cloud IDs are stored under
`server_endpoint`, never as local filesystem paths. Tokens remain outside settings.
Cloud pairs are listed in setup but cannot activate local comparison/sync. Local
pair management preserves cloud definitions and reserves their names.

The reviewed-copy branch owns the subsequent identity and transfer integration;
its current progress and remaining scope are recorded above.
This setup preview does not implement cloud copying, empty-file uploads, destination
folder creation or safe replacement. Editing/deleting saved cloud pairs and
restoring them in the setup browser also remain follow-up work.

Developer-only prerequisites for future live validation: a Microsoft public-client
registration accepting personal accounts, localhost redirect, and optional msal,
msal-extensions and requests packages. Configure TRACESYNC_ONEDRIVE_CLIENT_ID in a
development environment; consumers must not be asked to register an app. SDK
versions/packaging are not validated or added to release requirements in this
slice. No live OAuth, credential-cache, Graph or packaged test was performed.

Explicit Connect always lets the user select an account; it does not silently
choose the first cached account. MSAL's protected cache adapter is tested with a
fake library; actual Windows DPAPI acceptance remains open. Closing during sign-in
discards setup results but cannot revoke browser sign-in already in progress.
Closing is temporarily disabled while a save finishes; no partial pair is applied.

## Preserved scaffold evidence

Development evidence below belongs to the preserved local `codex/cloud-sftp-resume` workspace based on v0.11.0, not the scoped setup checkpoint.
It preserves SFTP work and imports scaffold files from remote Google Drive
`5f01d88` and OneDrive `6d21895` feature branches. Those histories have not been
merged into master. The remote v0.11.1 tag denotes scaffolding, not a published
portfolio release. Neither cloud provider is wired into the UI.

Google Drive now has offline tests for fresh version/identity checks surrounding
download, size verification, temporary cleanup, duplicate names (including folder
and case collisions across pages), metadata failures and unsupported native files.
Uploads remain disabled. OneDrive is imported scaffolding, not locally runtime-tested.

No endpoint or cloud app registration is available. The user explicitly chose
local tests and scaffolding. Do not initiate OAuth or remote mutations to validate
this checkpoint. Runtime SDK dependencies are intentionally not added to the desktop
release requirements: Google needs google-api-python-client/google-auth-oauthlib
and keyring; OneDrive needs requests/msal/msal-extensions. Resolve and validate
versions in a separate development environment before enabling either adapter.

Outstanding before cloud UI integration: Google Picker and least-privilege scope
review (the imported authentication helper still requests full Drive access),
account-scoped token storage, folder chooser pagination, SDK/auth contract tests,
OneDrive transfer and error-classification tests, and explicit disposable-account
acceptance. Do not wire the broad-scope Google authentication helper into the UI.

## User flow

1. Choose Google Drive or OneDrive for either endpoint and select **Sign in**.
2. TraceSync opens the provider's sign-in and consent page in the system browser.
   The user signs into their account and approves the requested file access.
3. Return to TraceSync and choose the cloud folder. Show the connected account and
   selected folder so the endpoint is clear.
4. Compare that folder with the other selected endpoint. Keep the existing
   results table, direction selection, preview, confirmation, progress, summary,
   and history flow.
5. Initially allow safe create-only copies. Keep existing destination files
   unchanged until provider-specific conditional replacement and remote backup
   behavior have a separate safety design.
6. If authentication expires, request sign-in again through the provider flow.
   Never ask users to paste passwords, client secrets, or access tokens into
   TraceSync.

## Shared design

- Keep each vendor's API calls, pagination, account identity, folder picking,
  token refresh, metadata, and upload behavior in its provider adapter. Do not
  build a generic cloud SDK or flatten vendor APIs into `MainWindow`.
- Share only stable application concepts: account/profile references, endpoint
  selection, secure token storage interface, progress/cancellation reporting,
  and conversion to `StorageLocation`/`ComparisonMetadata`.
- Store refresh tokens in Windows-protected credential storage. Persist only
  non-secret provider/account and selected-folder references in settings. Keep
  tokens and authorization headers out of logs, error strings, and history.
- Use the platform system browser and OAuth authorization-code flow with PKCE.
  A packaged desktop app is a public client; do not ship a client secret.
- Use provider file IDs as native identity. Names and relative paths are for
  display and comparison; do not assume they uniquely identify cloud objects.
- Record only safe endpoint snapshots in history, as with the current provider
  contract.
- Advertise only capabilities that the actual API operation guarantees. Begin
  with create-only transfer; unknown outcomes must not be retried automatically.

## Google Drive branch

Branch: `codex/google-drive-provider`, based on the shared cloud foundation.

- Use Google desktop OAuth in the system browser.
- Investigate Google Picker with the `drive.file` scope first. It is the narrower
  scope and is intended for files the user selects or opens with the app. Verify
  that the selected-folder workflow can enumerate its entire intended subtree.
  If not, pause and assess broader Drive scopes, their consent screen and
  verification requirements before requesting them.
- Use Drive file IDs for `StorageLocation` identity and provider version/ETag,
  modified time, size, and checksum only where the API provides them.
- Detect duplicate names among siblings. Google Drive's API says a file name
  isn't necessarily unique within a folder, while TraceSync comparison currently
  keys records by relative path. Until the comparison model can represent
  ambiguity, fail that folder comparison with a clear explanation instead of
  silently selecting one item.
- Validate upload create semantics carefully. `files.create` creates a Drive
  item, but the API does not make names unique; do not claim path-level atomic
  create-only safety based on a preflight name search.

## Microsoft OneDrive branch

Branch: `codex/onedrive-provider`, based on the shared cloud foundation.

- Use Microsoft Authentication Library (MSAL) with delegated user sign-in in
  the system browser and request the least access needed for the chosen account
  and workflow. Determine personal versus work/school account support before
  finalizing permissions.
- Use Microsoft Graph drive-item IDs and ETags/cTags for stable identity and
  change checks. Use paging and upload sessions for large files.
- Start with Graph create operations configured to fail on name conflicts. Do
  not use a rename or replace conflict policy for reviewed create-only actions.
- Treat asynchronous upload completion and lost responses as potentially
  uncertain; refresh provider state before offering another attempt.

### Current OneDrive branch state

`core/onedrive_auth.py` contains a Microsoft public-client sign-in adapter and
DPAPI-encrypted, file-locked MSAL cache. `core/onedrive_provider.py` contains a Graph
provider scaffold for recursive listing, metadata, downloads, and create-only
upload sessions. It is not connected to settings, provider selection, or the
main-window workflow. The selected folder ID must currently be supplied by a
caller; no user-facing folder picker exists. Matching destination subfolders
must already exist, zero-byte uploads are explicitly unsupported, and overwrite
is blocked.

The current delegated scopes are `User.Read` and `Files.ReadWrite`. Microsoft's
permission reference describes `Files.ReadWrite` as full read/create/update/delete
access to the signed-in user's files. The selected-folder UX therefore still
needs a clear consent explanation and an investigation of narrower options;
Microsoft's selected-file permissions are currently preview/Office-handler
scenarios, not a general Graph folder-picker substitute. See the [Microsoft
Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference).

The branch still needs app-registration and consent validation for personal and
work/school accounts; secure sign-in lifecycle and account/folder selection UI;
settings/provider factory and compare/preview/sync/history integration; tests
for paging, duplicate paths, stale eTags, transfer conflicts, interrupted or
unknown uploads, and token-cache behavior; PyInstaller credential-backend
validation; and live sign-in/transfer checks using a disposable OneDrive account.
Until those are complete, this is development scaffolding rather than a usable
OneDrive release.

## Approved product direction (2026-10-18)

Audience: everyday Windows users managing personal files. Use familiar cloud
accounts, not server protocols. SFTP is removed from the consumer roadmap;
preserve the unfinished implementation and saved profiles without further SFTP
feature work or destructive removal. OneDrive personal accounts come first,
Google Drive second; Dropbox is a later candidate, not a current commitment.

A run is manually started. TraceSync then performs the reviewed actions; this
is not authorization for background scheduling, deletion mirroring or automatic
conflict resolution. Preserve compare -> review -> confirm -> sync.

Developer registration is an application-owner responsibility. Ordinary users
connect through the system browser, choose a folder and save a named Folder Pair.
Never ask them for client secrets, API endpoints, refresh tokens or upload chunks.
Use desktop public-client OAuth and protected account-scoped token caching;
renew silently where possible and request Reconnect only when interaction is
needed. Do not confuse a selected folder in the UI with folder-limited consent.

Green next-step buttons and a pale-green guide apply to setup; warnings and
replacement review remain amber. Show account and folder identity clearly.
Network work must not freeze the UI. Cancellation and errors must leave existing
pairs and endpoints unchanged. Never report an uncertain upload as complete.

## Delivery sequence

1. **OneDrive setup:** connect a personal account, browse folders, choose a local
   folder and save a named Folder Pair with credential-free native IDs. Develop
   and test locally with injected auth/API fakes. Keep cloud execution blocked.
2. **OneDrive usable copy milestone:** restore saved pairs with account matching,
   silent renewal/reconnect, integrate comparison/review/history, support empty
   files and nested destination folders, validate create-only uploads and
   interruption/conflicts. New-folder creation needs an explicit safety contract.
3. **OneDrive safe replacement:** implement provider-specific conditional commit
   and backup/recovery with changed-file tests. Create-only copying is an interim
   milestone, not completion of the user's overwrite requirement. Never inherit
   the local overwrite race exception.
4. **Google Drive:** resolve Picker/whole-folder access and least-privilege scope,
   account-scoped storage, duplicate identities and native-document policy before
   the same end-to-end workflow. Uploads remain blocked pending safe semantics.
5. **Release acceptance:** disposable-account API/OAuth tests, packaged protected
   storage, reconnect/sign-out and manual desktop acceptance. No release claim
   follows from offline tests alone. Consider Dropbox only after these milestones.

API corrections underlying this plan: generic googleapis.com/microsoft.com URLs
are not API endpoints or permission scopes; timestamp checks alone do not protect
reviewed replacements; Microsoft simple upload currently supports 250 MB, not a
universal 4 MB threshold. Keep chunking and provider differences inside services.
Use official provider documentation below when revisiting these decisions.

For each provider, validate least-privilege consent, sign-in and token renewal,
folder permissions, pagination, special/duplicate names, changed or deleted
files, upload interruption, conflict behavior, packaged Windows credentials,
and account sign-out/revocation. Missing app registrations, consent, or a live
test account is an environmental blocker, not a pass.

## External API references

- [Google desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Google Drive scope guidance](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- [Google Picker overview](https://developers.google.com/workspace/drive/picker/guides/overview)
- [Google Drive file resource](https://developers.google.com/workspace/drive/api/reference/rest/v3/files)
- [Microsoft MSAL overview](https://learn.microsoft.com/en-us/entra/identity-platform/msal-overview)
- [Microsoft delegated permissions](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Microsoft Graph upload sessions](https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession?view=graph-rest-1.0)


### Empty uploads and destination folders (development branch)

On `codex/onedrive-create-folders-empty`, based on published source v0.14.0
(`8ffb2d0`), empty uploads use Graph new-file content PUT with the explicit URL
parameter `@microsoft.graph.conflictBehavior=fail`. This is the documented
[driveItem creation conflict behavior](https://learn.microsoft.com/en-us/graph/api/resources/driveitem#instance-attributes),
not the replacing default. Nonempty uploads retain upload sessions.

Missing cloud parents required by selected files are listed in preview warnings
before confirmation and created top-down with conflict failure. Existing parents
must retain their scanned native IDs; parents created by this run are reused only
with the same verified IDs. An external folder appearing after review blocks the
copy. Creation responses must match parent, name and type; unknown outcomes are
never retried. Created directories may remain after a failed/cancelled copy and
are never automatically deleted. Empty standalone directory mirroring is outside
this file-copy workflow. Both copy directions still prohibit replacements.

This slice is checkpointed as source v0.15.0 and tested with fakes only. Live personal-account
and packaged acceptance remain outstanding; the public binary remains v0.11.0.


Post-implementation review reproduced a forged cloud-to-local replacement bypass,
malformed-success misclassification, swallowed upload rejection, and run-owned
folder state/retry gaps. All were corrected with regression tests; final 51 focused
and 233 full tests pass. See ONEDRIVE_CREATE_VALIDATION.md (under docs/ for the root
handoff) for the complete gate report. Explicit authorization is still required
before any commit or integration; HEAD remains v0.15.0 with local changes only.
