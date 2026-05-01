@echo off
REM ==== Auto-release ====

REM ---------------------------------------------------------
REM Ensure clean working tree
REM ---------------------------------------------------------
git diff --quiet || (
    echo ERROR: Working tree is not clean.
    echo Commit or stash changes before preparing a release.
    exit /b 1
)

REM Get version number from file
setlocal
set /p VERSION=<version.txt

REM Tag name
set TAG=v%VERSION%

REM Executable and version paths
set EXE=dist\SuperADSClient.exe
set VERSION_FILE=version.txt

REM log path
set LOG=changelog.txt

REM Create GitHub release 
gh release create %TAG% %EXE% %VERSION_FILE% %LOG% ^
    --title "Super ADS Client %VERSION%" ^
    --notes "Auto-release for version %VERSION%"

echo Release %TAG% created successfully!
endlocal
pause
