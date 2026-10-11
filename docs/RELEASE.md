# Release workflow

Use Python 3.11 and the shared workflow_version_manager entry point through
`scripts/vm_release.py --vm C:/Users/Administrator/Desktop/GH/workflow_version_manager/version_manager.py`.
Append `inspect`, then `preview minor "Release description"`, then
`release minor "Release description" --yes --allow-dirty` after reviewing/staging
only intended files. The adapter leaves historical docs and screenshots intact;
the shared manager performs the actual VERSION/CHANGELOG update, commit and tag.

For v0.11.0, build from the isolated local-only release checkout, with VERSION set
to the previewed 0.11.0 while packaging. Restore its pre-release value before the
manager executes the exact previewed bump. Verify the resulting tag has the same
source and VERSION used for packaging. Build with:

`python -m PyInstaller --noconfirm --clean TraceSync.spec`

Run the full unittest suite and inspect the actual executable with isolated sample
folders, settings and LOCALAPPDATA. Record SHA-256, runtime/tool versions, test
outcomes and manual scope in CONTINUE.md. Integrate with current origin/master,
push master and the release tag, and verify remote commit identity. Publish the
versioned executable and checksum on tepong32.github.io, retain historical builds,
run its site validator and verify the deployed download hash.

SFTP services, credentials and live provider controls are excluded from v0.11.0.
The original development checkout remains untouched. Do not interpret its test
results as real-server or packaged-SFTP acceptance.
