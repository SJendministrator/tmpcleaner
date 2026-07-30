import os
import tempfile
from pathlib import Path

LOCALAPPDATA = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")

PROTECTED_EXTS = {".exe", ".dll", ".sys", ".bat", ".msi", ".com", ".cmd", ".ps1", ".vbs", ".ocx", ".drv"}
PREVIEW_LIMIT = 300

# 화이트리스트 타깃 정의
TARGETS = [
    ("윈도우 임시 파일", Path(tempfile.gettempdir())),
    ("시스템 임시 파일", Path(r"C:\Windows\Temp")),
    ("윈도우 업데이트 캐시", Path(r"C:\Windows\SoftwareDistribution\Download")),
    ("구글 크롬 캐시", Path(LOCALAPPDATA) / "Google" / "Chrome" / "User Data" / "Default" / "Cache"),
    ("마이크로소프트 엣지 캐시", Path(LOCALAPPDATA) / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache"),
    ("파이어폭스 캐시", Path(LOCALAPPDATA) / "Mozilla" / "Firefox" / "Profiles"),
    ("DirectX 셰이더 캐시", Path(LOCALAPPDATA) / "D3DSCache"),
    ("썸네일 캐시", Path(LOCALAPPDATA) / "Microsoft" / "Windows" / "Explorer"),
    ("다운로드 폴더 ⚠️", Path.home() / "Downloads"),
]

ALLOWED_ROOTS = {str(p.resolve()).lower() for _, p in TARGETS}

def is_path_allowed(p: Path) -> bool:
    try:
        rp = str(p.resolve()).lower()
    except Exception:
        rp = str(p.absolute()).lower()
    for root in ALLOWED_ROOTS:
        if rp.startswith(root + os.sep) or rp == root:
            return True
    return False

def is_deletable_file(p: Path, include_downloads: bool) -> bool:
    if not p.exists() or not p.is_file():
        return False
    if p.suffix.lower() in PROTECTED_EXTS:
        return False
    if not is_path_allowed(p):
        return False
    if "mozilla\\firefox\\profiles" in str(p).lower():
        if "cache2" not in str(p).lower():
            return False
    if "downloads" in str(p).lower() and not include_downloads:
        return False
    return True