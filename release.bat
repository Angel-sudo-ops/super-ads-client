@echo off
REM ==== Auto-release Super ADS Client ====
REM Get version number from file
setlocal
set /p VERSION=<version.txt

REM Tag name
set TAG=v%VERSION%

REM Executable path
set EXE=dist\SuperADSClient.exe

REM Create GitHub release
gh release create %TAG% %EXE% --title "Super ADS Client %VERSION%" --notes "Auto-release for version %VERSION%"

echo Release %TAG% created successfully!
endlocal
pause
