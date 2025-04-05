#!/bin/bash
# Time Capsule Startup Script

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

# Default values
ENV="dev"
HOST="0.0.0.0"
PORT="8000"
DEBUG=""
SSL=""
TLS_STRICT_HOST=""

# Help function
function show_help {
    echo "Usage: ./scripts/start.sh [options]"
    echo
    echo "Options:"
    echo "  -e, --env ENV       Set environment: dev, prod, test (default: dev)"
    echo "  -h, --host HOST     Set host address (default: 0.0.0.0)"
    echo "  -p, --port PORT     Set port number (default: 8000)"
    echo "  -d, --debug         Enable debug mode"
    echo "  --ssl               Enable SSL"
    echo "  --tls-strict-host   Require SNI (Server Name Indication) from clients"
    echo "  --help              Show this help message and exit"
    echo
    echo "Example:"
    echo "  ./scripts/start.sh --env prod --port 443 --ssl"
}

# Parse command line arguments
while [ "$1" != "" ]; do
    case $1 in
        -e | --env )           shift
                               ENV=$1
                               ;;
        -h | --host )          shift
                               HOST=$1
                               ;;
        -p | --port )          shift
                               PORT=$1
                               ;;
        -d | --debug )         DEBUG="--debug"
                               ;;
        --ssl )                SSL="--ssl"
                               ;;
        --tls-strict-host )    TLS_STRICT_HOST="--tls-strict-host"
                               ;;
        --help )               show_help
                               exit
                               ;;
        * )                    echo "Unknown option: $1"
                               show_help
                               exit 1
    esac
    shift
done

# Validate environment
if [[ "$ENV" != "dev" && "$ENV" != "prod" && "$ENV" != "test" ]]; then
    echo "Error: Environment must be one of: dev, prod, test"
    exit 1
fi

# Set up Python environment
print_header "Setting up Python environment"
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
    PYTHON_CMD="python3"
else
    # Use python3 directly
    if ! command -v python3 &> /dev/null; then
        echo "ERROR: python3 command not found."
        echo "Please install Python 3.8+ or run ./scripts/install.sh to set up a virtual environment."
        exit 1
    fi
    
    PYTHON_CMD="python3"
    echo "Using Python command: $PYTHON_CMD"
    echo "Consider running ./scripts/install.sh to set up a virtual environment."
fi

# Build SSL arguments for the Python command
SSL_ARGS=""

# Check for SSL configuration
if [[ -n "$SSL" ]]; then
    SSL_ARGS="$SSL"
    echo "SSL mode enabled"
elif [[ "$ENV" == "prod" && "$PORT" == "443" ]]; then
    # Default for production on port 443: enable SSL
    echo "SSL mode automatically enabled for production on port 443"
    SSL_ARGS="--ssl"
fi

# Security checks for production environment
if [[ "$ENV" == "prod" ]]; then
    print_header "Running production security checks"
    
    # Check if admin password is set
    if [ -z "$($PYTHON_CMD -c 'from app.config import get_secret; print(get_secret("ADMIN_PASSWORD") or "")')" ]; then
        echo "ERROR: Admin password is not set for production environment."
        echo "Run './scripts/set_admin_password.sh' to set it."
        exit 1
    fi
    
    # Check for proper SSL settings in production
    verify_ssl=$($PYTHON_CMD -c 'from app.config import CONFIG; print(CONFIG.get("verify_ssl", False))')
    if [[ "$verify_ssl" != "True" ]]; then
        echo "WARNING: SSL verification is disabled in production. This is unsafe!"
        echo "Consider editing the configuration to enable SSL verification."
    fi
    
    # Check if using a secure database for production
    db_driver=$($PYTHON_CMD -c 'from app.config import CONFIG; print(CONFIG["db"]["driver"])')
    if [[ "$db_driver" == *"sqlite"* ]]; then
        echo "WARNING: Using SQLite in production is not recommended."
        echo "Consider configuring a more robust database like PostgreSQL."
    fi
    
    # Check if DEBUG is enabled in production
    if [[ -n "$DEBUG" ]]; then
        echo "WARNING: Debug mode enabled in production. This exposes sensitive information."
        echo "Remove the -d or --debug flag for production use."
    fi
    
    # Check for SSL in production
    if [[ -z "$SSL_ARGS" && "$PORT" == "443" ]]; then
        echo "ERROR: Running on port 443 without SSL configuration is not allowed."
        echo "Please enable SSL with the --ssl option."
        exit 1
    fi
fi

# Create log directory if it doesn't exist
mkdir -p logs

# Print startup information
print_header "Starting Time Capsule"
echo "Environment: $ENV"
echo "Server will listen on $HOST:$PORT"
echo "Debug mode: ${DEBUG:+enabled}"
echo "SSL mode: ${SSL_ARGS:+enabled}"

# Export environment variables
export TIME_CAPSULE_ENV=$ENV

# Set database paths (if needed for environment-specific paths)
# export DB_PATH=path/to/$ENV/data

# Construct the TLS strict host argument
if [[ -n "$TLS_STRICT_HOST" ]]; then
    TLS_STRICT_HOST_ARGS="--tls-strict-host"
else
    TLS_STRICT_HOST_ARGS=""
fi

# Start the application with output logging
if [[ "$ENV" == "prod" ]]; then
    echo "Starting in production mode with log to file"
    cd app && sudo $PYTHON_CMD app.py --env $ENV --host "$HOST" --port "$PORT" $DEBUG $SSL_ARGS $TLS_STRICT_HOST_ARGS 2>&1 | tee -a ../logs/timecapsule_$(date +%Y%m%d).log
else
    cd app && sudo $PYTHON_CMD app.py --env $ENV --host "$HOST" --port "$PORT" $DEBUG $SSL_ARGS $TLS_STRICT_HOST_ARGS
fi

# Deactivate virtual environment if it was activated
if [ -d "venv" ] && [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "Deactivating virtual environment..."
    deactivate || true
fi 