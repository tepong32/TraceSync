# Cloud storage provider plan

## Status

The shared provider boundary is in place. Google Drive has an experimental,
read-only integration on `codex/google-drive-provider` that supports sign-in,
folder selection, comparison, review, and downloads to local storage. It has not
passed live account validation and is not part of a release. OneDrive remains a
separate planned branch. The intended workflow uses each provider's native API
behind `StorageProvider` and preserves TraceSync's compare, review, confirm,
sync, summary, and history flow.

## User flow

1. On a provider-enabled development build, choose Google Drive or OneDrive for
   an endpoint and select **Sign in**. Currently only Google Drive is wired, and
   only as a source for local downloads.
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

Current implementation status: the app has a tested desktop Picker OAuth flow,
Windows credential-store integration, saved non-secret folder references, and
UI wiring to compare a selected Drive folder with a local folder and download
reviewed files to local storage. Uploads to Drive are unavailable because Drive
does not provide the required path-level atomic absence guarantee. The scan
adapter follows pagination across My Drive/shared-drive results, rejects
duplicate sibling names and case-insensitive Windows collisions, rejects
Windows-invalid names and unsupported Workspace documents/shortcuts, checks
`canListChildren` to avoid incomplete scans, and fetches fresh source metadata
around downloads. The Windows Keyring backend is bundled in PyInstaller and a
frozen set/read/delete credential probe passed. This is not yet a validated
release: live consent, `drive.file` subtree access, app OAuth, and real transfers
still need a disposable-account check.

- Use Google desktop OAuth in the system browser.
- Use the desktop/mobile Google Picker OAuth trigger with `drive.file` and
  folder selection. Do not ship or require a confidential client secret in a
  desktop executable; desktop OAuth clients are public clients and Google
  supports PKCE.
- The selected folder ID and account are endpoint references, not credentials.
  Store tokens in Windows credential storage and endpoint references in
  TraceSync settings.
- Verify that the selected-folder workflow can enumerate its entire intended
  subtree using `drive.file`. If not, assess broader Drive scopes and their
  consent-screen and verification requirements before requesting them.
- For development, configure a Desktop OAuth client, enable both the Drive API
  and Google Picker API, declare `drive.file`, and add the test account to the
  consent screen's test-user list. Google expires Testing-mode authorizations
  after seven days, including offline refresh tokens, so that mode is only for
  integration checks. Before distributing to general users, configure a
  production OAuth consent screen and complete Google's applicable branding/
  verification steps. `drive.file` is a non-sensitive, per-file scope, but
  public distribution still requires the applicable basic OAuth app verification.
  Use a separate Google Cloud project for production.
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

## Delivery sequence

1. **Foundation branch:** document the contract, then define minimal account and
   endpoint settings, secure token-store boundary, cloud sign-in lifecycle, and
   provider factory integration points. Keep local behavior unchanged.
2. **Google Drive branch:** validate account sign-in, Picker/folder selection,
   read-only scan and downloads with a disposable account; resolve `drive.file`
   subtree access. Keep uploads unavailable unless the API can meet the safety
   contract.
3. **OneDrive branch:** implement the same user flow with MSAL and Graph; scan,
   download, then create-only upload sessions with explicit conflict failure.
4. **Integration:** merge providers separately, expose only validated choices,
   update settings/history/build packaging and help text, and retain the same
   review and confirmation steps.

For each provider, validate least-privilege consent, sign-in and token renewal,
folder permissions, pagination, special/duplicate names, changed or deleted
files, upload interruption, conflict behavior, packaged Windows credentials,
and account sign-out/revocation. Missing app registrations, consent, or a live
test account is an environmental blocker, not a pass.

## External API references

- [Google desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Google OAuth testing and verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification)
- [Google OAuth publishing status and test-user limits](https://support.google.com/cloud/answer/15549945?hl=en)
- [Google Drive scope guidance](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- [Google Picker overview](https://developers.google.com/workspace/drive/picker/guides/overview)
- [Google Drive file resource](https://developers.google.com/workspace/drive/api/reference/rest/v3/files)
- [Microsoft MSAL overview](https://learn.microsoft.com/en-us/entra/identity-platform/msal-overview)
- [Microsoft delegated permissions](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Microsoft Graph upload sessions](https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession?view=graph-rest-1.0)
