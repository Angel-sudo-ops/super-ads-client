@echo off
REM ==== Auto-release ====
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
