# TraceSync continuation

Active branch: codex/onedrive-create-safety-audit.
Worktree: C:/Users/Administrator/.codex/worktrees/tracesync-onedrive-create-safety.
HEAD: 0de6aa23987a5661b0578ea40b83f5082abedb32,
parent 4ddfd55e2874fecb76e6cf1e054fc971b03bbb41.
Subject: fix: harden OneDrive create-only safety checks.
This is a local source-only checkpoint; no merge, push, tag or executable publication.

Read AGENTS.md, docs/CLOUD_STORAGE.md, docs/ROADMAP.md, docs/BRANCH_WORKFLOW.md,
docs/ONEDRIVE_CREATE_VALIDATION.md and docs/ONEDRIVE_ENVIRONMENT.md before changes.
The validation report records the historical safety review and corrected invariants;
the environment document owns current dependency setup and build-tool blockers.

Current uncommitted work: add exactly msal==1.39.0, msal-extensions==1.3.1 and
requests==2.34.2 to requirements.txt and reconcile installation/checkpoint docs.
No provider/auth/cache/transfer/preview/synchronization code or tests changed.
Transitive dependencies are already declared by these distributions; no duplicate
transitive pins or unrelated upgrades. No PyInstaller spec change.

PASS: declared requirements installed in the external isolated environment
C:/xxx/_INSTALLS/_HERE/_xxx/TraceSync-acceptance-0de6aa2-20261018/venv;
pip check, focused 51 tests, full 233 tests, compilation and diff checks.
See ONEDRIVE_ENVIRONMENT.md for exact commands and external evidence filenames.
Dependencies were already satisfied from prior candidate preparation. Established
project environment remains unchanged, with the three cloud packages absent.
Existing Tk teardown diagnostics persist; unittest reports OK.

Material findings: existing PyInstaller 6.20.0 falls in a privileged-onefile advisory
range; isolated bootstrap setuptools 65.5.0 has a PackageIndex advisory. pip 23.2.1
is inherited old tooling. Preserve current pins in this narrow integration, but
hold build-tool approval pending targeted patched-tool/bootstrap review.

NOT RUN - ENVIRONMENTAL: live personal-account and actual Windows protected-cache
acceptance; no test account/registration was configured or used.
NOT RUN - OUT OF SCOPE: executable build/packaged acceptance, publication or new
PyInstaller analysis. Source tests are not packaged acceptance. Public binary
remains v0.11.0. TOCTOU and post-crash folder-accounting limits are unchanged.

Next: review/checkpoint dependency/docs edits only after separate authorization;
then resolve targeted build-tool security and authorize isolated live acceptance
separately. No sign-in, real-cache access, cloud mutations or account changes occurred.
Keep both cloud directions create-only, review-confirmation mandatory and unknown
outcomes non-retrying.

Preserved: dirty codex/onedrive-pair-management worktree at
C:/Users/Administrator/.codex/worktrees/tracesync-onedrive-reviewed-copy and the
canonical historical SFTP workspace/stash/backup. Do not merge unfinished history.
