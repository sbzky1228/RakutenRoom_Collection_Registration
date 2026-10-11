"""
Google Sheetsマネージャー - コレクション登録対象の抽出とステータス更新

列は見出し名で探すため、列の並び順が変わっても動作します。
"""
import unicodedata
from dataclasses import dataclass, field
from config import SPREADSHEET_ID, SHEET_NAME
from logger import get_logger

REQUIRED_COLUMNS = [
    'ItemURL', 'ItemCode', 'ItemName', 'CollectionName',
    'PostStatus', 'CollectionStatus', 'CollectedDate',
]

# 楽天ROOMのコレクション名の上限文字数（作成画面の入力欄の maxlength）
COLLECTION_NAME_MAX_LENGTH = 50


@dataclass
class SheetItem:
    """コレクションに登録する商品（スプレッドシートの1行）"""
    row_number: int      # スプレッドシートの行番号（1始まり、見出し行が1）
    item_url: str
    item_code: str
    item_name: str       # 「【楽天市場】」「：ショップ名」を除いた商品名


@dataclass
class Collection:
    """登録先のコレクションと、そこに登録する商品"""
    name: str
    items: list[SheetItem] = field(default_factory=list)


def normalize_item_name(raw_name: str) -> str:
    """
    ItemNameから先頭の「【楽天市場】」と、末尾の「：ショップ名」を除く

    例）【楽天市場】【公式】ビタペアC セラムミスト：【公式】ネイチャーリパブリック
        ⇒ 【公式】ビタペアC セラムミスト
    """
    name = (raw_name or '').strip()
    if name.startswith('【楽天市場】'):
        name = name[len('【楽天市場】'):]

    last_colon = max(name.rfind('：'), name.rfind(':'))
    if last_colon != -1:
        name = name[:last_colon]

    return name.strip()


def normalize_collection_name(name: str) -> str:
    """
    コレクション名を比較用の形にそろえる
    （全角・半角の英数字や記号、全角スペース、連続した空白、前後の空白の違いを無視する）
    """
    return ' '.join(unicodedata.normalize('NFKC', name or '').split())


def _column_letter(index: int) -> str:
    """0始まりの列番号をA1形式の列名に変換する（0 → A、26 → AA）"""
    letters = ''
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


class GoogleSheetsManager:
    """Google Sheets APIを操作するクラス"""

    def __init__(self, service, values):
        """
        Args:
            service: Google Sheets APIのサービスオブジェクト
            values: connect_to_sheets_and_get_values() で取得したシートの値
        """
        self.service = service
        self.values = values
        self.col = {}

    def _load_header(self) -> bool:
        """見出し行から必須列の位置を取得する"""
        header = self.values[0] if self.values else []
        missing = [name for name in REQUIRED_COLUMNS if name not in header]
        if missing:
            get_logger().error(f"スプレッドシートの1行目に必須列が見つかりません: {', '.join(missing)}")
            return False
        self.col = {name: header.index(name) for name in REQUIRED_COLUMNS}
        return True

    def _cell(self, row: list, name: str) -> str:
        index = self.col[name]
        return row[index].strip() if len(row) > index and row[index] else ''

    def get_target_collections(self) -> list[Collection] | None:
        """
        PostStatusが「済」かつCollectionStatusが「未」の商品を、CollectionNameごとにまとめて返す

        Returns:
            list[Collection]: 登録対象（対象なしの場合は空のリスト）
            None: 見出しが不正などで取得できなかった場合
        """
        logger = get_logger()
        if not self._load_header():
            return None

        collections: dict[str, Collection] = {}
        no_name_count = 0
        too_long_names = set()

        for row_number, row in enumerate(self.values[1:], start=2):
            if self._cell(row, 'PostStatus') != '済' or self._cell(row, 'CollectionStatus') != '未':
                continue

            item = SheetItem(
                row_number=row_number,
                item_url=self._cell(row, 'ItemURL'),
                item_code=self._cell(row, 'ItemCode'),
                item_name=normalize_item_name(self._cell(row, 'ItemName')),
            )
            collection_name = self._cell(row, 'CollectionName')

            if not collection_name:
                # 登録先が決まっていない商品は対象外（CollectionNameが記入されれば次回以降に登録される）
                no_name_count += 1
                continue
            if len(collection_name) > COLLECTION_NAME_MAX_LENGTH:
                too_long_names.add(collection_name)
                continue
            if not item.item_url:
                logger.warning(f"ItemURLが空のため対象外: 行{row_number} {item.item_code}")
                continue

            # 表記ゆれ（全角・半角スペースなど）があっても同じコレクションとしてまとめる
            key = normalize_collection_name(collection_name)
            collections.setdefault(key, Collection(collection_name)).items.append(item)

        if no_name_count:
            logger.warning(f"CollectionNameが未記入のため、登録対象外とした商品: {no_name_count}件")
        for name in sorted(too_long_names):
            logger.warning(
                f"コレクション名が{COLLECTION_NAME_MAX_LENGTH}文字を超えるため、登録対象外としました: {name}"
            )

        item_count = sum(len(collection.items) for collection in collections.values())
        logger.info(f"登録対象: {len(collections)}コレクション / {item_count}件")
        for collection in collections.values():
            logger.info(f"  コレクション「{collection.name}」: {len(collection.items)}件")
            for item in collection.items:
                logger.info(f"    行{item.row_number} {item.item_code} / {item.item_name}")
        return list(collections.values())

    def update_collection_status(self, items: list[SheetItem], status: str, collected_date: str) -> bool:
        """
        指定した商品の行のCollectionStatusとCollectedDateを更新する（1回のAPI呼び出しでまとめて更新）

        Args:
            items: 更新する商品
            status: CollectionStatusに書き込む値（「済」「不可」）
            collected_date: CollectedDateに書き込む日付
        """
        if not items:
            return True

        status_col = _column_letter(self.col['CollectionStatus'])
        date_col = _column_letter(self.col['CollectedDate'])
        data = []
        for item in items:
            data.append({'range': f"{SHEET_NAME}!{status_col}{item.row_number}", 'values': [[status]]})
            data.append({'range': f"{SHEET_NAME}!{date_col}{item.row_number}", 'values': [[collected_date]]})

        try:
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={'valueInputOption': 'RAW', 'data': data}
            ).execute()
            rows = ', '.join(str(item.row_number) for item in items)
            get_logger().info(f"CollectionStatusを「{status}」に更新しました（行: {rows}）")
            return True
        except Exception as e:
            get_logger().error(f"スプレッドシートのCollectionStatus更新に失敗しました: {e}")
            return False
