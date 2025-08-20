@echo off
REM ==== Auto-release Super ADS Client ====
REM Get version number from file
setlocal
set /p VERSION=<version.txt

REM Tag name
set TAG=v%VERSION%

REM Executable and version paths
set EXE=dist\SuperADSClient.exe
set VERSION_FILE=version.txt

REM Create GitHub release and upload both files
gh release create %TAG% %EXE% %VERSION_FILE% --title "Super ADS Client %VERSION%" --notes "Auto-release for version %VERSION%"

echo Release %TAG% created successfully!
endlocal
pause
