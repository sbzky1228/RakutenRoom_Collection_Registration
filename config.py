import os
import sys
from pathlib import Path
from dotenv import load_dotenv


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


# .envファイルを読み込む
ENV_PATH = _resolve_env_path()
if ENV_PATH:
    load_dotenv(str(ENV_PATH))
    ENV_DIR = ENV_PATH.parent
else:
    load_dotenv('.env')
    ENV_DIR = Path.cwd()


# 楽天ログイン情報
RAKUTEN_USER_ID = os.getenv('RAKUTEN_USER_ID', '')
RAKUTEN_PASSWORD = os.getenv('RAKUTEN_PASSWORD', '')

# Google Sheets情報
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '')
SHEET_NAME = os.getenv('SHEET_NAME', 'Sheet1')
SERVICE_ACCOUNT_PATH = _resolve_path_from_env(os.getenv('SERVICE_ACCOUNT_PATH', ''), ENV_DIR)

# Google Sheets API scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Playwrightの設定
# - PLAYWRIGHT_BROWSERS_PATH は .env または環境変数から読み取ります
# - 実行ファイル起動時に未指定の場合は、Windowsの既定パス (%LOCALAPPDATA%\ms-playwright) を自動検出します
PLAYWRIGHT_BROWSERS_PATH = _resolve_path_from_env(os.getenv('PLAYWRIGHT_BROWSERS_PATH', ''), ENV_DIR)
CHROMIUM_EXECUTABLE_PATH = _resolve_path_from_env(os.getenv('CHROMIUM_EXECUTABLE_PATH', ''), ENV_DIR)

if not PLAYWRIGHT_BROWSERS_PATH and getattr(sys, 'frozen', False):
    default_playwright = Path(os.path.expanduser('~')) / 'AppData' / 'Local' / 'ms-playwright'
    if default_playwright.exists():
        PLAYWRIGHT_BROWSERS_PATH = str(default_playwright)

if PLAYWRIGHT_BROWSERS_PATH:
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = PLAYWRIGHT_BROWSERS_PATH

HEADLESS_MODE = False    # ヘッドレスモード
BROWSER_TIMEOUT = 60000  # タイムアウト（ミリ秒）
PAGE_LOAD_TIMEOUT = 10000  # ページロード待機時間
NAVIGATION_TIMEOUT = 60000

# 楽天ROOM UIセレクタ
# 各ページ・画面ごとに分類し、どのページで使うかがわかるように整理しています。
class RoomSelectors:
    # --- ログイン画面 ---
    LOGIN_BUTTON = "[aria-label='ログイン'], a:has-text('ログイン'), button:has-text('ログイン')"
    LOGIN_USER_INPUT = "input[id='user_id'], input[name='loginId'], input[id='loginId'], input[placeholder='ユーザーID']"
    LOGIN_PASSWORD_INPUT = "input[id='password_current'], input[type='password'], input[id='loginUserInner_password']"
    LOGIN_SUBMIT_BUTTON = "button[type='submit'], button:has-text('ログイン'), div[id='cta011'], input[type='submit']"

    # --- コレクション一覧ページ ---
    # 既存コレクションの一覧表示と、新規作成ボタンのある画面です。
    COLLECTION_TAB_BUTTON = 'text=コレクション'
    CREATE_NEW_COLLECTION_BUTTON = 'text=新規作成'
    COLLECTION_ITEM_ROW = '.collection-item-row'
    COLLECTION_ITEM_NAME_TEXT = '.collection-item-name'

    # --- my ROOM ページ ---
    MY_ROOM_COLLECTION_CREATE_BUTTON = "button[aria-label='新規コレクションを作成する ＋']"
    MY_ROOM_COLLECTION_CARD = 'div.collection--2OtKZ'
    MY_ROOM_COLLECTION_TITLE = 'a.title--1MToE'
    MY_ROOM_COLLECTION_IMAGE_LINK = 'a.link-image--2kguM'
    MY_ROOM_COLLECTION_EDIT_BUTTON = 'div.collection-icon--2GUat a.link--3dvDa'
    MY_ROOM_COLLECTION_ITEM_COUNT = 'div.number-display--1oihd'

    # --- 既存コレクション詳細画面 ---
    # 既存のコレクションを開くと表示される閲覧画面用の要素です。
    COLLECTION_DETAIL_PAGE_TITLE = "div.container--3w_bo.container-small--1ZAOb.border-bottom--3kZUq div.style-bold--1xXjA"
    COLLECTION_DETAIL_PAGE_EDIT_BUTTON = "a[aria-label='編集']"
    COLLECTION_DETAIL_ITEM_CARD = "div.container--JAywt.collect--3N1ip"
    COLLECTION_DETAIL_ITEM_IMAGE_LINK = "a.link-image--2kguM"
    COLLECTION_DETAIL_ITEM_COMMENT_TEXT = "div.social-text-area--22OZg"
    COLLECTION_DETAIL_ITEM_PRICE_TEXT = "div.collect-gadgets--3BX8v div.text-display--3jedW"

    # --- 新規コレクション作成 / 既存コレクション編集画面 ---
    # 新規追加ボタンを押した後の画面と、既存コレクションの編集ボタンを押した後の画面は
    # 同じモーダル/フォームUI構造を共有しているため、同じセレクタ群を使います。
    COLLECTION_CATEGORY_BUTTON = "li[ng-click='showCategory()']"
    COLLECTION_ITEMS_BUTTON = "li[ng-click='showCategoryItems()']"
    COLLECTION_NAME_EDIT_BUTTON = "li[ng-click='collectionName()']"
    COLLECTION_DESCRIPTION_BUTTON = "li[ng-click='showIntroductions()']"
    COLLECTION_IMAGE_EDIT_BUTTON = "li[ng-click='showImgEdit()']"
    COLLECTION_DELETE_BUTTON = "div.button:has-text('このコレクションを削除')"
    COLLECTION_FINISH_BUTTON = "div.button[ng-click='createFinish()']"
    COLLECTION_CATEGORY_NAME_TEXT = "span.current-value-freeCollection[ng-bind='freeCollectionItem.categoryName']"
    COLLECTION_SELECTED_ITEMS_COUNT_TEXT = "span.current-value-freeCollection[ng-show='itemsCheckedIdsLength>0']"
    COLLECTION_NAME_TEXT = "span.current-value-freeCollection[ng-bind='freeCollectionItem.name']"
    COLLECTION_DESCRIPTION_TEXT = "span.current-value-freeCollection[ng-bind='freeCollectionItem.description']"

    # --- 新規コレクション作成 / アイテム追加画面 ---
    COLLECTION_NAME_INPUT = "input[name='collection_name']"
    COLLECTION_GENRE_SELECT = "select[name='genre']"
    COLLECTION_CREATE_BUTTON = "text=作成"
    ITEM_URL_INPUT = "input[name='item_url']"
    ITEM_ADD_BUTTON = "text=追加"

SELECTORS = RoomSelectors()

# Rakuten Room / navigation
RAKUTEN_ROOM_BASE_URL = 'https://room.rakuten.co.jp'
