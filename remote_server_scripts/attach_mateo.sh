#!/bin/bash
# Attach to mateo session on TAU server
# Usage: ./attach_mateo.sh
# Note: This requires an interactive terminal

echo "=========================================="
echo "Attaching to mateo session"
echo "Server: Shlomo1-pcl.eng.tau.ac.il"
echo "=========================================="
echo ""
echo "You will be prompted for password: greek"
echo ""

# Use expect to handle password and attach to session
expect << 'EOF'
set timeout 10
set host "Shlomo1-pcl.eng.tau.ac.il"
set user "user"
set password "greek"

# Force pseudo-terminal allocation
spawn ssh -o StrictHostKeyChecking=no -tt $user@$host "tmux attach -t mateo || tmux new -s mateo"

expect {
    "password:" {
        send "$password\r"
        exp_continue
    }
    "Password:" {
        send "$password\r"
        exp_continue
    }
    timeout {
        send_user "Connection timeout\n"
        exit 1
    }
}

# Pass control to user for interactive session
interact {
    \003 {
        send "\003"
        expect eof
        exit
    }
}
EOF
