#!/bin/bash
# Run a Python file on the remote TAU server
# 
# Usage: ./run_remote_python.sh [python_filename]
# Example: ./run_remote_python.sh marine_weather.py
#
# Configuration: Edit the PYTHON_FILE variable below

# ============================================================================
# CONFIGURATION - Change this to run different Python files
# ============================================================================
PYTHON_FILE="main.py"  # Change this to the Python file you want to run

# Server configuration
REMOTE_HOST="Shlomo1-pcl.eng.tau.ac.il"
REMOTE_USER="user"
REMOTE_PASSWORD="greek"
REMOTE_DIR="~/Ami"  # Directory where Python files are located

# ============================================================================
# Main Script
# ============================================================================

# Use command line argument if provided
if [ -n "$1" ]; then
    PYTHON_FILE="$1"
fi

echo "=========================================="
echo "Running Python file on remote server"
echo "=========================================="
echo "File: $PYTHON_FILE"
echo "Server: $REMOTE_USER@$REMOTE_HOST"
echo "Directory: $REMOTE_DIR"
echo "=========================================="
echo ""

# Check if VPN is connected (optional check)
if ! ifconfig | grep -q "utun.*inet"; then
    echo "⚠️  Warning: VPN may not be connected."
    echo "   Make sure GlobalProtect VPN is connected to vpn.tau.ac.il"
    echo ""
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 1
    fi
    echo ""
fi

# Run the Python file on remote server
expect << EOF
set timeout 90
set host "$REMOTE_HOST"
set user "$REMOTE_USER"
set password "$REMOTE_PASSWORD"
set python_file "$PYTHON_FILE"
set remote_dir "$REMOTE_DIR"

spawn ssh -o StrictHostKeyChecking=no \$user@\$host

expect {
    "password:" { send "\$password\r"; exp_continue }
    "Password:" { send "\$password\r"; exp_continue }
    "\$ " {
        send "cd \$remote_dir\r"
        expect "\$ " {
            send "python3 \$python_file\r"
            expect {
                "\$ " { send "exit\r" }
                "# " { send "exit\r" }
                timeout { 
                    send "\003"
                    expect "\$ " { send "exit\r" }
                }
            }
        }
    }
    "# " {
        send "cd \$remote_dir\r"
        expect "# " {
            send "python3 \$python_file\r"
            expect {
                "\$ " { send "exit\r" }
                "# " { send "exit\r" }
                timeout { 
                    send "\003"
                    expect "# " { send "exit\r" }
                }
            }
        }
    }
    eof
}
EOF

echo ""
echo "=========================================="
echo "Done!"
echo "=========================================="
