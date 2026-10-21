# Application-owner inputs and acceptance

Updated 2026-10-21. This is a preparation checklist, not a statement that cloud
engineering is finished. See PROVIDER_COMPLETION.md for the remaining code gates.
These registrations belong to the TraceSync owner, not to ordinary app users.

## What can be provided

| Provider | Non-secret owner input | Where it comes from | How to provide it |
| --- | --- | --- | --- |
| OneDrive personal | Application (client) ID, a UUID; confirmation that personal accounts and desktop localhost redirect are enabled | Microsoft Entra admin center → Entra ID → App registrations → TraceSync | Paste only the public client ID in chat, or put `onedrive_client_id` and `onedrive_tenant: consumers` in the ignored root `provider_config.json` of the OneDrive completion worktree |
| Google Drive | Desktop OAuth client ID ending `.apps.googleusercontent.com`; confirmation of enabled Drive API, consent audience/test users and declared scopes | Google Cloud console → Google Auth Platform → Clients; APIs & Services → Library | Paste only the public client ID in chat, or put `google_drive_client_id` in the ignored root `provider_config.json` of the Google completion worktree after configuration integration |
| Live acceptance | Confirmation that a disposable personal account and nonvaluable test folder are ready | Your browser/account, with synthetic test files | Tell the agent the provider and that the test folder is disposable. Sign in yourself through TraceSync's system-browser flow when requested |

Do not send passwords, access tokens, refresh tokens, private keys, browser profiles,
token caches or client secrets. Do not paste the complete downloaded OAuth JSON.
No real account data is required to finish offline development. Dummy client IDs
are used only in tests; they cannot produce usable sign-in.

## OneDrive registration

1. Sign in to https://entra.microsoft.com/ with an identity allowed to register
   applications. An Entra directory/application-developer role may be required;
   an ordinary personal OneDrive account alone need not have that portal access.
2. Open Entra ID → App registrations → New registration. Name it TraceSync.
   Choose **Personal Microsoft accounts only** for this personal-account milestone.
3. In Authentication, add a **Mobile and desktop applications** platform with
   `http://localhost` redirect. MSAL's interactive desktop method handles PKCE.
4. Under API permissions, use Microsoft Graph **delegated** `User.Read` and
   `Files.ReadWrite`. Do not add application permissions or create a secret.
5. Copy the Application (client) ID from Overview. The app uses the `consumers`
   authority. A user-selected folder is an app workflow boundary, not a claim that
   Microsoft consent grants access to only that folder.

Source development reads the ignored root file or explicit developer environment
overrides. For a future owner-operated OneDrive build, set only in the build shell:

```powershell
$env:TRACESYNC_BUILD_PROVIDERS = 'onedrive'
$env:TRACESYNC_ONEDRIVE_CLIENT_ID = '<public application UUID>'
$env:TRACESYNC_ONEDRIVE_TENANT = 'consumers'
```

The spec emits an allowlisted public `provider_config.json` into the external build
work directory and bundles it. End users do not need these environment variables.
Cloud build selection rejects missing/invalid IDs; a local-only build is separate.
The command above does not build or authorize a release.

## Google registration and consent

1. Open https://console.cloud.google.com/, select/create a project owned by you,
   and enable **Google Drive API** in APIs & Services → Library.
2. Configure Google Auth Platform Branding, Audience and Data Access. For an
   external testing app, add the disposable Google account as a test user.
3. Create an OAuth client with application type **Desktop app** and copy only its
   public Client ID. Do not create a web/server confidential-client integration.
4. The Google completion branch uses standard desktop loopback PKCE sign-in and an
   in-app folder chooser. It does not rely on undocumented OAuth Picker parameters.
   Whole-folder downloading requests `https://www.googleapis.com/auth/drive.readonly`.
   This reads all Drive files at the permission level; TraceSync's selected pair
   limits its workflow. It is a restricted scope and requires applicable Google
   verification before public distribution. Testing consent is not production
   approval. No Picker API key is needed for this native folder browser.
5. Google upload/replacement semantics and any necessary write scope are still
   engineering gates. Do not grant full write access just to make tests pass or
   represent a read/download connector as completed two-way cloud synchronization.

## After public IDs are supplied

First verify source-mode connect, wrong-account refusal, folder selection,
save/edit/delete/reopen, renewal, disconnect, read-only comparison, approved
transfer, empty/nested files, conflict and permission/unknown-outcome behavior
against disposable accounts. Tests must check actual remote bytes and existing
files remain protected. Then build in the approved isolated toolchain and repeat
the relevant non-elevated packaged checks with protected credential persistence.
Earlier Gate A/B artifacts prove their documented historical scope only.

No public IDs, mocks or import tests can substitute for these live/package gates.
Safe OneDrive replacement and Google upload/replacement design must also be
completed and validated before claiming the original full synchronization goal.

Official references checked 2026-10-21:

- https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app
- https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
- https://learn.microsoft.com/en-us/graph/permissions-reference
- https://developers.google.com/identity/protocols/oauth2/native-app
- https://developers.google.com/workspace/drive/api/guides/api-specific-auth

## Exact source configuration locations

- OneDrive completion: `C:/Users/Administrator/.codex/worktrees/tracesync-onedrive-completion/provider_config.json`.
- Google completion: `C:/Users/Administrator/.codex/worktrees/tracesync-google-drive-completion/provider_config.json`.

These root files are ignored development configuration, not credential caches.
UTF-8 with or without a BOM is accepted. You can instead paste only the two public
client IDs in this chat and let the agent configure them locally. The owner must
still confirm that the corresponding portal/consent settings are ready.

A future combined build uses the Google completion branch's shared configuration:

```powershell
$env:TRACESYNC_BUILD_PROVIDERS = 'onedrive,google_drive'
$env:TRACESYNC_ONEDRIVE_CLIENT_ID = '<public Microsoft application UUID>'
$env:TRACESYNC_ONEDRIVE_TENANT = 'consumers'
$env:TRACESYNC_GOOGLE_CLIENT_ID = '<public Google Desktop OAuth client ID>'
```

The OneDrive-only branch intentionally rejects selecting Google for packaging.
These commands set public build metadata only; they do not authorize a build,
real-account access, uploads, release or publication. Do not distribute a build
with dummy IDs as a working cloud application. Live source checks and packaged
acceptance still follow, and engineering gates above remain visible.
