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

## Other Servers

| Server | Username | Password | Notes |
|--------|----------|----------|-------|
| `edison-pc.eng.tau.ac.il` | `user` | `greek` (same as Shlomo1) | Live weather collector since 2026-10-14: `~/Ami/pipeline_v2`, tmux session `collector_v2` (see CLAUDE.md, "Deployment on edison"). The old `collect_all` is stopped; do not restart it. Verified working 2026-10-19. |
| `Shlomo2-pcl.eng.tau.ac.il` | `user` | `greek` (same as Shlomo1/Edison) | Data-collection host, runs its own independent `collect_all` copy. Verified working 2026-08-17 — a separate `amishafir` account also exists but its password is unconfirmed; don't bother with it, `user`/`greek` works fine. |
| `talraviv-pcl.eng.tau.ac.il` | `ami` | `greek` (SSH key preferred, below) | Ubuntu 24.04, 12 cores, 31 GB RAM. Collects Routes 3-6 since 2026-10-19 (see CLAUDE.md, "Deployment on talraviv-pcl"): `~/voyage_collector`, venv `~/collector-venv`, tmux `collector_volatile`. Own public IP, so its own Open-Meteo quota. `/tsl-disk` (lab NAS) mounted; `/data` is a spare 1.8 TB disk. Server clock is Israel time. Verified working 2026-10-19. |

### Key login to talraviv-pcl

Ami's Mac has a key installed on talraviv-pcl and an alias in `~/.ssh/config`:

```
Host talraviv
  HostName talraviv-pcl.eng.tau.ac.il
  User ami
  IdentityFile ~/.ssh/id_ed25519_claude
  IdentitiesOnly yes
```

So `ssh talraviv`, `scp FILE talraviv:` and `rsync ... talraviv:` need no password. From another machine, install a key once with `ssh-copy-id -i KEY.pub ami@talraviv-pcl.eng.tau.ac.il`.

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
- **"Permission denied"**: Password is `greek` for the `user` account on Shlomo1/Shlomo2/Edison, and for `ami` on talraviv-pcl.
- **"expect: command not found"**: `brew install expect`
- **"Module not found" on server**: `ssh user@server "pip3 install --user package_name"`

## Deprecated

The `remote_server_scripts/` folder is deprecated. Use the `remote-server` agent or this skill reference instead.
