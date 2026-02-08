#!/bin/bash
# Generate self-signed TLS certificates for local development
# These are NOT for production use - use Let's Encrypt or a proper CA

set -e

CERT_DIR="nginx/ssl"
mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/cert.pem" ] && [ -f "$CERT_DIR/key.pem" ]; then
    echo "Certificates already exist in $CERT_DIR/. Remove them first to regenerate."
    exit 0
fi

echo "Generating self-signed TLS certificate for local development..."

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$CERT_DIR/key.pem" \
    -out "$CERT_DIR/cert.pem" \
    -subj "/C=US/ST=Development/L=Local/O=ClinicalOntology/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1"

echo "Certificates generated:"
echo "  Certificate: $CERT_DIR/cert.pem"
echo "  Private key: $CERT_DIR/key.pem"
echo ""
echo "NOTE: These are self-signed certs for development only."
echo "Your browser will show a security warning - this is expected."
