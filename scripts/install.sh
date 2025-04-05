#!/bin/bash
# Time Capsule Installation Script
# This script creates a virtual environment and installs all dependencies

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

# Detect Python version
PYTHON_CMD=""
for cmd in python3
do
    if command -v $cmd &> /dev/null; then
        version=$($cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        major=$(echo $version | cut -d. -f1)
        minor=$(echo $version | cut -d. -f2)
        
        if [ "$major" -ge 3 ] && [ "$minor" -ge 8 ]; then
            PYTHON_CMD=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python 3.8 or higher is required but not found."
    echo "Please install Python 3.8+ and try again."
    exit 1
fi

# Show Python version
print_header "Python Information"
$PYTHON_CMD --version
echo "Using Python executable: $PYTHON_CMD"

# Create virtual environment if it doesn't exist
print_header "Setting up virtual environment"
if [ ! -d "venv" ]; then
    echo "Creating new virtual environment..."
    $PYTHON_CMD -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Update pip, setuptools and wheel
print_header "Updating basic packages"
pip install --upgrade pip setuptools wheel

# Install dependencies
print_header "Installing dependencies"
pip install -r requirements.txt

# Setup data directories
print_header "Setting up application directories"
mkdir -p logs
mkdir -p app/data
mkdir -p cert

# Set up admin password for production
print_header "Setting up admin password"
echo "Would you like to set an admin password for production mode? (y/n)"
read -p "This is required when running in production mode: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -s -p "Enter admin password: " ADMIN_PWD
    echo
    read -s -p "Confirm admin password: " ADMIN_PWD_CONFIRM
    echo
    
    if [ "$ADMIN_PWD" != "$ADMIN_PWD_CONFIRM" ]; then
        echo "Passwords don't match. Please try again later."
    else
        # Create production environment file if it doesn't exist
        if [ ! -f ".env.production" ]; then
            if [ -f ".env.example" ]; then
                cp .env.example .env.production
                echo "Created .env.production from example file."
            else
                echo "TIME_CAPSULE_ENV=prod" > .env.production
                echo "Created minimal .env.production file."
            fi
        fi
        
        # Set admin password in environment file
        if [[ "$OS" == "Darwin" ]]; then
            # macOS version
            sed -i '' "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=$ADMIN_PWD/" .env.production
        else
            # Linux version
            sed -i "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=$ADMIN_PWD/" .env.production
        fi
        
        echo "Admin password set successfully in .env.production"
    fi
else
    echo "Skipping admin password setup. You'll need to set it before running in production mode."
fi

# Create example environment file if it doesn't exist
if [ ! -f ".env" ]; then
    print_header "Creating default environment file"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Created .env from example file."
    else
        echo "TIME_CAPSULE_ENV=dev" > .env
        echo "Created minimal .env file."
    fi
fi

# Generate self-signed certificates for testing if they don't exist
if [ ! -f "cert/fullchain.pem" ] || [ ! -f "cert/privkey.pem" ]; then
    print_header "Generating test certificates"
    
    read -p "Would you like to generate self-signed TLS certificates for testing? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ./scripts/generate_test_certs.sh
    else
        echo "Skipping certificate generation."
    fi
fi

print_header "Installation Complete"
echo "Time Capsule has been successfully installed!"
echo 
echo "To start the application in development mode:"
echo "  ./scripts/start.sh"
echo
echo "To start with TLS enabled (if certificates are generated):"
echo "  ./scripts/test_tls.sh"
echo
echo "To activate the virtual environment manually:"
echo "  source venv/bin/activate"
echo
echo "Happy time traveling! 🚀" 