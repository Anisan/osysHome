#!/bin/bash

# Check for required tools
command -v wget >/dev/null 2>&1 || { echo >&2 "wget is not installed. Please install wget and try again."; exit 1; }
command -v unzip >/dev/null 2>&1 || { echo >&2 "unzip is not installed. Please install unzip and try again."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo >&2 "Python3 is not installed. Please install Python3 and try again."; exit 1; }

# Download and extract the main repository
echo "Downloading the osysHome repository..."
if ! wget -q https://github.com/Anisan/osysHome/archive/refs/heads/master.zip -O osysHome.zip; then
    echo "Error downloading the repository."
    exit 1
fi

echo "Extracting the osysHome repository..."
if ! unzip -q osysHome.zip; then
    echo "Error extracting the repository."
    exit 1
fi

mv osysHome-master osysHome || { echo "Failed to rename the extracted directory."; exit 1; }

# Clean up the downloaded ZIP file
rm -f osysHome.zip

cd osysHome || { echo "Failed to navigate to the osysHome directory."; exit 1; }

# Create a virtual environment
echo "Creating a virtual environment..."
if ! python3 -m venv venv; then
    echo "Error creating the virtual environment."
    exit 1
fi

# Activate the virtual environment
echo "Activating the virtual environment..."
source venv/bin/activate || { echo "Failed to activate the virtual environment."; exit 1; }

# Install dependencies
echo "Installing dependencies from requirements.txt..."
if ! pip install -r requirements.txt; then
    echo "Error installing dependencies."
    exit 1
fi

# Create the plugins directory
echo "Creating the plugins directory..."
mkdir -p plugins || { echo "Failed to create the plugins directory."; exit 1; }

# List of all modules
declare -A modules=(
    ["Modules"]="https://github.com/Anisan/osysHome-Modules/archive/refs/heads/master.zip"
    ["Objects"]="https://github.com/Anisan/osysHome-Objects/archive/refs/heads/master.zip"
    ["Users"]="https://github.com/Anisan/osysHome-Users/archive/refs/heads/master.zip"
    ["Scheduler"]="https://github.com/Anisan/osysHome-Scheduler/archive/refs/heads/master.zip"
    ["wsServer"]="https://github.com/Anisan/osysHome-wsServer/archive/refs/heads/master.zip"
    ["Dashboard"]="https://github.com/Anisan/osysHome-Dashboard/archive/refs/heads/master.zip"
)

# Download and extract all modules
echo "Downloading and extracting all modules..."
for module in "${!modules[@]}"; do
    repo="${modules[$module]}"
    dir="plugins/$module"
    zip_file="$module.zip"

    echo "Downloading module: $module..."
    if ! wget -q "$repo" -O "$zip_file"; then
        echo "Error downloading module: $repo"
        exit 1
    fi

    # Ensure the target directory is empty before extraction
    rm -rf "$dir" && mkdir -p "$dir"

    echo "Extracting module: $module..."
    if ! unzip -q "$zip_file" -d "$dir"; then
        echo "Error extracting module: $module"
        exit 1
    fi

    # Move the contents of the extracted folder into the target directory
    extracted_dir=$(unzip -Z1 "$zip_file" | head -1 | cut -d'/' -f1)
    mv "$dir/$extracted_dir"/* "$dir/" && rm -rf "$dir/$extracted_dir"

    # Clean up the downloaded ZIP file
    rm -f "$zip_file"
done

# Create the settings file
echo "Creating the settings.py file..."
if ! cp settings_sample.py settings.py; then
    echo "Error creating the settings file."
    exit 1
fi

echo "Setup complete. Please modify the database settings in settings.py."

# Generate documentation using pdoc
echo "Generating documentation with pdoc..."
if ! pdoc --docformat google --no-show-source --output-dir docs settings_sample.py app plugins; then
    echo "Error generating documentation."
    exit 1
fi

echo "Documentation generated successfully in the 'docs' directory."

# Instructions for starting the application
echo "Installation completed successfully!"
echo "To start the application, run the following command:"
echo "  ./start.sh"