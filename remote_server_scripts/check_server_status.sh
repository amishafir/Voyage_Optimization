#!/bin/bash
# Check what's running on the remote TAU server
# Usage: ./check_server_status.sh

REMOTE_HOST="Shlomo1-pcl.eng.tau.ac.il"
REMOTE_USER="user"
REMOTE_PASSWORD="greek"
REMOTE_DIR="~/Ami"

echo "=========================================="
echo "Checking Server Status"
echo "Server: $REMOTE_USER@$REMOTE_HOST"
echo "=========================================="
echo ""

expect << EOF
set timeout 30
set host "$REMOTE_HOST"
set user "$REMOTE_USER"
set password "$REMOTE_PASSWORD"
set remote_dir "$REMOTE_DIR"

spawn ssh -o StrictHostKeyChecking=no \$user@\$host

expect {
    "password:" { 
        send "\$password\r"
        exp_continue
    }
    "Password:" { 
        send "\$password\r"
        exp_continue
    }
    "$ " {
        send "cd \$remote_dir\r"
        expect "$ " {
            send_user "\n=== Active tmux Sessions ===\n"
            send "tmux list-sessions 2>/dev/null || echo 'No tmux sessions found'\r"
            expect "$ " {
                send_user "\n=== Running Python Processes ===\n"
                send "ps aux | grep -E 'python[3]?.*\.py' | grep -v grep || echo 'No Python processes found'\r"
                expect "$ " {
                    send_user "\n=== Recent Files in ~/Ami ===\n"
                    send "ls -lth \$remote_dir 2>/dev/null | head -20\r"
                    expect "$ " {
                        send_user "\n=== Excel Output Files ===\n"
                        send "ls -lh \$remote_dir/*.xlsx 2>/dev/null || echo 'No Excel files found'\r"
                        expect "$ " {
                            send "exit\r"
                        }
                    }
                }
            }
        }
    }
    "# " {
        send "cd \$remote_dir\r"
        expect "# " {
            send_user "\n=== Active tmux Sessions ===\n"
            send "tmux list-sessions 2>/dev/null || echo 'No tmux sessions found'\r"
            expect "# " {
                send_user "\n=== Running Python Processes ===\n"
                send "ps aux | grep -E 'python[3]?.*\.py' | grep -v grep || echo 'No Python processes found'\r"
                expect "# " {
                    send_user "\n=== Recent Files in ~/Ami ===\n"
                    send "ls -lth \$remote_dir 2>/dev/null | head -20\r"
                    expect "# " {
                        send_user "\n=== Excel Output Files ===\n"
                        send "ls -lh \$remote_dir/*.xlsx 2>/dev/null || echo 'No Excel files found'\r"
                        expect "# " {
                            send "exit\r"
                        }
                    }
                }
            }
        }
    }
    timeout {
        send_user "Connection timeout\n"
        exit 1
    }
    eof
}

expect eof
EOF

echo ""
echo "=========================================="
echo "Status check complete"
echo "=========================================="
