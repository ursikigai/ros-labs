@echo off
REM Run a command with the built workspace overlay sourced.
REM Usage: pixi run cmd /c scripts\in_ws.bat <command ...>
call "%~dp0..\ws\install\setup.bat" || exit /b 1
%*
exit /b %ERRORLEVEL%
