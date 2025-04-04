#!/bin/bash

# Time Capsule start script

# Navigate to script directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run migrations
echo "Running migrations..."
python migrate_data.py

# Start the application
echo "Starting Time Capsule application on port 8000..."
python app.py

# Deactivate virtual environment when done
if [ -d "venv" ]; then
    deactivate
fi 