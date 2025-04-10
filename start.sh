#!/bin/bash

# Activate the virtual environment
echo "Activating the virtual environment..."
source venv/bin/activate || { echo "Failed to activate the virtual environment."; exit 1; }

# Start the application
echo "Starting the application..."
python3 main.py &

# Get the PID of the running application
APP_PID=$!

# Wait for the application to start
sleep 2

# Display the web address
echo "The application is running. Access it at: http://server_ip:5000/"

# Keep the script running until the user stops it
echo "Press Ctrl+C to stop the application."
wait $APP_PID