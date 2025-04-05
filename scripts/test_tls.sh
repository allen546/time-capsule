#!/bin/bash
# Test script to verify TLS setup

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

# Detect OS for sed compatibility
OS=$(uname)
if [[ "$OS" == "Darwin" ]]; then
    # macOS version
    SED_CMD="sed -i ''"
else
    # Linux version
    SED_CMD="sed -i"
fi

# Check if certificates exist
print_header "Checking certificates"
if [ ! -f "cert/fullchain.pem" ] || [ ! -f "cert/privkey.pem" ]; then
    echo "ERROR: TLS certificates not found in cert/ directory."
    echo "Please run ./scripts/generate_test_certs.sh first."
    exit 1
fi
echo "✓ Found TLS certificates"

# Create test environment file if not exists
if [ ! -f ".env.test" ]; then
    print_header "Creating test environment file"
    cp .env.production .env.test
    
    # Set test-specific values
    $SED_CMD 's/PORT=443/PORT=8443/' .env.test
    $SED_CMD 's/DB_DRIVER=postgresql+asyncpg/DB_DRIVER=sqlite+aiosqlite/' .env.test
    
    # Set dummy passwords for testing
    $SED_CMD 's/ADMIN_PASSWORD=/ADMIN_PASSWORD=admin123/' .env.test
    $SED_CMD 's/ENCRYPTION_KEY=/ENCRYPTION_KEY=test123encryption456key/' .env.test
    
    echo "✓ Created test environment file .env.test"
fi

# Run the application with TLS on a test port
print_header "Starting Time Capsule with TLS"
echo "The application will start on https://localhost:8443"
echo "Press Ctrl+C to stop the server when done testing."
echo ""

# Set environment variables to use the test config
export TIME_CAPSULE_ENV=test
export CERT_DIR="./cert"
export PORT=8443
export SSL_CERT="fullchain.pem"
export SSL_KEY="privkey.pem"

# Start the actual server
print_header "Starting TLS server"
cd app && python app.py --env test --host 0.0.0.0 --port 8443 --ssl ../cert/fullchain.pem,../cert/privkey.pem 