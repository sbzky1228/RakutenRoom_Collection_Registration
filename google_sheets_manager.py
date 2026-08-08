"""
Google Sheetsマネージャー - Google Sheetsへのデータ取得・検索・書き込みを担当します。
"""
from googleapiclient.errors import HttpError
from config import SHEET_NAME, SPREADSHEET_ID
from logger import logger


class GoogleSheetsManager:
    """Google Sheets APIを操作するクラス"""

    def __init__(self, service):
        self.service = service
        self.spreadsheet_id = SPREADSHEET_ID
        self.sheet_name = SHEET_NAME

    def get_sheet_data(self):
        """スプレッドシートの値を取得します。"""
        try:
            range_name = self.sheet_name
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            values = result.get('values', [])
            logger.info(f"スプレッドシートから {len(values)} 行を取得しました")
            return values
        except Exception as e:
            logger.error(f"スプレッドシートの読み込みに失敗しました: {e}")
            return []

    def _normalize_item_name(self, raw_name: str) -> str:
        """ItemNameの不要な接頭辞・末尾部分を削除します。"""
        if not raw_name:
            return ''

        name = raw_name
        if name.startswith('【楽天市場】'):
            name = name[len('【楽天市場】'):]

        last_colon = max(name.rfind(':'), name.rfind('：'))
        if last_colon != -1:
            name = name[:last_colon]

        return name.strip()

    def find_uncollected_items(self, data):
        """スプレッドシートのデータから未登録アイテムを抽出します。"""
        items = []
        for i, row in enumerate(data[1:], start=1):  # Skip header
            if len(row) > 9 and row[7] == '済' and row[9] == '未':
                item = {
                    'row_index': i,
                    'ItemCode': row[3],
                    'ItemURL': row[0],
                    'ItemName': self._normalize_item_name(row[4]),
                    'CollectionName': row[5],
                    'CollectionGenre': row[6]
                }
                items.append(item)
        logger.info(f"未登録のアイテム数: {len(items)}")
        return items

    def get_uncollected_items(self):
        """未登録アイテムをスプレッドシートから取得します。"""
        data = self.get_sheet_data()
        return self.find_uncollected_items(data)

    def update_collection_status(self, row_index: int, status: str, collected_date: str) -> bool:
        """指定行のコレクション登録ステータスと登録日を更新します。"""
        try:
            range_name = f'{self.sheet_name}!J{row_index + 1}:K{row_index + 1}'
            body = {
                'values': [[status, collected_date]]
            }
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            logger.info(f"行 {row_index + 1} のコレクションステータスを '{status}' に更新しました")
            return True
        except HttpError as e:
            logger.error(f"スプレッドシートへのステータス更新に失敗しました: {e}")
            return False
        except Exception as e:
            logger.error(f"スプレッドシートへのステータス更新に失敗しました: {e}")
            return False
