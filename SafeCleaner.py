# SafeCleaner - Storage Sense-style safe cleaner
# Author: Gemini, based on ChatGPT's code
# Requirements: pip install pyqt5 send2trash
# Build to exe: pyinstaller --onefile --noconsole SafeCleaner.py

import os
import sys
import shutil
import tempfile
import ctypes
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
    QTextEdit, QMessageBox, QLabel, QDialog, QListWidget, QListWidgetItem,
    QProgressBar, QSizePolicy
)
from send2trash import send2trash

# -----------------------------
# Safety settings
# -----------------------------
PROTECTED_EXTS = {".exe", ".dll", ".sys", ".bat", ".msi", ".com", ".cmd", ".ps1", ".vbs", ".ocx", ".drv"}
PREVIEW_LIMIT = 300

def human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for u in units:
        if size < 1024.0:
            return f"{size:.2f} {u}"
        size /= 1024.0
    return f"{size:.2f} PB"

def get_username():
    try:
        return os.getlogin()
    except Exception:
        return Path.home().name

USER = get_username()
LOCALAPPDATA = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")

# -----------------------------
# Whitelisted targets only
# -----------------------------
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


# --- 멀티스레딩 고속 삭제 스레드 ---
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


# --- 멀티스레딩 스캔 스레드 ---
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


