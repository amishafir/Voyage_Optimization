#!/bin/bash
# Simple script to connect to GlobalProtect VPN
# Portal: vpn.tau.ac.il
# Username: user
# Password: greek

echo "=========================================="
echo "Connecting to GlobalProtect VPN"
echo "Portal: vpn.tau.ac.il"
echo "Username: user"
echo "=========================================="
echo ""

# Open GlobalProtect GUI
echo "Opening GlobalProtect application..."
open /Applications/GlobalProtect.app

echo ""
echo "Please complete the connection in the GlobalProtect window:"
echo "  1. Portal: vpn.tau.ac.il"
echo "  2. Username: user"
echo "  3. Password: greek"
echo ""
echo "Waiting for connection..."
echo ""

# Wait a bit and check connection status
sleep 3

# Check if VPN is connected by looking for utun interfaces
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if ifconfig | grep -q "utun"; then
        echo "✓ VPN connection detected!"
        echo ""
        echo "Your VPN IP address:"
        ifconfig | grep -A 2 "utun" | grep "inet " | head -1
        echo ""
        echo "VPN is connected. You can now connect to remote servers."
        exit 0
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo -n "."
done

echo ""
echo "⚠️  Connection status unclear. Please check GlobalProtect window."
echo "If connected, you can verify with: ifconfig | grep utun"

