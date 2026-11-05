@echo off
REM Build this lab's workspace. Pure-Python packages only: no C++ compiler needed.
REM The build tree lives at a short path (R2B_BUILD_BASE, set by the pixi task) because of Windows' 260-character limit.
REM There is no --symlink-install (symlinks need Developer Mode): re-run this after every edit in ws\src.
setlocal
cd /d "%~dp0..\ws" || exit /b 1
if "%R2B_BUILD_BASE%"=="" set "R2B_BUILD_BASE=%SystemDrive%\rb\lab"
colcon build --build-base "%R2B_BUILD_BASE%" --event-handlers console_cohesion+
exit /b %ERRORLEVEL%
