@echo off
REM Build the course workspace with MSVC activated.
REM Usage (from repo root):  pixi run build            -> all packages
REM                          pixi run build <pkg ...>  -> only the named packages (+ deps)
setlocal
set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" set "VCVARS=C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" (
  echo ERROR: vcvars64.bat not found. Install "Visual Studio Build Tools" with the C++ workload.
  exit /b 1
)
REM vcvars64.bat shells out to vswhere.exe, which lives in the VS Installer folder.
set "PATH=%PATH%;%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
call "%VCVARS%" >nul || exit /b 1
cd /d "%~dp0..\ws" || exit /b 1
REM NOTE: no --symlink-install. Creating symlinks on Windows needs Developer Mode or admin
REM rights, so Python edits are picked up by re-running this script (takes a few seconds).
REM Release is required: the default Debug config needs python_d.exe, which conda does not ship.
REM The build tree lives at a SHORT path: generated rosidl object files exceed Windows' 260
REM character path limit inside the repo (271 chars) and MSVC fails with C1083. Override with
REM the R2B_BUILD_BASE environment variable if C:\ is not writable.
if "%R2B_BUILD_BASE%"=="" set "R2B_BUILD_BASE=%SystemDrive%\r2b"
REM A build tree last used by another copy of this lab has a CMake cache pointing at that copy: start clean.
set "PREV="
if exist "%R2B_BUILD_BASE%\.owner" set /p PREV=<"%R2B_BUILD_BASE%\.owner"
if /i not "%PREV%"=="%CD%" (
  if exist "%R2B_BUILD_BASE%" rmdir /s /q "%R2B_BUILD_BASE%"
  mkdir "%R2B_BUILD_BASE%"
)
>"%R2B_BUILD_BASE%\.owner" echo %CD%
if "%~1"=="" (
  colcon build --build-base "%R2B_BUILD_BASE%" --event-handlers console_cohesion+ --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -GNinja
) else (
  colcon build --build-base "%R2B_BUILD_BASE%" --event-handlers console_cohesion+ --packages-up-to %* --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -GNinja
)
exit /b %ERRORLEVEL%
