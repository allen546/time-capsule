#!/bin/bash
# Time Capsule Production Startup Script

# Exit on error
set -e

# Print section header
function print_header() {
    echo "====================================================="
    echo " $1"
    echo "====================================================="
}

# Default values
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-443}"
CERT_DIR="${CERT_DIR:-./cert}"
ROOT_DIR="$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

# Change to root directory
cd "$ROOT_DIR"

# Load environment variables from .env.production
if [ -f .env.production ]; then
    print_header "Loading production environment variables"
    set -o allexport
    source .env.production
    set +o allexport
fi

# Verify TLS certificates exist
print_header "Verifying TLS certificates"
SSL_CERT="${SSL_CERT:-fullchain.pem}"
SSL_KEY="${SSL_KEY:-privkey.pem}"

if [ ! -f "$CERT_DIR/$SSL_CERT" ]; then
    echo "ERROR: SSL certificate not found at $CERT_DIR/$SSL_CERT"
    exit 1
fi

if [ ! -f "$CERT_DIR/$SSL_KEY" ]; then
    echo "ERROR: SSL key not found at $CERT_DIR/$SSL_KEY"
    exit 1
fi

echo "✓ Found SSL certificate: $CERT_DIR/$SSL_CERT"
echo "✓ Found SSL key: $CERT_DIR/$SSL_KEY"

# Security checks for production environment
print_header "Running production security checks"

# Check if admin password is set
if [ -z "$ADMIN_PASSWORD" ]; then
    echo "WARNING: Admin password is not set in .env.production."
    echo "Please set ADMIN_PASSWORD for better security."
fi

# Check if ENCRYPTION_KEY is set
if [ -z "$ENCRYPTION_KEY" ]; then
    echo "WARNING: Encryption key is not set in .env.production."
    echo "Please set ENCRYPTION_KEY for better security."
fi

# Create log directory if it doesn't exist
mkdir -p logs

# Export environment variables
export TIME_CAPSULE_ENV=prod
export SSL_CERT_PATH="$CERT_DIR/$SSL_CERT"
export SSL_KEY_PATH="$CERT_DIR/$SSL_KEY"

# Print startup information
print_header "Starting Time Capsule in PRODUCTION mode"
echo "Server will listen on $HOST:$PORT with TLS/SSL enabled"
echo "Log files will be saved to ./logs/"

# Start the application with output logging
cd app && python app.py \
    --env prod \
    --host $HOST \
    --port $PORT \
    --ssl $SSL_CERT_PATH,$SSL_KEY_PATH \
    2>&1 | tee -a ../logs/timecapsule_$(date +%Y%m%d).log 