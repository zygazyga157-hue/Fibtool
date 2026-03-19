@echo off
REM Scheduled Tasks Runner for FibTool
REM This batch file runs the Python scheduled tasks script

cd /d "%~dp0"
python scheduled_tasks.py

REM Exit with the same code as Python script
exit /b %ERRORLEVEL%
