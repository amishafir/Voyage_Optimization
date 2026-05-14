#!/bin/bash
# Check the status of the wave forecasting script running on the server
# Usage: ./check_forecasting.sh

REMOTE_HOST="Shlomo1-pcl.eng.tau.ac.il"
REMOTE_USER="user"
REMOTE_PASSWORD="greek"
REMOTE_DIR="~/Ami"
TMUX_SESSION="wave_forecast"

echo "=========================================="
echo "Checking Wave Forecasting Script Status"
echo "=========================================="
echo ""

expect << EOF
set timeout 30
set host "$REMOTE_HOST"
set user "$REMOTE_USER"
set password "$REMOTE_PASSWORD"
set remote_dir "$REMOTE_DIR"
set tmux_session "$TMUX_SESSION"

spawn ssh -o StrictHostKeyChecking=no \$user@\$host

expect {
    "password:" { send "\$password\r"; exp_continue }
    "Password:" { send "\$password\r"; exp_continue }
    "\$ " {
        send "cd \$remote_dir\r"
        expect "\$ " {
            # Check if tmux session exists
            send "tmux has-session -t \$tmux_session 2>/dev/null && echo 'Session exists' || echo 'Session not found'\r"
            expect "\$ " {
                # Show last few lines of output
                send "tmux capture-pane -t \$tmux_session -p -S -20 2>/dev/null || echo 'Cannot capture output'\r"
                expect "\$ " {
                    # Check if output file exists
                    send "ls -lh current_wave_forecast.xlsx 2>/dev/null || echo 'Output file not found yet'\r"
                    expect "\$ " {
                        send "exit\r"
                    }
                }
            }
        }
    }
    "# " {
        send "cd \$remote_dir\r"
        expect "# " {
            send "tmux has-session -t \$tmux_session 2>/dev/null && echo 'Session exists' || echo 'Session not found'\r"
            expect "# " {
                send "tmux capture-pane -t \$tmux_session -p -S -20 2>/dev/null || echo 'Cannot capture output'\r"
                expect "# " {
                    send "ls -lh current_wave_forecast.xlsx 2>/dev/null || echo 'Output file not found yet'\r"
                    expect "# " {
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
echo "To attach to the session:"
echo "  ssh $REMOTE_USER@$REMOTE_HOST"
echo "  tmux attach -t $TMUX_SESSION"
echo "=========================================="
