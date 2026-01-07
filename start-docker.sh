#!/bin/bash

# Get the local network IP address
HOST_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')

if [ -z "$HOST_IP" ]; then
    echo "Warning: Could not detect local IP address"
    HOST_IP="<unknown>"
fi

echo "Detected host IP: $HOST_IP"

# Export the HOST_IP and run docker-compose
export HOST_IP
docker-compose up "$@"
