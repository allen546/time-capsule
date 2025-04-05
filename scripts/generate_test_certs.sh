#!/bin/bash
# Generate self-signed TLS certificates for testing

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

# Create cert directory if it doesn't exist
print_header "Creating certificates directory"
mkdir -p cert
cd cert

# Clean up any existing certificates
print_header "Cleaning up existing certificates"
rm -f *.pem *.key *.csr *.srl

# Generate CA key and certificate
print_header "Generating CA certificate"
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days 1825 -out ca.pem \
    -subj "/C=US/ST=California/L=San Francisco/O=Time Capsule Test/OU=Testing/CN=Time Capsule CA"

# Generate server key
print_header "Generating server key"
openssl genrsa -out privkey.pem 2048

# Create a config file for SAN extension
cat > openssl.cnf << EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = req_ext

[dn]
C = US
ST = California
L = San Francisco
O = Time Capsule Test
OU = Server
CN = localhost

[req_ext]
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = 127.0.0.1
EOF

# Generate CSR using the config file
print_header "Generating server CSR"
openssl req -new -key privkey.pem -out server.csr -config openssl.cnf

# Create a config for signing
cat > sign.cnf << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = 127.0.0.1
EOF

# Sign the CSR with the CA key
print_header "Signing the server certificate"
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key \
    -CAcreateserial -out server.pem -days 825 -sha256 \
    -extfile sign.cnf

# Create fullchain by concatenating server certificate and CA certificate
print_header "Creating fullchain certificate"
cat server.pem ca.pem > fullchain.pem

# Set the proper permissions
print_header "Setting proper permissions"
chmod 600 privkey.pem
chmod 644 fullchain.pem

# Clean up temporary files
print_header "Cleaning up"
rm -f server.csr openssl.cnf sign.cnf

# Verify the certificates
print_header "Verifying certificates"
openssl verify -CAfile ca.pem fullchain.pem
openssl x509 -in fullchain.pem -text -noout | grep -A1 "Subject:"
openssl x509 -in fullchain.pem -text -noout | grep -A1 "Issuer:"

print_header "Certificate generation completed"
echo "Generated files:"
echo " - fullchain.pem: Server certificate + CA certificate"
echo " - privkey.pem: Server private key"
echo ""
echo "You can now run the application in production mode with these certificates:"
echo "  ./scripts/run_production.sh"
echo ""
echo "Note: Since these are self-signed certificates, browsers will show a security warning."
echo "To bypass this in Chrome, type 'thisisunsafe' while the warning is displayed."
echo "For production use, obtain proper certificates from a trusted CA like Let's Encrypt."

cd "$ROOT_DIR" 