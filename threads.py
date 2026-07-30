import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtCore import QThread, pyqtSignal
from send2trash import send2trash
from core import is_deletable_file

class CleanThread(QThread):
    progress_update = pyqtSignal(int, int, int)
    finished = pyqtSignal(int, int)

    def __init__(self, files: list, use_trash: bool):
        super().__init__()
        self.files = files
        self.use_trash = use_trash
        self.deleted_count = 0
        self.bytes_freed = 0
        self.total_count = len(files)

    def _delete_single_item(self, item):
        fp, size = item
        try:
            if self.use_trash:
                send2trash(str(fp))
            else:
                fp.unlink(missing_ok=True)
            return True, size
        except Exception:
            return False, 0

    def run(self):
        max_workers = min(16, os.cpu_count() * 2 or 4)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = executor.map(self._delete_single_item, self.files)
            for i, (success, size) in enumerate(results):
                if success:
                    self.deleted_count += 1
                    self.bytes_freed += size
                current_count = i + 1
                percentage = int((current_count / self.total_count) * 100)
                if current_count % 100 == 0 or current_count == self.total_count:
                    self.progress_update.emit(current_count, self.total_count, percentage)
        self.finished.emit(self.deleted_count, self.bytes_freed)


class ScanThread(QThread):
    finished = pyqtSignal(list, int, int)
    progress_update = pyqtSignal(str, int, int)

    def __init__(self, targets: list, include_downloads: bool):
        super().__init__()
        self.targets = targets
        self.include_downloads = include_downloads

    def run(self):
        total_bytes = 0
        all_files = []
        num_targets = len(self.targets)
        for i, (name, path) in enumerate(self.targets):
            if not path.exists():
                continue
            self.progress_update.emit(f"스캔 중: {name}", i + 1, num_targets)
            for root, _, filenames in os.walk(path):
                for fname in filenames:
                    fp = Path(root) / fname
                    if is_deletable_file(fp, self.include_downloads):
                        try:
                            size = fp.stat().st_size
                            total_bytes += size
                            all_files.append((fp, size))
                        except Exception:
                            pass
        self.finished.emit(all_files, total_bytes, len(all_files))