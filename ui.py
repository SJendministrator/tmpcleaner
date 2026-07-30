from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton
from utils import human_size

# 메인 프레임 Fluent 다크 테마 QSS 스타일시트
STYLESHEET = """
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
"""

class PreviewDialog(QDialog):
    def __init__(self, title: str, items: list, total_count: int):
        super().__init__()
        flags = self.windowFlags() & ~Qt.WindowContextHelpButtonHint
        self.setWindowFlags(flags)
        self.setWindowTitle(f"미리보기: {title}")
        self.resize(720, 480)
        
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