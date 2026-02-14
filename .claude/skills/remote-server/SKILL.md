# Remote Server Reference

## Server Details

| Setting | Value |
|---------|-------|
| VPN Portal | `vpn.tau.ac.il` |
| VPN Client | GlobalProtect (`/Applications/GlobalProtect.app`) |
| Server | `Shlomo1-pcl.eng.tau.ac.il` |
| Username | `user` |
| Password | `greek` |
| Working Directory | `~/Ami` |

## Quick Commands

### Check VPN
```bash
ifconfig | grep -A 1 "utun" | grep "inet "
```

### SSH to server
```bash
ssh user@Shlomo1-pcl.eng.tau.ac.il
# Password: greek
```

### Upload file
```bash
scp LOCAL_FILE user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/
```

### Download file
```bash
scp user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/REMOTE_FILE ./
```

### Run script remotely
```bash
ssh user@Shlomo1-pcl.eng.tau.ac.il "cd ~/Ami && python3 script.py"
```

### tmux sessions
```bash
# List sessions
ssh user@Shlomo1-pcl.eng.tau.ac.il "tmux list-sessions"

# Attach to session (interactive)
ssh -t user@Shlomo1-pcl.eng.tau.ac.il "tmux attach -t SESSION_NAME"

# Create new session with script
ssh user@Shlomo1-pcl.eng.tau.ac.il "tmux new-session -d -s SESSION_NAME 'cd ~/Ami && python3 script.py'"

# Check session output
ssh user@Shlomo1-pcl.eng.tau.ac.il "tmux capture-pane -t SESSION_NAME -p -S -30"

# Detach: Ctrl+B, then D
```

## Common tmux Session Names

| Session | Script | Purpose |
|---------|--------|---------|
| `pickle_forecast` | `multi_location_forecast_pickle.py` | Weather data collection (pickle) |
| `wave_forecast` | `current_wave_forecasting.py` | Wave/current forecasting |
| `mateo` | (general) | General-purpose session |

## Common Workflows

### Deploy and run a script in tmux
```bash
scp script.py requirements.txt user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/
ssh user@Shlomo1-pcl.eng.tau.ac.il "cd ~/Ami && pip3 install --user -r requirements.txt && tmux new-session -d -s my_session 'python3 script.py'"
```

### Check job status and download results
```bash
ssh user@Shlomo1-pcl.eng.tau.ac.il "tmux capture-pane -t my_session -p -S -20"
scp user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/output_file ./
```

## Troubleshooting

- **"Connection refused"**: Check VPN is connected (`ifconfig | grep utun`)
- **"Permission denied"**: Password is `greek`
- **"expect: command not found"**: `brew install expect`
- **"Module not found" on server**: `ssh user@server "pip3 install --user package_name"`

## Deprecated

The `remote_server_scripts/` folder is deprecated. Use the `remote-server` agent or this skill reference instead.
