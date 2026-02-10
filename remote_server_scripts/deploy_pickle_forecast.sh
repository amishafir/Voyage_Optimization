#!/bin/bash
# Deploy and run the multi_location_forecast_pickle.py script on the remote TAU server
#
# This script will:
# 1. Copy the script and requirements to the server
# 2. Install dependencies on the server
# 3. Run the script in a tmux session (so it continues even if you disconnect)
#
# Usage: ./deploy_pickle_forecast.sh

# ============================================================================
# CONFIGURATION
# ============================================================================
REMOTE_HOST="Shlomo1-pcl.eng.tau.ac.il"
REMOTE_USER="user"
REMOTE_PASSWORD="greek"
REMOTE_DIR="~/Ami"  # Directory on remote server

LOCAL_SCRIPT="../test_files/multi_location_forecast_pickle.py"
LOCAL_REQUIREMENTS="../requirements.txt"
TMUX_SESSION="pickle_forecast"

# ============================================================================
# Main Script
# ============================================================================

echo "=========================================="
echo "Deploying Pickle Forecast Script"
echo "=========================================="
echo "Local script: $LOCAL_SCRIPT"
echo "Server: $REMOTE_USER@$REMOTE_HOST"
echo "Remote directory: $REMOTE_DIR"
echo "TMUX session: $TMUX_SESSION"
echo "=========================================="
echo ""

# Check if local files exist
if [ ! -f "$LOCAL_SCRIPT" ]; then
    echo "Error: $LOCAL_SCRIPT not found"
    exit 1
fi

if [ ! -f "$LOCAL_REQUIREMENTS" ]; then
    echo "Error: $LOCAL_REQUIREMENTS not found"
    exit 1
fi

# Check if VPN is connected (optional check)
if ! ifconfig | grep -A 1 "utun" | grep -q "inet "; then
    echo "Warning: VPN may not be connected."
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

# Step 1: Copy files to server
echo "Step 1: Copying files to server..."
expect << EOF
set timeout 60
set host "$REMOTE_HOST"
set user "$REMOTE_USER"
set password "$REMOTE_PASSWORD"
set remote_dir "$REMOTE_DIR"
set local_script "$LOCAL_SCRIPT"
set local_requirements "$LOCAL_REQUIREMENTS"

spawn scp -o StrictHostKeyChecking=no \$local_script \$local_requirements \$user@\$host:\$remote_dir/

expect {
    "password:" { send "\$password\r" }
    "Password:" { send "\$password\r" }
    timeout { puts "Timeout waiting for password prompt"; exit 1 }
}

expect {
    eof { puts "Files copied successfully" }
    timeout { puts "Timeout"; exit 1 }
}
EOF

if [ $? -ne 0 ]; then
    echo "Failed to copy files"
    exit 1
fi

echo "Files copied successfully"
echo ""

# Step 2: Install dependencies and run in tmux
echo "Step 2: Installing dependencies and starting script in tmux..."
expect << EOF
set timeout 300
set host "$REMOTE_HOST"
set user "$REMOTE_USER"
set password "$REMOTE_PASSWORD"
set remote_dir "$REMOTE_DIR"
set script_name "multi_location_forecast_pickle.py"
set tmux_session "$TMUX_SESSION"

spawn ssh -tt -o StrictHostKeyChecking=no \$user@\$host

expect {
    "password:" { send "\$password\r"; exp_continue }
    "Password:" { send "\$password\r"; exp_continue }
    "\$ " {
        send "cd \$remote_dir\r"
        expect "\$ " {
            # Kill existing tmux session if it exists
            send "tmux kill-session -t \$tmux_session 2>/dev/null; echo done\r"
            expect "\$ "

            # Install dependencies
            send "pip3 install --user -r requirements.txt\r"
            expect {
                "\$ " {
                    puts "Dependencies installed"
                }
                timeout {
                    puts "Warning: Dependency installation may have timed out"
                }
            }

            # Create new tmux session and run script
            send "tmux new-session -d -s \$tmux_session -c \$remote_dir\r"
            expect "\$ " {
                send "tmux send-keys -t \$tmux_session \"python3 \$script_name\" C-m\r"
                expect "\$ " {
                    puts "Script started in tmux session: \$tmux_session"
                    send "exit\r"
                }
            }
        }
    }
    "# " {
        send "cd \$remote_dir\r"
        expect "# " {
            send "tmux kill-session -t \$tmux_session 2>/dev/null; echo done\r"
            expect "# "
            send "pip3 install --user -r requirements.txt\r"
            expect "# " {
                send "tmux new-session -d -s \$tmux_session -c \$remote_dir\r"
                expect "# " {
                    send "tmux send-keys -t \$tmux_session \"python3 \$script_name\" C-m\r"
                    expect "# " {
                        puts "Script started in tmux session: \$tmux_session"
                        send "exit\r"
                    }
                }
            }
        }
    }
    eof
}
EOF

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "The script is now running in tmux session: $TMUX_SESSION"
echo ""
echo "To check status:"
echo "  SSH to server and run: tmux attach -t $TMUX_SESSION"
echo ""
echo "To detach from tmux: Press Ctrl+B, then D"
echo ""
