"""Google setup uses the existing asynchronous Folder Pair presentation."""
from ui.dialogs.onedrive_setup_dialog import OneDriveSetupDialog
from core.google_drive_setup_service import GoogleDriveSetupService


class GoogleDriveSetupDialog(OneDriveSetupDialog):
    def __init__(self, parent, service=None):
        super().__init__(parent, service=service or GoogleDriveSetupService(), provider_name="Google Drive",
            scope_notice="Google permission allows reading all Drive files; this pair chooses what TraceSync reads. "
                         "Reviewed downloads only. Uploads and existing-file replacements are disabled.")
