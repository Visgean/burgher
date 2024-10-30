import hashlib
import os
from pathlib import Path

IGNORE_FILES = [
    "__pycache__",
    ".git",
    ".pyc",
]


def ignore_path(path: Path):
    spath = str(path)
    for p in IGNORE_FILES:
        if p in spath:
            return True
    return False


def recursive_max_stat(paths: list[Path], initial_hash=""):
    if not paths:
        return ""

    files = []
    prev_hash = initial_hash

    for p in paths:
        if p.is_dir():
            files.extend(list(p.rglob("**/*")))
        else:
            files.append(p)

    for path in sorted(files):
        if ignore_path(path):
            continue

        stat = os.stat(path)
        keys = f"{stat.st_mtime}, {stat.st_ctime}, {stat.st_size}, {prev_hash}"
        h = hashlib.new("sha256")
        h.update(keys.encode())
        prev_hash = h.hexdigest()

    return prev_hash
