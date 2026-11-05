@echo off
REM Run a command with an UPSTREAM overlay (built by build_upstream.bat) sourced.
REM Usage: pixi run cmd /c scripts\in_upstream.bat <name> <command ...>
REM Example: pixi run cmd /c scripts\in_upstream.bat packt ros2 launch my_robot_bringup number_app.launch.py
REM Set COURSE=1 to ALSO source the course workspace (ws\install), e.g. for the Nav2 + Essentials test.
setlocal
set "NAME=%~1"
set "UP=%~dp0..\upstream_ws\%NAME%\install"
if "%NAME%"=="" (echo usage: in_upstream.bat ^<name^> ^<command^> & exit /b 2)
if not exist "%UP%\setup.bat" (echo ERROR: upstream_ws\%NAME% is not built. Run build_upstream.bat first. & exit /b 1)
if "%COURSE%"=="1" call "%~dp0..\ws\install\setup.bat" || exit /b 1
call "%UP%\setup.bat" || exit /b 1
REM Some upstream CMake files install plugin DLLs to lib\<pkg> (Linux habit) instead of bin\; Windows only finds
REM DLLs through PATH, so add those folders.
for /d %%D in ("%UP%\*") do if exist "%%D\lib\%%~nxD" set "PATH=%%D\lib\%%~nxD;%PATH%"
REM %* ignores SHIFT, and %1..%9 would split an argument such as model:=x at the '=' (and stop at 9 words),
REM so take everything after the first word (the overlay name) from %* itself.
set "ALL=%*"
call set "REST=%%ALL:*%NAME% =%%"
%REST%
exit /b %ERRORLEVEL%
