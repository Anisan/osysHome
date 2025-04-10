@echo off

:: Activate the virtual environment
echo Activating the virtual environment...
call venv\Scripts\activate
if %ERRORLEVEL% neq 0 (
    echo Failed to activate the virtual environment.
    exit /b 1
)

:: Start the application
echo Starting the application...
start python main.py

:: Display the web address
echo The application is running. Access it at: http://127.0.0.1:5000/

:: Keep the script running until the user stops it
echo Press Ctrl+C to stop the application.
pause