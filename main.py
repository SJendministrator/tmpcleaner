import sys
import ctypes
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QLabel, QProgressBar, QTextEdit, QMessageBox

from utils import human_size, is_admin
from core import TARGETS, PREVIEW_LIMIT
from threads import ScanThread, CleanThread
from ui import STYLESHEET, PreviewDialog

class CleanerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SafeCleaner (Storage Sense 스타일)")
        self.setGeometry(500, 250, 720, 600)
        self.setStyleSheet(STYLESHEET)
        
        self.all_scanned_files = []
        self.all_scanned_bytes = 0
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        self.header = QLabel("삭제해도 안전한 시스템 캐시 및 브라우저 임시 파일만 정리합니다.")
        self.header.setObjectName("headerLabel")
        layout.addWidget(self.header)

        self.trash_cb = QCheckBox("🔄 삭제 시 휴지통으로 이동 (안전한 복구 권장)")
        self.trash_cb.setChecked(True)
        layout.addWidget(self.trash_cb)
        layout.addSpacing(5)

        self.checkboxes = []
        for name, path in TARGETS:
            cb = QCheckBox(name)
            cb.setChecked(False if "다운로드" in name else True)
            layout.addWidget(cb)
            self.checkboxes.append((name, path, cb))
            
        layout.addSpacing(10)

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton("🔍 선택 항목 스캔")
        self.scan_btn.clicked.connect(self.scan_and_preview)
        self.clean_btn = QPushButton("🧹 정리 실행")
        self.clean_btn.clicked.connect(self.clean_selected)
        btn_row.addWidget(self.scan_btn)
        btn_row.addWidget(self.clean_btn)
        layout.addLayout(btn_row)

        self.progressBar = QProgressBar(self)
        self.progressBar.setTextVisible(True)
        self.progressBar.hide()
        layout.addWidget(self.progressBar)
        
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(QLabel("📝 작업 로그:"))
        layout.addWidget(self.log)

        self.setLayout(layout)

    def _selected_targets(self):
        return [(name, path) for name, path, cb in self.checkboxes if cb.isChecked()]

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