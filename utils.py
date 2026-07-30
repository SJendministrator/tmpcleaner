import os
import ctypes
from pathlib import Path

def human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for u in units:
        if size < 1024.0:
            return f"{size:.2f} {u}"
        size /= 1024.0
    return f"{size:.2f} PB"

def get_username() -> str:
    try:
        return os.getlogin()
    except Exception:
        return Path.home().name

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False