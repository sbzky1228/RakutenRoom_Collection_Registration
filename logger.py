"""
ロギングモジュール - ログ出力機能
"""
import datetime
import traceback
from pathlib import Path


class Logger:
    """ログ出力を管理するクラス"""

    def __init__(self, log_dir: str = 'logs'):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.datetime.now()
        self.log_file = self.log_dir / f"rakuten_room_collection_registration_{now.strftime('%Y%m%d_%H%M%S')}.log"

    def log(self, message: str, level: str = 'INFO'):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}"

        print(log_message)
        with self.log_file.open('a', encoding='utf-8') as f:
            f.write(log_message + '\n')

    def info(self, message: str):
        self.log(message, 'INFO')

    def warning(self, message: str):
        self.log(message, 'WARNING')

    def error(self, message: str):
        self.log(message, 'ERROR')

    def exception(self, message: str):
        self.log(f"{message}\n{traceback.format_exc()}", 'ERROR')

    def get_log_file(self) -> str:
        return str(self.log_file)


logger = Logger()
