#!/bin/bash
# Quick script to connect to TAU server via VPN
# Server: Shlomo1-pcl.eng.tau.ac.il
# Username: user
# Password: greek

echo "=========================================="
echo "Connecting to TAU Server"
echo "Server: Shlomo1-pcl.eng.tau.ac.il"
echo "=========================================="
echo ""

# Check if VPN is connected
if ! ifconfig | grep -q "utun.*inet"; then
    echo "⚠️  VPN not connected. Connecting to VPN first..."
    ./connect_vpn.sh
    sleep 3
fi

# Connect to server using expect
expect << 'EOF'
set timeout 30
set host "Shlomo1-pcl.eng.tau.ac.il"
set user "user"
set password "greek"

spawn ssh -o StrictHostKeyChecking=no $user@$host

expect {
    "password:" {
        send "$password\r"
        exp_continue
    }
    "Password:" {
        send "$password\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    "$ " {
        interact
    }
    "# " {
        interact
    }
    eof
}
EOF

