"""Synthetic, offline diagnostic. Never instantiate authentication or inspect a default cache."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import logging
from pathlib import Path
import sys

from acceptance.cache_support import checked_root, windows_identity


CASES = ("write", "read", "plaintext", "unencrypted", "persistence", "encryption", "decryption", "offline")
SYNTHETIC_MARKER = "TRACESYNC-SYNTHETIC-NOT-A-TOKEN-53d2c01f"


class OfflineViolation(RuntimeError):
    pass


def offline_audit(event, args):
    if event.startswith("socket.") or event in ("subprocess.Popen", "os.system", "os.startfile", "os.startfile/2", "webbrowser.open"):
        raise OfflineViolation("offline_only")


def forbidden_auth(*args, **kwargs):
    raise OfflineViolation("authentication_forbidden")


def forbidden_plaintext(*args, **kwargs):
    raise AssertionError("plaintext_persistence_forbidden")


@contextmanager
def replaced(target, name, value):
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, original)


def require(condition):
    if not condition:
        raise AssertionError("diagnostic_assertion")


def account():
    return {"home_account_id": "synthetic.home", "environment": "synthetic.invalid",
            "realm": "synthetic", "username": SYNTHETIC_MARKER,
            "local_account_id": "synthetic", "authority_type": "MSSTS"}


def store(path):
    from core.onedrive_auth import OneDriveTokenStore
    return OneDriveTokenStore(path).create_cache()


def write_entry(cache):
    cache.modify(cache.CredentialType.ACCOUNT, account(), account())


def checked_case_directory(root, case, *, create):
    # No arbitrary cache filenames, adoption of old cases, junctions or symlinks.
    directory = root / case
    if create:
        directory.mkdir(exist_ok=False)
    require(directory.is_dir() and not directory.lstat().st_file_attributes & 0x400)
    for path in directory.iterdir():
        require(not path.lstat().st_file_attributes & 0x400)
        require(path.name in ("cache.bin", "cache.bin.lockfile", "blocked"))
    return directory


def run_case(root, case):
    import msal_extensions as extension
    from msal_extensions.persistence import (FilePersistenceWithDataProtection,
                                            PersistenceEncryptionError, PersistenceDecryptionError)
    from msal_extensions.windows import WindowsDataProtectionAgent
    from core.onedrive_auth import OneDriveConfigurationError

    if case in ("read", "plaintext"):
        directory = checked_case_directory(root, "write", create=False)
    else:
        directory = checked_case_directory(root, case, create=True)
    path = directory / "cache.bin"
    if case in ("write", "read"):
        cache = store(path)
        require(type(cache) is extension.PersistedTokenCache and cache.is_encrypted)
        require(type(cache._persistence) is FilePersistenceWithDataProtection)
        if case == "write":
            write_entry(cache)
            require(path.is_file())
        else:
            require(path.is_file())
            require(list(cache.search(cache.CredentialType.ACCOUNT)) == [account()])
        return "windows_dpapi_and_locked_cache"
    if case == "plaintext":
        content = path.read_bytes()
        for encoding in ("utf-8", "utf-16-le", "utf-16-be", "utf-16"):
            require(SYNTHETIC_MARKER.encode(encoding) not in content)
        return "synthetic_plaintext_absent"
    if case == "unencrypted":
        class Unencrypted:
            is_encrypted = False
        def forbidden_constructor(*args, **kwargs):
            raise AssertionError("unencrypted_cache_constructed")
        with replaced(extension, "build_encrypted_persistence", lambda location: Unencrypted()), replaced(extension, "PersistedTokenCache", forbidden_constructor):
            try:
                store(path)
            except OneDriveConfigurationError:
                require(not list(directory.iterdir()))
                return "injected_unencrypted_backend_rejected"
        raise AssertionError("unencrypted_backend_accepted")
    if case == "persistence":
        blocked = directory / "blocked"
        blocked.write_bytes(b"synthetic path obstruction")
        try:
            store(blocked / "cache.bin")
        except OSError:
            require(list(directory.iterdir()) == [blocked])
            return "invalid_destination_rejected"
        raise AssertionError("persistence_failure_not_reported")
    if case == "encryption":
        def fail_protect(*args, **kwargs):
            raise OSError("synthetic encryption failure")
        cache = store(path)
        with replaced(WindowsDataProtectionAgent, "protect", fail_protect):
            try:
                write_entry(cache)
            except PersistenceEncryptionError:
                require(not path.exists())
                require(not list(directory.iterdir()))
                return "injected_encryption_failure_no_fallback"
        raise AssertionError("encryption_failure_not_reported")
    if case == "decryption":
        cache = store(path)
        write_entry(cache)
        path.write_bytes(b"synthetic corrupt encrypted cache")
        try:
            list(store(path).search(cache.CredentialType.ACCOUNT))
        except PersistenceDecryptionError:
            require(path.read_bytes() == b"synthetic corrupt encrypted cache")
            require(list(directory.iterdir()) == [path])
            return "corrupt_synthetic_cache_no_fallback"
        raise AssertionError("decryption_failure_not_reported")
    if case == "offline":
        import socket
        import msal
        import webbrowser
        for action in (lambda: socket.socket(), lambda: msal.PublicClientApplication("synthetic"),
                       lambda: webbrowser.open("https://synthetic.invalid")):
            try:
                action()
            except OfflineViolation:
                continue
            raise AssertionError("offline_guard_failed")
        require(not list(directory.iterdir()))
        return "network_browser_auth_guards_verified"
    raise ValueError("invalid_case")


def parse_args(argv):
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument("--cache-acceptance", action="store_true", required=True)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--case", choices=CASES, required=True)
    return parser.parse_args(argv)


def main(argv=None):
    result = {"status": "FAIL", "case": "invocation"}
    try:
        # argparse's own diagnostics can expose raw arguments. Suppress them too.
        from contextlib import redirect_stderr
        import io
        with redirect_stderr(io.StringIO()):
            args = parse_args(sys.argv[1:] if argv is None else argv)
        result["case"] = args.case
        identity = windows_identity()
        result.update(identity)
        if identity["elevated"] or identity["integrity_rid"] != 8192:
            raise ValueError("medium_integrity_required")
        root = checked_root(args.directory, create=args.case == "write")
        result["run_id"] = root.name
        logging.disable(logging.CRITICAL)
        sys.addaudithook(offline_audit)
        import msal
        from msal_extensions.persistence import FilePersistence
        with replaced(msal, "PublicClientApplication", forbidden_auth), replaced(FilePersistence, "save", forbidden_plaintext):
            result["evidence"] = run_case(root, args.case)
        result["artifact_sha256"] = hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
        result["status"] = "PASS"
    except (Exception, SystemExit) as error:
        # Never print raw exception strings, cache content, argv or a traceback.
        result["error"] = "invalid_invocation" if isinstance(error, (ValueError, SystemExit, argparse.ArgumentError)) else "diagnostic_failed"
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["status"] == "PASS" else 1
