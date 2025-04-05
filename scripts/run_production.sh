#!/bin/bash
# Simplified script for running Time Capsule in production mode

# Exit on error
set -e

# Print section header
function print_header() {
    echo "====================================================="
    echo " $1"
    echo "====================================================="
}

# Get root directory
ROOT_DIR="$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

# Change to root directory
cd "$ROOT_DIR"

# Check for .env.production
if [ ! -f ".env.production" ]; then
    print_header "ERROR: Missing configuration"
    echo "No .env.production file found."
    echo "Please run ./scripts/set_admin_password.sh first to set up production environment."
    exit 1
fi

# Check for admin password
if ! grep -q "^ADMIN_PASSWORD=.\+" .env.production; then
    print_header "ERROR: Admin password not set"
    echo "Admin password is not set in .env.production."
    echo "Please run ./scripts/set_admin_password.sh to set it."
    exit 1
fi

# Run in production mode
print_header "Starting Time Capsule in PRODUCTION mode"
echo "Using configuration from .env.production"
echo "TLS/SSL will be enabled automatically"
echo

# Load environment variables from .env.production
set -o allexport
source .env.production
set +o allexport

# Set HOST and PORT if not defined in .env.production
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-443}"

echo "Server will listen on $HOST:$PORT"
echo "Press Ctrl+C to stop."
echo

# Make the scripts executable if they aren't already
chmod +x ./scripts/start.sh

# Start the application with explicit parameters
./scripts/start.sh --env prod --host "$HOST" --port "$PORT" --ssl --tls-strict-host 