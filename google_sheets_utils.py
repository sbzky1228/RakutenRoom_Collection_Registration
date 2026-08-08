"""
Google Sheets ユーティリティモジュール - Google Sheetsサービス初期化関数

Google Sheets APIへの接続・認証とサービスオブジェクトの取得を担当します。

認証方式はサービスアカウント方式です。
サービスアカウントJSONのパスは `.env` の SERVICE_ACCOUNT_PATH から読み取ります。
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import SCOPES, SERVICE_ACCOUNT_PATH
from logger import logger


def connect_to_sheets():
    """Google Sheets APIに接続し、serviceオブジェクトを返します。"""
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_PATH,
            scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)
        logger.info('スプレッドシートへの接続に成功しました。')
        return service
    except Exception as e:
        logger.error(f"スプレッドシートへの接続に失敗しました: {e}")
        return None
