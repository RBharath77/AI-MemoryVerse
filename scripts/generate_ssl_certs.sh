#!/usr/bin/env bash
# ==============================================================================
# AI-MemoryVerse — Automated TLS/SSL Certificate Generator
# Generates high-grade self-signed SAN SSL certificates for HTTPS Load Balancing
# ==============================================================================

set -euo pipefail

SSL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../docker/nginx/ssl" && pwd)"
mkdir -p "${SSL_DIR}"

KEY_FILE="${SSL_DIR}/server.key"
CRT_FILE="${SSL_DIR}/server.crt"
CONF_FILE="${SSL_DIR}/openssl.cnf"

echo "🔐 Generating Commercial-Grade TLS/SSL Certificates for AI-MemoryVerse..."

# Create OpenSSL configuration with Subject Alternative Names (SAN)
cat <<EOF > "${CONF_FILE}"
[req]
default_bits        = 4096
default_md          = sha256
distinguished_name  = req_distinguished_name
x509_extensions     = v3_req
prompt              = no

[req_distinguished_name]
C                   = US
ST                  = California
L                   = San Francisco
O                   = AI-MemoryVerse
OU                  = Security & Infrastructure
CN                  = localhost

[v3_req]
basicConstraints    = CA:FALSE
keyUsage            = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage    = serverAuth, clientAuth
subjectAltName      = @alt_names

[alt_names]
DNS.1   = localhost
DNS.2   = *.localhost
DNS.3   = memoryverse.local
DNS.4   = *.memoryverse.local
DNS.5   = host.docker.internal
IP.1    = 127.0.0.1
IP.2    = ::1
EOF

# Generate 4096-bit RSA Private Key and Self-Signed Certificate
openssl req -x509 -nodes -days 3650 \
  -newkey rsa:4096 \
  -keyout "${KEY_FILE}" \
  -out "${CRT_FILE}" \
  -config "${CONF_FILE}"

# Set secure file permissions
chmod 600 "${KEY_FILE}"
chmod 644 "${CRT_FILE}"

echo "✅ SSL Certificates successfully generated:"
echo "   - Certificate: ${CRT_FILE}"
echo "   - Private Key: ${KEY_FILE}"
echo "   - Validity: 10 Years (SAN: localhost, 127.0.0.1, memoryverse.local)"

