@echo off
setlocal
set "TRACESYNC_ONEDRIVE_CLIENT_ID="
set "TRACESYNC_ONEDRIVE_TENANT="
set "TRACESYNC_DIAGNOSTIC_EXE=%~dp0TraceSync-Cache-Acceptance.exe"
set "TRACESYNC_DIAGNOSTIC_HASHFILE=%~dp0SHA256.txt"
powershell -NoProfile -Command "$expected=(Get-Content -LiteralPath $env:TRACESYNC_DIAGNOSTIC_HASHFILE).Split(' ')[0]; if((Get-FileHash -LiteralPath $env:TRACESYNC_DIAGNOSTIC_EXE -Algorithm SHA256).Hash -ne $expected){exit 1}"
if errorlevel 1 goto failed
for /f %%I in ('powershell -NoProfile -Command "[guid]::NewGuid().ToString()"') do set "TRACESYNC_RUN_ID=%%I"
if not defined TRACESYNC_RUN_ID goto failed
set "TRACESYNC_RUN_ROOT=%TEMP%\TraceSync-cache-acceptance-%TRACESYNC_RUN_ID%"
set "LOCALAPPDATA=%TRACESYNC_RUN_ROOT%\unused-profile"
if not exist "%~dp0Results" mkdir "%~dp0Results"
set "TRACESYNC_RESULT=%~dp0Results\%TRACESYNC_RUN_ID%.jsonl"
if exist "%TRACESYNC_RESULT%" goto failed
echo Running synthetic cache checks. No account or browser is used.
for %%C in (write read plaintext unencrypted persistence encryption decryption offline) do (
    "%TRACESYNC_DIAGNOSTIC_EXE%" --cache-acceptance --directory "%TRACESYNC_RUN_ROOT%" --case %%C >> "%TRACESYNC_RESULT%" 2>&1
    if errorlevel 1 goto failed
)
echo All diagnostic processes completed. Results are saved in the Results folder.
pause
exit /b 0
:failed
echo Diagnostic stopped. No acceptance pass is claimed. Ask Codex to inspect the Results folder.
pause
exit /b 1
