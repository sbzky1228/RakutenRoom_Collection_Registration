"""
テストの共通設定

- プロジェクト直下のモジュールを import できるようにする
- ログは一時フォルダに出力し、プロジェクトの logs を汚さない
  （config を import する前に環境変数で指定する。load_dotenv は既存の環境変数を上書きしない）
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ['LOG_DIR'] = tempfile.mkdtemp(prefix='rakuten_room_collection_test_logs_')
os.environ['SHEET_NAME'] = 'リスト'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
