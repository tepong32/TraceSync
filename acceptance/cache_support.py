"""Path and process checks for the synthetic Windows cache diagnostic only."""
import ctypes
import os
from pathlib import Path
import tempfile
from uuid import UUID


PREFIX = "TraceSync-cache-acceptance-"
MARKER = "TraceSync synthetic cache acceptance v1"


def checked_root(raw, *, create=False):
    path = Path(raw)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("invalid_directory")
    # Exactly one fresh run directory directly beneath this user's TEMP.
    if not path.name.startswith(PREFIX):
        raise ValueError("invalid_directory")
    suffix = path.name[len(PREFIX):]
    if str(UUID(suffix)) != suffix:
        raise ValueError("invalid_directory")
    if path.parent.resolve() != Path(tempfile.gettempdir()).resolve():
        raise ValueError("invalid_directory")
    for parent in (path, *path.parents):
        if parent.exists() and parent.lstat().st_file_attributes & 0x400:
            raise ValueError("reparse_directory")
    if create:
        path.mkdir(exist_ok=False)
        (path / "acceptance-marker.txt").write_text(MARKER, encoding="ascii")
    else:
        marker = path / "acceptance-marker.txt"
        if not path.is_dir() or not marker.is_file() or marker.lstat().st_file_attributes & 0x400:
            raise ValueError("unowned_directory")
        if marker.read_text(encoding="ascii") != MARKER:
            raise ValueError("unowned_directory")
    return path


def windows_identity():
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    api.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    api.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    api.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
    api.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    api.GetSidSubAuthority.argtypes = [ctypes.c_void_p, w.DWORD]
    api.GetSidSubAuthority.restype = ctypes.POINTER(w.DWORD)

    class SidAttributes(ctypes.Structure):
        _fields_ = [("sid", ctypes.c_void_p), ("attributes", w.DWORD)]

    token = w.HANDLE()
    if not api.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size, elevation = w.DWORD(), w.DWORD()
        if not api.GetTokenInformation(token, 20, ctypes.byref(elevation), ctypes.sizeof(elevation), ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        api.GetTokenInformation(token, 25, None, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not api.GetTokenInformation(token, 25, buffer, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.cast(buffer, ctypes.POINTER(SidAttributes)).contents.sid
        count = api.GetSidSubAuthorityCount(sid).contents.value
        rid = api.GetSidSubAuthority(sid, count - 1).contents.value
        username, length = ctypes.create_unicode_buffer(257), w.DWORD(257)
        if not api.GetUserNameW(username, ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"user": username.value, "pid": os.getpid(), "elevated": bool(elevation.value), "integrity_rid": rid}
    finally:
        kernel.CloseHandle(token)
