"""
設定ファイル - 環境変数や定数を管理

このモジュールでは以下を定義します：
- 楽天ログイン情報（ユーザーID、パスワード）
- Google Sheets連携情報（spreadsheet ID、sheet name）
- ログ・user_dataの保存先
- Playwrightとタイムアウト設定
- Google Sheets APIスコープ
- 楽天ROOM・楽天市場URL定義
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv


# プログラムのフォルダ（user_data・logsの保存先）
# - .exe実行時: RakutenRoomCollection.exe と同じフォルダ
# - python main.py 実行時: このファイルのあるフォルダ（プロジェクト直下）
# 実行時の作業フォルダ（タスクスケジューラの「開始」設定など）に左右されないよう固定する
APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, 'frozen', False)
    else Path(__file__).resolve().parent
)


def _resolve_env_path() -> Path | None:
    candidates = []
    if getattr(sys, 'frozen', False):
        candidates.append(Path(sys._MEIPASS) / '.env')
        candidates.append(Path(sys.executable).resolve().parent / '.env')
    candidates.append(Path.cwd() / '.env')
    candidates.append(Path(__file__).resolve().parent / '.env')
    for path in candidates:
        if path.exists():
            return path.resolve()
    return None


def _resolve_path_from_env(value: str, base_dir: Path) -> str:
    if not value:
        return ''
    path = Path(value)
    if path.is_absolute():
        return str(path)

    candidate = base_dir / path
    if candidate.exists():
        return str(candidate.resolve())

    candidate = Path.cwd() / path
    if candidate.exists():
        return str(candidate.resolve())

    candidate = Path(__file__).resolve().parent / path
    return str(candidate.resolve())


# .envファイルを読み込む（機密な情報を環境変数から取得）
ENV_PATH = _resolve_env_path()
if ENV_PATH:
    load_dotenv(str(ENV_PATH))
    ENV_DIR = ENV_PATH.parent
else:
    load_dotenv('.env')
    ENV_DIR = Path.cwd()

# ============================================================
# 楽天ログイン情報
# ============================================================
RAKUTEN_USER_ID = os.getenv('RAKUTEN_USER_ID', '')  # 楽天会員ID
RAKUTEN_PASSWORD = os.getenv('RAKUTEN_PASSWORD', '')  # 楽天パスワード

# ============================================================
# Google Sheets連携情報
# ============================================================
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '')  # Googleスプレッドシートの一意のID
SHEET_NAME = os.getenv('SHEET_NAME', 'Sheet1')  # シート名
SERVICE_ACCOUNT_PATH = _resolve_path_from_env(os.getenv('SERVICE_ACCOUNT_PATH', ''), ENV_DIR)

# ============================================================
# ログの保存先
# .envのLOG_DIRで任意のフォルダを指定できる（相対パスはプログラムのフォルダ基準）
# 未指定の場合はプログラムのフォルダの logs
# ============================================================
_log_dir = os.getenv('LOG_DIR', '').strip()
LOG_DIR = (APP_DIR / _log_dir).resolve() if _log_dir else APP_DIR / 'logs'

# ============================================================
# Playwright設定
# ============================================================
PLAYWRIGHT_BROWSERS_PATH = _resolve_path_from_env(os.getenv('PLAYWRIGHT_BROWSERS_PATH', ''), ENV_DIR)

if not PLAYWRIGHT_BROWSERS_PATH and getattr(sys, 'frozen', False):
    default_playwright = Path(os.path.expanduser('~')) / 'AppData' / 'Local' / 'ms-playwright'
    if default_playwright.exists():
        PLAYWRIGHT_BROWSERS_PATH = str(default_playwright)

if PLAYWRIGHT_BROWSERS_PATH:
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = PLAYWRIGHT_BROWSERS_PATH

HEADLESS_MODE = False   # ヘッドレスモード（UIを表示しない）
BROWSER_TIMEOUT = 60000  # ブラウザタイムアウト時間（ミリ秒）
NAVIGATION_TIMEOUT = 60000  # ナビゲーション待機時間（ミリ秒）

# ============================================================
# APIスコープ
# ============================================================
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# ============================================================
# 楽天URL定義
# ============================================================
RAKUTEN_MY_URL = "https://my.rakuten.co.jp/"  # ログイン状態の判定に使う会員ページ
RAKUTEN_ROOM_URL = "https://room.rakuten.co.jp/"  # 楽天ROOMのトップ
