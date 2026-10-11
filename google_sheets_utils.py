"""
Google Sheets ユーティリティモジュール - Google Sheetsへの接続とデータ取得

【認証方式について】
サービスアカウント方式を使用しています。
OAuth2方式と異なりトークンの期限切れが発生しないため、認証情報の更新処理は不要です。
サービスアカウントのJSONファイルのパスは .env の SERVICE_ACCOUNT_PATH に記載してください。
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import SCOPES, SERVICE_ACCOUNT_PATH, SPREADSHEET_ID, SHEET_NAME
from logger import get_logger


def connect_to_sheets_and_get_values():
    """
    スプレッドシートに接続し、シートの全データ（見出し行を含む）を取得する

    【この関数をmain()の最初に実行する理由】
    - 接続失敗を早期に検知し、無駄なブラウザ起動・楽天へのアクセスを防ぐ
    - 取得したserviceを後続の書き込み処理に引き渡し、再認証を不要にする

    Returns:
        tuple: (service, values)
            - service: Google Sheets APIのサービスオブジェクト（失敗時はNone）
            - values: シートの値（行のリスト。失敗時は空のリスト）
    """
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_PATH,
            scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)

        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:K"
        ).execute()
        return service, result.get('values', [])

    except Exception as e:
        get_logger().error(f"スプレッドシートへの接続に失敗しました: {e}")
        return None, []
