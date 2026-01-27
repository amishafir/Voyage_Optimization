# Remote Server Scripts - Complete Guide

This folder contains all scripts and documentation needed to run Python files on the remote TAU server.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Step-by-Step Instructions](#step-by-step-instructions)
4. [Scripts Overview](#scripts-overview)
5. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

1. **GlobalProtect VPN Client**
   - Must be installed on your Mac
   - Usually located at: `/Applications/GlobalProtect.app`

2. **SSH Client**
   - Built into macOS/Unix systems
   - No installation needed

3. **Expect** (for automated password entry)
   - Usually pre-installed on macOS
   - Check with: `which expect`
   - If missing: `brew install expect`

### Required Credentials

- **VPN Portal:** `vpn.tau.ac.il`
- **Username:** `user`
- **Password:** `greek`
- **Remote Server:** `Shlomo1-pcl.eng.tau.ac.il`
- **Remote Directory:** `~/Ami`

---

## Quick Start

### Run a Python file on the remote server:

```bash
cd remote_server_scripts
./run_remote_python.sh your_script.py
```

That's it! The script will:
1. Check VPN connection
2. Connect to the server
3. Run your Python file
4. Show the output

---

## Step-by-Step Instructions

### Step 1: Connect to VPN

**Option A: Using the script (Recommended)**
```bash
cd remote_server_scripts
./connect_vpn.sh
```

**Option B: Manual connection**
1. Open GlobalProtect application
2. Enter portal: `vpn.tau.ac.il`
3. Username: `user`
4. Password: `greek`
5. Click "Connect"

**Verify VPN connection:**
```bash
ifconfig | grep utun
```
You should see VPN interface(s) listed.

### Step 2: Run Python File on Remote Server

**Method 1: Using the automated script (Easiest)**

```bash
cd remote_server_scripts

# Run with default file (main.py)
./run_remote_python.sh

# Or specify a file
./run_remote_python.sh marine_weather.py
```

**Method 2: Manual SSH connection**

```bash
cd remote_server_scripts
./connect_tau_server.sh

# Once connected, run:
cd ~/Ami
python3 your_script.py
exit
```

**Method 3: Direct SSH command**

```bash
ssh user@Shlomo1-pcl.eng.tau.ac.il
# Enter password: greek
cd ~/Ami
python3 your_script.py
exit
```

### Step 3: Access tmux Session (Optional)

If you need to attach to an existing tmux session:

```bash
cd remote_server_scripts
./attach_mateo.sh
```

---

## Scripts Overview

### 1. `run_remote_python.sh` ⭐ Main Script

**Purpose:** Run any Python file on the remote server automatically.

**Usage:**
```bash
./run_remote_python.sh [python_filename]
```

**Examples:**
```bash
# Run main.py (default)
./run_remote_python.sh

# Run specific file
./run_remote_python.sh marine_weather.py
./run_remote_python.sh data_processor.py
```

**Configuration:**
Edit the script to change default file:
```bash
PYTHON_FILE="main.py"  # Change this line
```

**What it does:**
- Checks VPN connection
- Connects to remote server
- Navigates to `~/Ami` directory
- Runs the Python file
- Displays output
- Exits automatically

### 2. `connect_vpn.sh`

**Purpose:** Connect to GlobalProtect VPN.

**Usage:**
```bash
./connect_vpn.sh
```

**What it does:**
- Opens GlobalProtect application
- Waits for you to enter credentials
- Verifies connection status

### 3. `connect_tau_server.sh`

**Purpose:** Connect to remote server interactively.

**Usage:**
```bash
./connect_tau_server.sh
```

**What it does:**
- Checks VPN connection
- Connects to server via SSH
- Gives you an interactive shell
- You can run commands manually

### 4. `attach_mateo.sh`

**Purpose:** Attach to tmux session named "mateo" on remote server.

**Usage:**
```bash
./attach_mateo.sh
```

**What it does:**
- Connects to remote server
- Attaches to or creates "mateo" tmux session
- Gives you interactive access to the session

---

## File Structure

```
remote_server_scripts/
├── README.md                  # This file
├── run_remote_python.sh       # Main script to run Python files
├── connect_vpn.sh             # VPN connection script
├── connect_tau_server.sh      # Interactive server connection
└── attach_mateo.sh            # Attach to tmux session
```

---

## Common Workflows

### Workflow 1: Run a Python script once

```bash
cd remote_server_scripts
./run_remote_python.sh my_script.py
```

### Workflow 2: Upload and run a new script

```bash
# 1. Upload your script to server
scp my_script.py user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/

# 2. Run it
cd remote_server_scripts
./run_remote_python.sh my_script.py
```

### Workflow 3: Work in tmux session

```bash
# 1. Connect to VPN
cd remote_server_scripts
./connect_vpn.sh

# 2. Attach to mateo session
./attach_mateo.sh

# 3. Inside the session:
cd ~/Ami
python3 my_script.py
# Work interactively...
# Press Ctrl+B then D to detach
```

### Workflow 4: Interactive debugging

```bash
# 1. Connect to server interactively
cd remote_server_scripts
./connect_tau_server.sh

# 2. Navigate and run
cd ~/Ami
python3 -i my_script.py  # Interactive mode
# Debug interactively...
exit
```

---

## Troubleshooting

### Problem: "VPN not connected" warning

**Solution:**
```bash
./connect_vpn.sh
# Or connect manually via GlobalProtect app
```

**Verify:**
```bash
ifconfig | grep utun
```

### Problem: "Permission denied" when running script

**Solution:**
```bash
chmod +x run_remote_python.sh
chmod +x connect_vpn.sh
chmod +x connect_tau_server.sh
chmod +x attach_mateo.sh
```

### Problem: "expect: command not found"

**Solution:**
```bash
# Install expect
brew install expect

# Or use manual SSH connection instead
ssh user@Shlomo1-pcl.eng.tau.ac.il
```

### Problem: "Connection refused" or "Timeout"

**Possible causes:**
1. VPN not connected
2. Network issues
3. Server is down

**Solutions:**
1. Check VPN: `ifconfig | grep utun`
2. Try connecting manually: `ssh user@Shlomo1-pcl.eng.tau.ac.il`
3. Wait a few minutes and try again

### Problem: "Module not found" on remote server

**Solution:**
Connect to server and install packages:
```bash
./connect_tau_server.sh
# Then inside:
pip3 install --user package_name
```

### Problem: Script runs but no output

**Possible causes:**
1. Python file has errors
2. Output is being buffered
3. Script is waiting for input

**Solutions:**
1. Check Python file for syntax errors
2. Add `-u` flag: `python3 -u script.py`
3. Check if script needs input

### Problem: Can't find Python file on server

**Solution:**
1. Check file exists: `ls ~/Ami/*.py`
2. Verify correct filename (case-sensitive)
3. Upload file if missing:
   ```bash
   scp my_script.py user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/
   ```

---

## Configuration

### Change Default Python File

Edit `run_remote_python.sh`:
```bash
PYTHON_FILE="your_default_file.py"  # Line 12
```

### Change Server Settings

Edit `run_remote_python.sh`:
```bash
REMOTE_HOST="Shlomo1-pcl.eng.tau.ac.il"  # Line 15
REMOTE_USER="user"                         # Line 16
REMOTE_PASSWORD="greek"                    # Line 17
REMOTE_DIR="~/Ami"                         # Line 18
```

### Change VPN Portal

Edit `connect_vpn.sh`:
```bash
# Update portal address in the script
```

---

## Security Notes

⚠️ **Important Security Considerations:**

1. **Password in Scripts:** The password is stored in plain text in the scripts. 
   - Only use on trusted machines
   - Don't commit to public repositories
   - Consider using SSH keys instead

2. **SSH Keys (Recommended):**
   ```bash
   # Generate SSH key
   ssh-keygen -t rsa -b 4096
   
   # Copy to server
   ssh-copy-id user@Shlomo1-pcl.eng.tau.ac.il
   
   # Then you can remove password from scripts
   ```

3. **File Permissions:**
   ```bash
   chmod 600 *.sh  # Restrict access to scripts
   ```

---

## Examples

### Example 1: Run a data processing script

```bash
cd remote_server_scripts
./run_remote_python.sh data_processor.py
```

### Example 2: Run multiple scripts

```bash
cd remote_server_scripts
./run_remote_python.sh script1.py
./run_remote_python.sh script2.py
./run_remote_python.sh script3.py
```

### Example 3: Long-running script in tmux

```bash
# 1. Connect to VPN
./connect_vpn.sh

# 2. Attach to session
./attach_mateo.sh

# 3. Run script (will continue even if you disconnect)
cd ~/Ami
nohup python3 long_script.py > output.log 2>&1 &

# 4. Detach: Ctrl+B then D
# 5. Reattach later to check progress
```

---

## Additional Resources

- **Server:** Shlomo1-pcl.eng.tau.ac.il
- **VPN Portal:** vpn.tau.ac.il
- **Remote Directory:** ~/Ami
- **Python Version on Server:** Check with `python3 --version`

---

## Quick Reference

| Task | Command |
|------|---------|
| Run Python file | `./run_remote_python.sh file.py` |
| Connect VPN | `./connect_vpn.sh` |
| Connect to server | `./connect_tau_server.sh` |
| Attach to tmux | `./attach_mateo.sh` |
| Check VPN | `ifconfig \| grep utun` |
| Upload file | `scp file.py user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/` |

---

## Support

If you encounter issues:
1. Check the [Troubleshooting](#troubleshooting) section
2. Verify VPN connection
3. Test manual SSH connection
4. Check server status

---

**Last Updated:** January 2026
