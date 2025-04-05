#!/bin/bash
# Test HTTPS connection to the Time Capsule server

# Get root directory
ROOT_DIR="$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

# Change to root directory
cd "$ROOT_DIR"

# Set default port
PORT=${1:-8443}

echo "Testing HTTPS connection to localhost:$PORT..."
echo "Note: Certificate verification errors are expected for self-signed certificates."
echo ""

# Test basic HTTPS connection
echo "1. Testing basic HTTPS connection (allowing insecure connections):"
curl -k https://localhost:$PORT/health && echo "" || (echo "Connection failed!" && exit 1)

echo ""
echo "2. Testing HTTPS connection with server certificate verification:"
curl --cacert cert/ca.pem https://localhost:$PORT/health && echo "" || echo "Certificate verification failed (expected with self-signed certs)"

echo ""
echo "3. Testing HTTPS headers and security:"
curl -k -I https://localhost:$PORT/ | grep -E '(HTTP|Strict-Transport-Security|Content-Security|X-Content|X-Frame)'

echo ""
echo "HTTPS connection tests completed. If you saw JSON data in test 1, the server is working correctly with TLS." 