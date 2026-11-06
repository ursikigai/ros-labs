@echo off
REM Build an UPSTREAM repository (cloned into upstream\) in its own overlay, away from the course workspace.
REM Usage (from repo root):  pixi run cmd /c scripts\build_upstream.bat <name> <path-to-sources> [colcon args...]
REM   <name>  : short name; install goes to upstream_ws\<name>\install, build tree to %R2B_UP_ROOT%\<name>
REM   <path>  : folder searched for packages (relative to repo root)
REM Example :  scripts\build_upstream.bat packt upstream\ros2-from-scratch\ch9
setlocal
set "NAME=%~1"
if "%R2B_UP_ROOT%"=="" set "R2B_UP_ROOT=%SystemDrive%\r2b_up"
set "SRC=%~2"
if "%NAME%"=="" (echo usage: build_upstream.bat ^<name^> ^<path^> [colcon args] & exit /b 2)
if "%SRC%"=="" (echo usage: build_upstream.bat ^<name^> ^<path^> [colcon args] & exit /b 2)
set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" set "VCVARS=C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" (echo ERROR: vcvars64.bat not found & exit /b 1)
set "PATH=%PATH%;%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
call "%VCVARS%" >nul || exit /b 1
cd /d "%~dp0.." || exit /b 1
REM A build tree last used by another copy of this lab has a CMake cache pointing at that copy: start clean.
set "PREV="
if exist "%R2B_UP_ROOT%\%NAME%\.owner" set /p PREV=<"%R2B_UP_ROOT%\%NAME%\.owner"
if /i not "%PREV%"=="%CD%" (
  if exist "%R2B_UP_ROOT%\%NAME%" rmdir /s /q "%R2B_UP_ROOT%\%NAME%"
  mkdir "%R2B_UP_ROOT%\%NAME%"
)
>"%R2B_UP_ROOT%\%NAME%\.owner" echo %CD%
REM NOTE: %* ignores SHIFT (it always holds ALL original arguments), so gather the extras by hand.
shift
shift
set "EXTRA=%1 %2 %3 %4 %5 %6 %7 %8 %9"
REM Release (no python_d.exe in conda), short build base (260-char path limit), no symlinks (needs privileges).
colcon --log-base "upstream_ws\%NAME%\log" build --base-paths "%SRC%" --build-base "%R2B_UP_ROOT%\%NAME%" ^
  --install-base "upstream_ws\%NAME%\install" --event-handlers console_cohesion+ %EXTRA% ^
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -GNinja "-Dconsole_bridge_DIR=%CONDA_PREFIX%\Library\CMake"
REM ^ pluginlib/class_loader need console_bridge, whose CMake config sits in Library\CMake (not on the default search path).
exit /b %ERRORLEVEL%
