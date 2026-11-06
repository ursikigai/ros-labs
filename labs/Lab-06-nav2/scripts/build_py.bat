@echo off
REM Build this lab's workspace. Pure-Python packages only: no C++ compiler needed.
REM The build tree lives at a short path (R2B_BUILD_BASE, set by the pixi task) because of Windows' 260-character limit.
REM There is no --symlink-install (symlinks need Developer Mode): re-run this after every edit in ws\src.
setlocal
cd /d "%~dp0..\ws" || exit /b 1
if "%R2B_BUILD_BASE%"=="" set "R2B_BUILD_BASE=%SystemDrive%\rb\lab"
REM A build tree last used by another copy of this lab has a CMake cache pointing at that copy: start clean.
set "PREV="
if exist "%R2B_BUILD_BASE%\.owner" set /p PREV=<"%R2B_BUILD_BASE%\.owner"
if /i not "%PREV%"=="%CD%" (
  if exist "%R2B_BUILD_BASE%" rmdir /s /q "%R2B_BUILD_BASE%"
  mkdir "%R2B_BUILD_BASE%"
)
>"%R2B_BUILD_BASE%\.owner" echo %CD%
colcon build --build-base "%R2B_BUILD_BASE%" --event-handlers console_cohesion+
exit /b %ERRORLEVEL%
