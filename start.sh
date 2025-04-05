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

# Default values
ENV="dev"
HOST="0.0.0.0"
PORT="8000"
DEBUG=""

# Help function
function show_help {
    echo "Usage: ./start.sh [options]"
    echo
    echo "Options:"
    echo "  -e, --env ENV       Set environment: dev, prod, test (default: dev)"
    echo "  -h, --host HOST     Set host address (default: 0.0.0.0)"
    echo "  -p, --port PORT     Set port number (default: 8000)"
    echo "  -d, --debug         Enable debug mode"
    echo "  --help              Show this help message and exit"
    echo
    echo "Example:"
    echo "  ./start.sh --env prod --port 8080"
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

# Security checks for production environment
if [[ "$ENV" == "prod" ]]; then
    print_header "Running production security checks"
    
    # Check if admin password is set
    if [ -z "$(python3 -c 'from app.config import get_secret; print(get_secret("ADMIN_PASSWORD") or "")')" ]; then
        echo "ERROR: Admin password is not set for production environment."
        echo "Run './manage_secrets.py set --env prod ADMIN_PASSWORD' to set it."
        exit 1
    fi
    
    # Check for proper SSL settings in production
    verify_ssl=$(python3 -c 'from app.config import CONFIG; print(CONFIG.get("verify_ssl", False))')
    if [[ "$verify_ssl" != "True" ]]; then
        echo "WARNING: SSL verification is disabled in production. This is unsafe!"
        echo "Consider editing the configuration to enable SSL verification."
    fi
    
    # Check if using a secure database for production
    db_driver=$(python3 -c 'from app.config import CONFIG; print(CONFIG["db"]["driver"])')
    if [[ "$db_driver" == *"sqlite"* ]]; then
        echo "WARNING: Using SQLite in production is not recommended."
        echo "Consider configuring a more robust database like PostgreSQL."
    fi
    
    # Check if DEBUG is enabled in production
    if [[ -n "$DEBUG" ]]; then
        echo "WARNING: Debug mode enabled in production. This exposes sensitive information."
        echo "Remove the -d or --debug flag for production use."
    fi
fi

# Create log directory if it doesn't exist
mkdir -p logs

# Print startup information
echo "Starting Time Capsule in $ENV environment"
echo "Server will listen on $HOST:$PORT"

# Export environment variables
export TIME_CAPSULE_ENV=$ENV

# Set database paths (if needed for environment-specific paths)
# export DB_PATH=path/to/$ENV/data

# Start the application with output logging
if [[ "$ENV" == "prod" ]]; then
    echo "Starting in production mode with log to file"
    cd app && python3 app.py --env $ENV --host $HOST --port $PORT $DEBUG 2>&1 | tee -a ../logs/timecapsule_$(date +%Y%m%d).log
else
    cd app && python3 app.py --env $ENV --host $HOST --port $PORT $DEBUG
fi 