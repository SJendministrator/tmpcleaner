# 🧹 SafeCleaner (Storage Sense 스타일 캐시 정리기)

Windows의 찌든 임시 파일과 브라우저 캐시를 안전하고 강력하게 삭제하는 **PyQt5 기반의 고속 디스크 다이어트 프로그램**입니다. 단일 스레드 삭제의 한계를 극복하기 위해 **Multi-threading(ThreadPoolExecutor)** 방식을 도입하여, 수십만 개의 자잘한 파일도 굳음(응답 없음) 현상 없이 초고속으로 진압합니다.

## ✨ 주요 기능
- **안전한 화이트리스트 기반 삭제:** 시스템 실행에 치명적인 파일(`.exe`, `.dll`, `.sys` 등)은 필터링되어 절대 지워지지 않습니다.
- **초고속 멀티스레딩 연산:** `ThreadPoolExecutor`를 활용해 최대 16개 스레드가 동시 다발적으로 파일을 소거합니다.
- **실시간 GUI 시각화:** 대량 파일 삭제 시에도 UI가 멈추지 않고 프로그레스 바(Progress Bar)를 통해 진행 상황을 실시간으로 안내합니다.
- **Fluent 다크 모드 테마:** 눈이 편안한 Windows 11 스타일의 다크 UI를 지원합니다.

## 🛠️ 요구 사항
```bash
pip install pyqt5 send2trash