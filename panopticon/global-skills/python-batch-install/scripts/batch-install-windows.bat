@echo off
setlocal EnableExtensions EnableDelayedExpansion

for %%I in ("%~dp0") do set "SCRIPT_DIR=%%~fI"
set "DEFAULT_MANIFEST=%SCRIPT_DIR%..\assets\environment-manifest.template.yaml"
if not defined MANIFEST_FILE set "MANIFEST_FILE=%DEFAULT_MANIFEST%"
if not defined MANIFEST_PYTHON set "MANIFEST_PYTHON=py -3.11"
set "MANIFEST_HELPER=%SCRIPT_DIR%render_windows_manifest_env.py"
set "MANIFEST_ENV_FILE=%TEMP%\openclaw-manifest-%RANDOM%-%RANDOM%.cmd"
if not defined DRY_RUN set "DRY_RUN=0"

if not exist "%MANIFEST_FILE%" (
    echo [ERROR] Manifest file not found: %MANIFEST_FILE%
    exit /b 1
)

if not exist "%MANIFEST_HELPER%" (
    echo [ERROR] Manifest helper not found: %MANIFEST_HELPER%
    exit /b 1
)

call :render_manifest
if errorlevel 1 exit /b 1
call "%MANIFEST_ENV_FILE%"
del /q "%MANIFEST_ENV_FILE%" >nul 2>&1

if not defined WORKSPACE_DIR set "WORKSPACE_DIR=%MANIFEST_WORKSPACE_DIR%"
if not defined PACKAGE_DIR set "PACKAGE_DIR=%MANIFEST_WINDOWS_PACKAGE_DIR%"
if not defined REQ_FILE set "REQ_FILE=%MANIFEST_WINDOWS_REQUIREMENTS%"
if not defined VENV_ROOT set "VENV_ROOT=%MANIFEST_WINDOWS_VENV_ROOT%"
if not defined BASE_PYTHON set "BASE_PYTHON=%MANIFEST_WINDOWS_BASE_PYTHON%"
if not defined PLAYWRIGHT_ZIP set "PLAYWRIGHT_ZIP=%PACKAGE_DIR%\ms-playwright.zip"
if not defined PLAYWRIGHT_DEST set "PLAYWRIGHT_DEST=%LOCALAPPDATA%"
if not defined SEVEN_ZIP set "SEVEN_ZIP=C:\Program Files\7-Zip\7z.exe"
if not defined ENV_NAMES set "ENV_NAMES=%MANIFEST_ENV_NAMES%"
if not defined VERIFY_PIP_SHOW set "VERIFY_PIP_SHOW=%MANIFEST_VERIFY_PIP_SHOW%"
if not defined VERIFY_SNIPPETS set "VERIFY_SNIPPETS=%MANIFEST_VERIFY_SNIPPETS%"

rem Override examples:
rem   set "MANIFEST_FILE=C:\work\environment-manifest.yaml"
rem   set "ENV_NAMES=package3.11 package3.11-test"
rem   set "VENV_ROOT=D:\venvs"
rem   set "BASE_PYTHON=C:\Python311\python.exe"

if not exist "%REQ_FILE%" (
    echo [ERROR] Requirements file not found: %REQ_FILE%
    exit /b 1
)

if not exist "%PACKAGE_DIR%" (
    echo [ERROR] Package directory not found: %PACKAGE_DIR%
    exit /b 1
)

if "%DRY_RUN%"=="1" (
    call :print_plan
    exit /b 0
)

if not exist "%VENV_ROOT%" mkdir "%VENV_ROOT%"

set "SUCCESS_ENVS="
set "FAILED_ENVS="

for %%E in (%ENV_NAMES%) do (
    call :install_one %%E
)

echo.
echo Batch install summary
echo Manifest: %MANIFEST_FILE%
echo Workspace: %WORKSPACE_DIR%
echo Wheel dir: %PACKAGE_DIR%
echo Requirements: %REQ_FILE%
echo Venv root: %VENV_ROOT%
echo Successful environments:%SUCCESS_ENVS%
echo Failed environments:%FAILED_ENVS%

if defined FAILED_ENVS exit /b 1
exit /b 0

:print_plan
echo.
echo Dry-run plan
echo Manifest: %MANIFEST_FILE%
echo Workspace: %WORKSPACE_DIR%
echo Base Python: %BASE_PYTHON%
echo Wheel dir: %PACKAGE_DIR%
echo Requirements: %REQ_FILE%
echo Venv root: %VENV_ROOT%
echo Pip show checks: %VERIFY_PIP_SHOW%
for %%E in (%ENV_NAMES%) do (
    call :resolve_verify_imports %%E
    echo.
    echo Planned environment: %%E
    echo   venv: %VENV_ROOT%\%%E
    if defined VERIFY_IMPORTS (
        echo   imports: !VERIFY_IMPORTS!
    ) else (
        echo   imports: ^<none^>
    )
)
if defined MANIFEST_SNIPPET_COUNT (
    echo.
    echo Python snippet checks
    for /L %%N in (0,1,%MANIFEST_SNIPPET_COUNT%) do (
        call set "CURRENT_SNIPPET=%%MANIFEST_SNIPPET_%%N%%"
        echo   !CURRENT_SNIPPET!
    )
)
exit /b 0

