@echo off
:: ============================================================================
:: build_installer.bat — One-click Windows Installer Builder for Agentic
:: ============================================================================
:: This script:
::   1. Generates assets\icon.ico  (multi-size Windows icon)
::   2. Runs PyInstaller to bundle the app into dist\Agentic\
::   3. Runs Inno Setup Compiler (iscc) to produce installer\Agentic-Setup.exe
::
:: Prerequisites:
::   • Python 3.11+  (added to PATH)
::   • pip install -r requirements.txt   (includes pyinstaller)
::   • Inno Setup 6  https://jrsoftware.org/isdl.php  (installed to default path)
::
:: Usage (from the agentic-app\ directory):
::   build_installer.bat
::
:: Output:
::   installer\Agentic-Setup.exe
:: ============================================================================

setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo.
echo ============================================================
echo  Agentic Installer Builder
echo ============================================================
echo.

:: ── Step 1: Check Python ──────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    echo         Install Python 3.11+ from https://python.org and add it to PATH.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo [OK] %%v found

:: ── Step 2: Install / verify dependencies ────────────────────────────────
echo.
echo [1/4] Installing Python dependencies...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed. Check requirements.txt and your internet connection.
    pause & exit /b 1
)
echo [OK] Dependencies installed.

:: ── Step 3: Generate icon.ico ────────────────────────────────────────────
echo.
echo [2/4] Generating icon files...
if not exist "assets\icon.png" (
    python assets\generate_icon.py
)
python assets\generate_icon_ico.py
if errorlevel 1 (
    echo [WARN] Icon generation failed — installer will use a default icon.
)

:: ── Step 4: Run PyInstaller ──────────────────────────────────────────────
echo.
echo [3/4] Building application bundle with PyInstaller...
echo       (This may take several minutes on first run)
python -m PyInstaller agentic.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed. See output above for details.
    pause & exit /b 1
)
if not exist "dist\Agentic\Agentic.exe" (
    echo [ERROR] dist\Agentic\Agentic.exe not found after PyInstaller run.
    pause & exit /b 1
)
echo [OK] PyInstaller bundle created: dist\Agentic\

:: ── Step 5: Run Inno Setup ──────────────────────────────────────────────
echo.
echo [4/4] Compiling Windows installer with Inno Setup...

:: Add common Inno Setup install locations to PATH for this script session.
set "PATH=%PATH%;C:\Program Files (x86)\Inno Setup 6;C:\Program Files\Inno Setup 6"

:: Detect compiler from PATH.
where iscc >nul 2>&1
if not errorlevel 1 goto :compile_installer

echo [WARN] Inno Setup Compiler (iscc.exe) not found.
echo       Attempting automatic install via winget...

where winget >nul 2>&1
if errorlevel 1 goto :no_winget

winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :install_failed

echo [OK] Inno Setup installed.
goto :retry_iscc

:no_winget
echo [WARN] winget is not available on this system.
goto :retry_iscc

:install_failed
echo [WARN] Automatic Inno Setup install failed.

:retry_iscc
set "PATH=%PATH%;C:\Program Files (x86)\Inno Setup 6;C:\Program Files\Inno Setup 6"
where iscc >nul 2>&1
if errorlevel 1 goto :no_iscc

:compile_installer
if not exist "installer" mkdir "installer"
iscc setup.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup compilation failed. See output above.
    pause & exit /b 1
)
goto :done

:no_iscc
echo.
echo [WARN] Inno Setup Compiler is still unavailable.
echo        Install manually from: https://jrsoftware.org/isdl.php
echo.
echo        The PyInstaller bundle is ready at: dist\Agentic\
echo        You can run dist\Agentic\Agentic.exe directly without an installer.

:done
:: ── Done ─────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo  BUILD COMPLETE
echo ============================================================
echo.
if exist "installer\Agentic-Setup.exe" (
    echo  Installer : installer\Agentic-Setup.exe
    echo  Portable  : dist\Agentic\Agentic.exe
    echo.
    echo  Distribute "installer\Agentic-Setup.exe" to users.
    echo  Double-clicking it starts the installation wizard.
) else (
    echo  Installer : not generated (Inno Setup unavailable)
    echo  Portable  : dist\Agentic\Agentic.exe
    echo.
    echo  Run this script again after Inno Setup is available.
)
echo.
pause
endlocal
