@echo off

:: Check if Python is installed
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python is not installed. Please install Python and try again.
    exit /b 1
)

:: Create a directory for the project
if not exist osysHome (
    mkdir osysHome
)
cd osysHome

:: Download and extract the main repository
echo Downloading the osysHome repository...
curl -L https://github.com/Anisan/osysHome/archive/refs/heads/master.zip -o osysHome.zip
if %ERRORLEVEL% neq 0 (
    echo Error downloading the repository.
    exit /b 1
)

echo Extracting the osysHome repository...
tar -xf osysHome.zip --strip-components=1
if %ERRORLEVEL% neq 0 (
    echo Error extracting the repository.
    exit /b 1
)

:: Clean up the downloaded ZIP file
del osysHome.zip

:: Create a virtual environment
echo Creating a virtual environment...
python -m venv venv
if %ERRORLEVEL% neq 0 (
    echo Error creating the virtual environment.
    exit /b 1
)

:: Activate the virtual environment
echo Activating the virtual environment...
call venv\Scripts\activate
if %ERRORLEVEL% neq 0 (
    echo Failed to activate the virtual environment.
    exit /b 1
)

:: Install dependencies
echo Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo Error installing dependencies.
    exit /b 1
)

:: Create the plugins directory
echo Creating the plugins directory...
mkdir plugins
if %ERRORLEVEL% neq 0 (
    echo Failed to create the plugins directory.
    exit /b 1
)
:: Download and extract all modules
echo Downloading and extracting all modules...
for %%M in (
    "Modules=https://github.com/Anisan/osysHome-Modules/archive/refs/heads/master.zip"
    "Objects=https://github.com/Anisan/osysHome-Objects/archive/refs/heads/master.zip"
    "Users=https://github.com/Anisan/osysHome-Users/archive/refs/heads/master.zip"
    "Scheduler=https://github.com/Anisan/osysHome-Scheduler/archive/refs/heads/master.zip"
    "wsServer=https://github.com/Anisan/osysHome-wsServer/archive/refs/heads/master.zip"
    "Dashboard=https://github.com/Anisan/osysHome-Dashboard/archive/refs/heads/master.zip"
) do (
    :: Remove surrounding quotes from %%M
    set "MODULE_PAIR=%%M"
    setlocal enabledelayedexpansion
    set "MODULE_PAIR=!MODULE_PAIR:"=!"
    for /f "tokens=1,2 delims==" %%A in ("!MODULE_PAIR!") do (
        echo Downloading module: %%A... %%B
        powershell -Command "Invoke-WebRequest -Uri '%%B' -OutFile %%A.zip"
        if %ERRORLEVEL% neq 0 (
            echo Error downloading module: %%A
            exit /b 1
        )
		
		:: Check if the ZIP file exists
		if not exist "%%A.zip" (
			echo File %%A.zip not found. Skipping module: %%A
			exit /b 1
		)

        echo Extracting module: %%A...
        :: Extract the ZIP file into the plugins directory
        tar -xf "%%A.zip" -C plugins
        if %ERRORLEVEL% neq 0 (
            echo Error extracting module: %%A
            exit /b 1
        )

        :: Rename the extracted folder to match the module name
        move "plugins\osysHome-%%A-master" "plugins\%%A"
        if %ERRORLEVEL% neq 0 (
            echo Error renaming module folder: %%A
            exit /b 1
        )

        :: Clean up the downloaded ZIP file
        del %%A.zip
    )
)

:: Create the settings file
echo Creating the settings.py file...
copy settings_sample.py settings.py >nul
if %ERRORLEVEL% neq 0 (
    echo Error creating the settings file.
    exit /b 1
)

:: Generate documentation using pdoc
echo Generating documentation with pdoc...
pdoc --docformat google --no-show-source --output-dir docs settings_sample.py app plugins
if %ERRORLEVEL% neq 0 (
    echo Error generating documentation.
    exit /b 1
)

echo Documentation generated successfully in the 'docs' directory.

:: Instructions for starting the application
echo Installation completed successfully!
echo To start the application, run the following command:
echo   start.bat