:install_one
set "ENV_NAME=%~1"
set "ENV_DIR=%VENV_ROOT%\%~1"
set "PYTHON_EXE=%ENV_DIR%\Scripts\python.exe"
call :resolve_verify_imports "%ENV_NAME%"

echo [INFO] Preparing venv: %ENV_DIR%
if exist "%ENV_DIR%" rmdir /s /q "%ENV_DIR%"

call %BASE_PYTHON% -m venv "%ENV_DIR%"
if errorlevel 1 (
    set "FAILED_ENVS=%FAILED_ENVS% %ENV_NAME%:venv-create-failed"
    echo [WARN] Failed to create venv for %ENV_NAME%
    exit /b 1
)

echo [INFO] Installing requirements into: %ENV_NAME%
set "ORIGINAL_PATH=%PATH%"
set "PATH=%ENV_DIR%\Scripts;%ORIGINAL_PATH%"

rem The upstream autoinstall-win.bat is interactive and uses relative paths.
rem This wrapper performs the same steps directly inside the target venv.
call "%PYTHON_EXE%" -m pip install --no-index --find-links "%PACKAGE_DIR%" -r "%REQ_FILE%"
if errorlevel 1 (
    set "PATH=%ORIGINAL_PATH%"
    set "FAILED_ENVS=%FAILED_ENVS% %ENV_NAME%:offline-install-failed"
    echo [WARN] Offline install failed for %ENV_NAME%
    exit /b 1
)

if exist "%PLAYWRIGHT_ZIP%" (
    if exist "%SEVEN_ZIP%" (
        echo [INFO] Extracting Playwright archive for: %ENV_NAME%
        "%SEVEN_ZIP%" x "%PLAYWRIGHT_ZIP%" -o"%PLAYWRIGHT_DEST%" -y >nul
        if errorlevel 1 (
            set "PATH=%ORIGINAL_PATH%"
            set "FAILED_ENVS=%FAILED_ENVS% %ENV_NAME%:playwright-extract-failed"
            echo [WARN] Playwright extraction failed for %ENV_NAME%
            exit /b 1
        )
    ) else (
        echo [WARN] 7-Zip not found, skipping Playwright extraction for %ENV_NAME%
    )
) else (
    echo [WARN] Playwright archive not found, skipping extraction for %ENV_NAME%
)

echo [INFO] Verifying key packages in: %ENV_NAME%
if defined VERIFY_PIP_SHOW (
    call "%PYTHON_EXE%" -m pip show %VERIFY_PIP_SHOW% >nul 2>&1
    if errorlevel 1 (
        set "PATH=%ORIGINAL_PATH%"
        set "FAILED_ENVS=%FAILED_ENVS% %ENV_NAME%:pip-show-failed"
        echo [WARN] pip show verification failed for %ENV_NAME%
        exit /b 1
    )
)

if defined VERIFY_IMPORTS (
    for %%I in (%VERIFY_IMPORTS%) do (
        call "%PYTHON_EXE%" -c "import %%I" >nul 2>&1
        if errorlevel 1 (
            set "PATH=%ORIGINAL_PATH%"
            set "FAILED_ENVS=%FAILED_ENVS% %ENV_NAME%:module-import-failed:%%I"
            echo [WARN] Module import verification failed for %ENV_NAME%: %%I
            exit /b 1
        )
    )
)

if defined MANIFEST_SNIPPET_COUNT (
    for /L %%N in (0,1,%MANIFEST_SNIPPET_COUNT%) do (
        call set "CURRENT_SNIPPET=%%MANIFEST_SNIPPET_%%N%%"
        call "%PYTHON_EXE%" -c "!CURRENT_SNIPPET!"
        if errorlevel 1 (
            set "PATH=%ORIGINAL_PATH%"
            set "FAILED_ENVS=%FAILED_ENVS% %ENV_NAME%:python-snippet-failed"
            echo [WARN] Python snippet verification failed for %ENV_NAME%
            exit /b 1
        )
    )
)

set "PATH=%ORIGINAL_PATH%"
set "SUCCESS_ENVS=%SUCCESS_ENVS% %ENV_NAME%"
exit /b 0

:resolve_verify_imports
set "VERIFY_IMPORTS="
for /L %%N in (0,1,%MANIFEST_ENV_COUNT%) do (
    call set "CURRENT_ENV_NAME=%%MANIFEST_ENV_%%N_NAME%%"
    if /I "%~1"=="!CURRENT_ENV_NAME!" (
        call set "VERIFY_IMPORTS=%%MANIFEST_ENV_%%N_VERIFY_IMPORTS%%"
    )
)
exit /b 0

:render_manifest
call %MANIFEST_PYTHON% "%MANIFEST_HELPER%" "%MANIFEST_FILE%" > "%MANIFEST_ENV_FILE%"
if errorlevel 1 (
    echo [ERROR] Failed to parse manifest: %MANIFEST_FILE%
    exit /b 1
)
exit /b 0