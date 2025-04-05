#!/bin/bash
# Script to set the admin password for Time Capsule production environment

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

print_header "Setting Admin Password for Production"

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    echo "No .env.production file found."
    read -p "Would you like to create one? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env.production
            echo "Created .env.production from example file."
        else
            # Create a more comprehensive default .env.production
            cat > .env.production << EOL
TIME_CAPSULE_ENV=prod
HOST=0.0.0.0
PORT=443
DEEPSEEK_API_KEY=
# Database configuration will use SQLite by default
EOL
            echo "Created default .env.production file."
        fi
    else
        echo "Cannot continue without a .env.production file."
        exit 1
    fi
fi

# Prompt for password
read -s -p "Enter admin password: " ADMIN_PWD
echo
read -s -p "Confirm admin password: " ADMIN_PWD_CONFIRM
echo

if [ "$ADMIN_PWD" != "$ADMIN_PWD_CONFIRM" ]; then
    echo "Passwords don't match. Please try again."
    exit 1
fi

# Set admin password in environment file
if [[ "$OS" == "Darwin" ]]; then
    # macOS version
    if grep -q "^ADMIN_PASSWORD=" .env.production; then
        sed -i '' "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=$ADMIN_PWD/" .env.production
    else
        echo "ADMIN_PASSWORD=$ADMIN_PWD" >> .env.production
    fi
else
    # Linux version
    if grep -q "^ADMIN_PASSWORD=" .env.production; then
        sed -i "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=$ADMIN_PWD/" .env.production
    else
        echo "ADMIN_PASSWORD=$ADMIN_PWD" >> .env.production
    fi
fi

print_header "Admin Password Set Successfully"
echo "The admin password has been set in .env.production"
echo
echo "You can now run the application in production mode using:"
echo "  ./scripts/run_production.sh"
echo
echo "Or if you need more control over the parameters:"
echo "  ./scripts/start.sh --env prod --host 0.0.0.0 --port 443"
echo
echo "Make sure you have SSL certificates in the cert/ directory."
echo "If you don't, you can generate test certificates with:"
echo "  ./scripts/generate_test_certs.sh" 