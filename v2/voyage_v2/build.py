"""
Compile the C++ core (v2/cpp) into a shared library, with the system C++
compiler and no other tools, whenever a source is newer than the library.

    python3 -m voyage_v2.build          # force a rebuild
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

CPP = Path(__file__).resolve().parents[1] / "cpp"
LIBRARY = CPP / "build" / ("libvoyage_v2.dylib" if sys.platform == "darwin" else "libvoyage_v2.so")


def _sources():
    return sorted((CPP / "src").glob("*.cpp")), sorted((CPP / "include").rglob("*.h*"))


def is_stale() -> bool:
    if not LIBRARY.exists():
        return True
    built = LIBRARY.stat().st_mtime
    sources, headers = _sources()
    return any(p.stat().st_mtime > built for p in sources + headers)


def build() -> Path:
    sources, _ = _sources()
    LIBRARY.parent.mkdir(parents=True, exist_ok=True)
    tmp = LIBRARY.with_name(f"{LIBRARY.name}.{os.getpid()}.tmp")
    cmd = [os.environ.get("CXX", "c++"), "-std=c++17", "-O3", "-fPIC", "-shared",
           "-Wall", "-Wextra", f"-I{CPP / 'include'}", *map(str, sources), "-o", str(tmp)]
    print("compiling the C++ core:", " ".join(cmd[:6]), "...", file=sys.stderr)
    subprocess.run(cmd, check=True)
    os.replace(tmp, LIBRARY)        # atomic, so concurrent builds cannot leave a half-written library
    return LIBRARY


def ensure_library() -> Path:
    return build() if is_stale() else LIBRARY


if __name__ == "__main__":
    print(build())
