@echo off
setlocal EnableDelayedExpansion

REM =========================================================
REM Prepare Release
REM - Clean working tree check
REM - Optional manual version override
REM - Auto bump A.B.C.D with rollover
REM - Generate changelog
REM - Commit version + changelog
REM - Push commits first
REM - Create & push tag
REM - Clear recovery instructions on failure
REM =========================================================

REM ---------------------------------------------------------
REM Ensure clean working tree
REM ---------------------------------------------------------
git diff --quiet || (
    echo ERROR: Working tree is not clean.
    echo Commit or stash changes before preparing a release.
    exit /b 1
)

REM ---------------------------------------------------------
REM Read current version
REM ---------------------------------------------------------
set /p OLD_VERSION=<version.txt
echo Current version: %OLD_VERSION%
echo.

REM ---------------------------------------------------------
REM Prompt for version override
REM ---------------------------------------------------------
set /p INPUT_VERSION=Enter new version (A.B.C.D) or press ENTER to auto-bump: 

REM ---------------------------------------------------------
REM Decide new version
REM ---------------------------------------------------------
if not defined INPUT_VERSION (
    REM ---- AUTO BUMP ----
    for /f "tokens=1-4 delims=." %%a in ("%OLD_VERSION%") do (
        set MAJOR=%%a
        set MINOR=%%b
        set FEATURE=%%c
        set PATCH=%%d
    )

    set /a PATCH+=1

    if !PATCH! GTR 9 (
        set PATCH=0
        set /a FEATURE+=1
    )

    if !FEATURE! GTR 9 (
        set FEATURE=0
        set /a MINOR+=1
    )

    if !MINOR! GTR 9 (
        set MINOR=0
        set /a MAJOR+=1
    )
    

    set NEW_VERSION=!MAJOR!.!MINOR!.!FEATURE!.!PATCH!
    set VERSION_MODE=auto
) else (
    REM ---- MANUAL OVERRIDE ----
    echo %INPUT_VERSION% | findstr /R "^[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+$" >nul || (
        echo ERROR: Invalid version format. Expected A.B.C.D
        exit /b 1
    )

    set NEW_VERSION=%INPUT_VERSION%
    set VERSION_MODE=manual
)

set TAG=v%NEW_VERSION%

echo.
echo New version: %NEW_VERSION% (%VERSION_MODE%)
echo.

REM ---------------------------------------------------------
REM Safety: tag must not already exist
REM ---------------------------------------------------------
git rev-parse %TAG% >nul 2>&1 && (
    echo ERROR: Tag %TAG% already exists.
    exit /b 1
)

REM ---------------------------------------------------------
REM Write version.txt
REM ---------------------------------------------------------
echo %NEW_VERSION% > version.txt

REM ---------------------------------------------------------
REM Determine previous tag (if any)
REM ---------------------------------------------------------
git describe --tags --abbrev=0 > prev_tag.tmp 2>nul
if errorlevel 1 (
    set PREV_TAG=
) else (
    set /p PREV_TAG=<prev_tag.tmp
)
del prev_tag.tmp 2>nul

REM ---------------------------------------------------------
REM Generate changelog
REM ---------------------------------------------------------
echo [%NEW_VERSION%]> changelog.new

if defined PREV_TAG (
    git log %PREV_TAG%..HEAD --pretty=format:"- %%s" | findstr /v /i "export .exe bump version" >> changelog.new
) else (
    git log --pretty=format:"- %%s" | findstr /v /i "export .exe bump version" >> changelog.new
)

REM Blank line separation
echo( >> changelog.new

if exist changelog.txt (
    type changelog.txt >> changelog.new
)

move /Y changelog.new changelog.txt

REM ---------------------------------------------------------
REM Commit release metadata
REM ---------------------------------------------------------
git add version.txt changelog.txt
git commit -m "release: v%NEW_VERSION%"

REM ---------------------------------------------------------
REM Push commits FIRST
REM ---------------------------------------------------------
git push || (
    echo.
    echo Release prepared locally, but commits were NOT pushed.
    echo DO NOT rerun prepare_release.
    echo Fix the issue and run:
    echo   git push
    echo   git tag %TAG%
    echo   git push origin %TAG%
    exit /b 1
)

REM ---------------------------------------------------------
REM Create and push tag
REM ---------------------------------------------------------
git tag %TAG%
git push origin %TAG% || (
    echo.
    echo Release commit pushed, but tag push failed.
    echo Fix the issue and run:
    echo   git push origin %TAG%
    echo   (or: git push --tags)
    exit /b 1
)

echo.
echo Release %TAG% prepared successfully.
endlocal
pause
