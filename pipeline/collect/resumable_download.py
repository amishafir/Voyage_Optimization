"""Resumable, chunked SFTP downloader with connection-drop retry.

Downloads a remote file over SFTP in chunks, writing to a local ``.part``
file plus a JSON sidecar (``<local>.download_state.json``) that records the
remote file size *as snapshotted on the first run*. If the connection drops
partway through, re-running the exact same command resumes from the local
.part file's current size instead of starting over -- and keeps targeting
the originally-snapshotted size even if the remote file has grown further
in the meantime (useful when the source is being actively appended to by a
live collector), so the local copy stays byte-for-byte a valid prefix of
the file as it existed at snapshot time.

Note (Windows/Git Bash): if invoked from Git Bash, set MSYS_NO_PATHCONV=1
first -- otherwise MSYS rewrites POSIX-looking remote paths like
/home/user/... into a local Windows path before Python ever sees them.

Usage:
  python resumable_download.py <host> <user> <password> <remote_path> <local_path> \
      [--chunk-mb 4] [--max-retries 30] [--retry-wait 10] [--max-wait 300]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import paramiko


def connect(host: str, user: str, password: str, timeout: float = 20) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=timeout,
                    banner_timeout=30, auth_timeout=30)
    return client


def download(host: str, user: str, password: str, remote_path: str, local_path: str,
             chunk_size: int, max_retries: int, retry_wait: float, max_wait: float) -> None:
    part_path = local_path + ".part"
    state_path = local_path + ".download_state.json"
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)

    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
        if state.get("remote_path") != remote_path:
            raise RuntimeError(
                f"State file {state_path} was recorded for a different remote path "
                f"({state['remote_path']!r}); delete it to start fresh.")
        target_size = state["target_size"]
        print(f"Resuming: target size {target_size:,} bytes (snapshotted earlier)")
    else:
        target_size = None
        for attempt in range(1, max_retries + 1):
            try:
                client = connect(host, user, password)
                sftp = client.open_sftp()
                target_size = sftp.stat(remote_path).st_size
                sftp.close()
                client.close()
                break
            except Exception as e:  # noqa: BLE001
                print(f"Snapshot stat failed (attempt {attempt}/{max_retries}): {e}")
                if attempt >= max_retries:
                    raise
                time.sleep(min(retry_wait * (2 ** (attempt - 1)), max_wait))
        with open(state_path, "w") as f:
            json.dump({"remote_path": remote_path, "target_size": target_size}, f)
        print(f"Snapshotted remote size: {target_size:,} bytes")

    local_size = os.path.getsize(part_path) if os.path.exists(part_path) else 0

    attempt = 0
    while local_size < target_size:
        try:
            client = connect(host, user, password)
            sftp = client.open_sftp()
            remote_file = sftp.open(remote_path, "rb")
            remote_file.set_pipelined(True)
            remote_file.seek(local_size)
            with open(part_path, "ab") as out:
                remaining = target_size - local_size
                while remaining > 0:
                    data = remote_file.read(min(chunk_size, remaining))
                    if not data:
                        break
                    out.write(data)
                    out.flush()
                    os.fsync(out.fileno())
                    local_size += len(data)
                    remaining -= len(data)
                    pct = 100.0 * local_size / target_size
                    print(f"\r  {local_size:,}/{target_size:,} bytes ({pct:5.1f}%)",
                          end="", flush=True)
            remote_file.close()
            sftp.close()
            client.close()
            attempt = 0  # reset backoff after any successful stretch of progress
        except Exception as e:  # noqa: BLE001 - intentionally broad: any failure -> retry
            attempt += 1
            print(f"\nConnection error (attempt {attempt}/{max_retries}): {e}")
            if attempt >= max_retries:
                print("Max retries exceeded. Re-run this exact command later to resume "
                      "from where it left off.")
                sys.exit(1)
            wait = min(retry_wait * (2 ** (attempt - 1)), max_wait)
            print(f"Retrying in {wait:.0f}s...")
            time.sleep(wait)
            local_size = os.path.getsize(part_path) if os.path.exists(part_path) else 0

    print()
    if local_size >= target_size:
        os.replace(part_path, local_path)
        os.remove(state_path)
        print(f"Download complete: {local_path} ({target_size:,} bytes)")
    else:
        print("Download incomplete; re-run to resume.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("host")
    p.add_argument("user")
    p.add_argument("password")
    p.add_argument("remote_path")
    p.add_argument("local_path")
    p.add_argument("--chunk-mb", type=float, default=4.0)
    p.add_argument("--max-retries", type=int, default=30)
    p.add_argument("--retry-wait", type=float, default=10.0,
                    help="initial backoff seconds, doubles each consecutive failure")
    p.add_argument("--max-wait", type=float, default=300.0,
                    help="cap on the exponential backoff")
    args = p.parse_args()
    download(args.host, args.user, args.password, args.remote_path, args.local_path,
              int(args.chunk_mb * 1024 * 1024), args.max_retries, args.retry_wait, args.max_wait)


if __name__ == "__main__":
    main()