# --- 미리보기 다이얼로그 (다크 모드 커스텀) ---
class PreviewDialog(QDialog):
    def __init__(self, title: str, items: list, total_count: int):
        super().__init__()
        flags = self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        self.setWindowFlags(flags)
        self.setWindowTitle(f"미리보기: {title}")
        self.resize(720, 480)
        
        # 다이얼로그 전용 스타일시트 상속
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; }
            QLabel { color: #e3e3e3; font-family: "Segoe UI", "맑은 고딕"; font-size: 13px; font-weight: 500; }
            QListWidget { background-color: #252526; border: 1px solid #3e3e42; border-radius: 6px; color: #cccccc; padding: 5px; font-family: "Consolas", "Segoe UI"; font-size: 12px; }
            QPushButton { background-color: #2d2d2d; border: 1px solid #454545; border-radius: 5px; color: #ffffff; padding: 6px 16px; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background-color: #3d3d3d; border: 1px solid #0078d4; }
        """)

        layout = QVBoxLayout()
        if len(items) < total_count:
            label_text = f"💡 총 {total_count}개 파일 중 상위 {len(items)}개만 미리 표시합니다. (예상 절약 용량: {human_size(sum(sz for _, sz in items))})"
        else:
            label_text = f"📂 발견된 항목 수: {total_count}개  |  총 용량: {human_size(sum(sz for _, sz in items))}"
        
        layout.addWidget(QLabel(label_text))
        
        self.listw = QListWidget()
        for fp, sz in items:
            item = QListWidgetItem(f"   {fp}   ({human_size(sz)})")
            self.listw.addItem(item)
        layout.addWidget(self.listw)

        btns = QHBoxLayout()
        ok = QPushButton("닫기")
        ok.clicked.connect(self.accept)
        btns.addStretch(1)
        btns.addWidget(ok)
        layout.addLayout(btns)
        self.setLayout(layout)


# --- 메인 애플리케이션 (Fluent 다크 테마) ---
class CleanerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SafeCleaner (Storage Sense 스타일)")
        self.setGeometry(500, 250, 720, 600)
        
        self.all_scanned_files = []
        self.all_scanned_bytes = 0

        # 고품격 다크 모드 QSS 스타일시트 적용
        self.setStyleSheet("""
            QWidget {
                background-color: #1c1c1c;
                color: #e3e3e3;
                font-family: "Segoe UI", "맑은 고딕";
                font-size: 13px;
            }
            QLabel#headerLabel {
                font-size: 16px;
                font-weight: bold;
                color: #ffffff;
                margin-top: 5px;
                margin-bottom: 10px;
            }
            QCheckBox {
                spacing: 10px;
                padding: 6px 4px;
                color: #cccccc;
            }
            QCheckBox:hover {
                color: #ffffff;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border: 1px solid #00a2ed;
            }
            QPushButton {
                background-color: #2d2d2d;
                border: 1px solid #454545;
                border-radius: 6px;
                color: #ffffff;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #383838;
                border: 1px solid #0078d4;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
            QProgressBar {
                border: 1px solid #454545;
                border-radius: 6px;
                text-align: center;
                background-color: #252526;
                color: #ffffff;
                font-weight: bold;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 5px;
            }
            QTextEdit {
                background-color: #252526;
                border: 1px solid #2d2d2d;
                border-radius: 6px;
                color: #a6a6a6;
                padding: 8px;
                font-family: "Consolas", "나눔고딕코딩";
                font-size: 12px;
            }
        """)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(8)

        self.header = QLabel("삭제해도 안전한 시스템 캐시 및 브라우저 임시 파일만 정리합니다.")
        self.header.setObjectName("headerLabel")
        self.layout.addWidget(self.header)

        self.trash_cb = QCheckBox("🔄 삭제 시 휴지통으로 이동 (안전한 복구 권장)")
        self.trash_cb.setChecked(True)
        self.layout.addWidget(self.trash_cb)

        # 구분선 역할의 빈 마진
        self.layout.addSpacing(5)

        self.checkboxes = []
        for name, path in TARGETS:
            cb = QCheckBox(name)
            cb.setChecked(False if "다운로드" in name else True)
            self.layout.addWidget(cb)
            self.checkboxes.append((name, path, cb))
            
        self.layout.addSpacing(10)

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton("🔍 선택 항목 스캔")
        self.scan_btn.clicked.connect(self.scan_and_preview)
        self.clean_btn = QPushButton("🧹 정리 실행")
        self.clean_btn.clicked.connect(self.clean_selected)
        btn_row.addWidget(self.scan_btn)
        btn_row.addWidget(self.clean_btn)
        self.layout.addLayout(btn_row)

        self.progressBar = QProgressBar(self)
        self.progressBar.setTextVisible(True)
        self.progressBar.hide()
        self.layout.addWidget(self.progressBar)
        
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.layout.addWidget(QLabel("📝 작업 로그:"))
        self.layout.addWidget(self.log)

        self.setLayout(self.layout)

    def scan_and_preview(self):
        selected = self._selected_targets()
        if not selected:
            QMessageBox.information(self, "안내", "스캔할 항목을 선택하세요.")
            return

        include_downloads = any("다운로드" in name for name, _ in selected)
        if include_downloads:
            reply = QMessageBox.warning(
                self, "⚠️ 경고",
                "다운로드 폴더에는 중요한 파일이 포함되어 있을 수 있습니다.\n정말 스캔 및 정리 대상에 포함하겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                selected = [(n, p) for (n, p) in selected if "다운로드" not in n]

        self.all_scanned_files = []
        self.all_scanned_bytes = 0
        self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔎 캐시 파일 정밀 스캔 시작...")
        
        self.progressBar.setRange(0, 0)
        self.progressBar.setFormat("파일 인덱스 카탈로그 구성 중...")
        self.progressBar.show()
        self._set_buttons_enabled(False)

        self.scan_thread = ScanThread(selected, include_downloads)
        self.scan_thread.progress_update.connect(self.update_scan_progress)
        self.scan_thread.finished.connect(self.show_preview_dialog)
        self.scan_thread.start()

    def update_scan_progress(self, current_task_text, current_target_index, total_targets):
        self.progressBar.setRange(0, total_targets)
        self.progressBar.setValue(current_target_index)
        self.progressBar.setFormat(f"[{current_target_index}/{total_targets}] {current_task_text}")

    def show_preview_dialog(self, all_files, total_bytes, total_count):
        self.progressBar.hide()
        self._set_buttons_enabled(True)
        self.all_scanned_bytes = total_bytes
        self.all_scanned_files = all_files
        
        self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 스캔 완료: 총 {total_count}개 항목 검출 (예상 확보 공간: {human_size(total_bytes)})")

        if not all_files:
            QMessageBox.information(self, "결과", "정리할 캐시 파일이 존재하지 않습니다. 시스템이 깨끗합니다!")
            return

        preview_items = all_files[:PREVIEW_LIMIT]
        dlg = PreviewDialog("검출 결과 목록", preview_items, total_count)
        dlg.exec_()
    
    def _selected_targets(self):
        sel = []
        for name, path, cb in self.checkboxes:
            if cb.isChecked():
                sel.append((name, path))
        return sel

    def clean_selected(self):
        if not self.all_scanned_files:
            QMessageBox.information(self, "안내", "먼저 '선택 항목 스캔'을 완료해 주세요.")
            return

        confirm = QMessageBox.question(
            self, "최종 정리 확인",
            f"선택한 장치에서 총 {human_size(self.all_scanned_bytes)}의 데이터를 제거합니다.\n진행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm == QMessageBox.No:
            return

        use_trash = self.trash_cb.isChecked()
        self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 멀티스레드 삭제 쿼리 기동...")
        
        self.progressBar.setRange(0, len(self.all_scanned_files))
        self.progressBar.setValue(0)
        self.progressBar.setFormat("작업 스케줄러 할당 중...")
        self.progressBar.show()
        self._set_buttons_enabled(False)

        self.clean_thread = CleanThread(self.all_scanned_files, use_trash)
        self.clean_thread.progress_update.connect(self.update_clean_progress)
        self.clean_thread.finished.connect(self.on_clean_finished)
        self.clean_thread.start()

    def update_clean_progress(self, current_count, total_count, percentage):
        self.progressBar.setValue(current_count)
        self.progressBar.setFormat(f"고속 삭제 진행 중: {current_count}/{total_count} 파일 ({percentage}%)")

    def on_clean_finished(self, deleted, freed):
        self.progressBar.hide()
        self._set_buttons_enabled(True)
        use_trash = self.trash_cb.isChecked()

        try:
            log_path = Path.home() / "SafeCleaner.log"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                        f"deleted={deleted}, freed={human_size(freed)}, trash={use_trash}\n")
            self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 마스터 로그 로컬 저장 완료: {log_path}")
        except Exception:
            pass

        self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🌟 최적화 완료: {deleted}개 소거 완료, {human_size(freed)} 디스크 공간 확보 완료!")
        
        self.all_scanned_files = []
        self.all_scanned_bytes = 0
        QMessageBox.information(self, "완료", f"성공적으로 최적화되었습니다.\n소거된 파일: {deleted}개\n확보된 용량: {human_size(freed)}")

    def _set_buttons_enabled(self, enabled: bool):
        self.scan_btn.setEnabled(enabled)
        self.clean_btn.setEnabled(enabled)
        for _, _, cb in self.checkboxes:
            cb.setEnabled(enabled)
        self.trash_cb.setEnabled(enabled)


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

if __name__ == "__main__":
    if not is_admin():
        if getattr(sys, 'frozen', False):
            try:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                sys.exit(0)
            except Exception as e:
                QMessageBox.warning(None, "오류", f"관리자 권한 요청 실패: {e}")
                sys.exit(1)
        else:
            print("경고: 비관리자 권한 개발 환경 스트리밍 모드")
            
    app = QApplication(sys.argv)
    win = CleanerApp()
    win.show()
    sys.exit(app.exec_())