"""google_sheets_manager のテスト（スプレッドシートには接続しない）"""
from google_sheets_manager import (
    GoogleSheetsManager,
    _column_letter,
    normalize_collection_name,
    normalize_item_name,
)

HEADER = ['ItemURL', 'ShopCode', 'ItemID', 'ItemCode', 'ItemName', 'CollectionName',
          'CollectionGenre', 'PostStatus', 'PostedDate', 'CollectionStatus', 'CollectedDate']


def row(url, name='', collection='', post='済', status='未'):
    shop, item_id = url.rstrip('/').split('/')[-2:]
    return [url, shop, item_id, f'{shop}:{item_id}', name, collection, '', post, '2026-10-01', status, '']


class FakeService:
    """values().batchUpdate() の呼び出し内容を記録するフェイク"""

    def __init__(self, fail=False):
        self.bodies = []
        self.fail = fail

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def batchUpdate(self, **kwargs):
        self.bodies.append(kwargs['body'])
        return self

    def execute(self):
        if self.fail:
            raise RuntimeError('API error')
        return {}


def test_normalize_item_name_removes_prefix_and_shop():
    raw = '【楽天市場】【 ネイチャーリパブリック 公式】ビタペアC セラムミスト 韓国コスメ：【公式】ネイチャーリパブリック'
    assert normalize_item_name(raw) == '【 ネイチャーリパブリック 公式】ビタペアC セラムミスト 韓国コスメ'


def test_normalize_item_name_uses_last_colon_and_keeps_name_without_prefix():
    assert normalize_item_name('商品A：説明：ショップ') == '商品A：説明'
    assert normalize_item_name('商品B') == '商品B'
    assert normalize_item_name('') == ''


def test_normalize_collection_name_ignores_width_and_spaces():
    assert normalize_collection_name('　キッチン　 ガジェット ') == 'キッチン ガジェット'
    assert normalize_collection_name('ＡＢＣ１２３') == 'ABC123'
    assert normalize_collection_name('キッチン') != normalize_collection_name('ガジェット')


def test_column_letter():
    assert _column_letter(0) == 'A'
    assert _column_letter(9) == 'J'
    assert _column_letter(25) == 'Z'
    assert _column_letter(26) == 'AA'


def test_get_target_collections_filters_and_groups():
    values = [
        HEADER,
        row('https://item.rakuten.co.jp/a/1/', '【楽天市場】商品1：店A', 'キッチン'),
        row('https://item.rakuten.co.jp/a/2/', '商品2', 'キッチン　'),            # 表記ゆれ → 同じコレクション
        row('https://item.rakuten.co.jp/b/3/', '商品3', 'ガジェット'),
        row('https://item.rakuten.co.jp/b/4/', '商品4', 'ガジェット', post='未'),   # 未投稿 → 対象外
        row('https://item.rakuten.co.jp/b/5/', '商品5', 'ガジェット', status='済'),  # 登録済み → 対象外
        row('https://item.rakuten.co.jp/b/6/', '商品6', ''),                       # コレクション名なし → 対象外
        row('https://item.rakuten.co.jp/b/7/', '商品7', 'あ' * 51),                 # 51文字 → 対象外
        ['https://item.rakuten.co.jp/c/8/'],                                       # 途中までしか値が無い行
    ]
    collections = GoogleSheetsManager(FakeService(), values).get_target_collections()

    assert [c.name for c in collections] == ['キッチン', 'ガジェット']
    kitchen = collections[0]
    assert [i.row_number for i in kitchen.items] == [2, 3]
    assert kitchen.items[0].item_name == '商品1'
    assert kitchen.items[0].item_code == 'a:1'
    assert [i.row_number for i in collections[1].items] == [4]


def test_get_target_collections_finds_columns_by_header_name():
    header = list(reversed(HEADER))
    values = [header, list(reversed(row('https://item.rakuten.co.jp/a/1/', '商品1', 'キッチン')))]
    collections = GoogleSheetsManager(FakeService(), values).get_target_collections()
    assert collections[0].items[0].item_url == 'https://item.rakuten.co.jp/a/1/'


def test_get_target_collections_returns_none_when_header_missing():
    values = [[c for c in HEADER if c != 'CollectionName'], []]
    assert GoogleSheetsManager(FakeService(), values).get_target_collections() is None
    assert GoogleSheetsManager(FakeService(), []).get_target_collections() is None


def test_get_target_collections_returns_empty_list_when_no_target():
    values = [HEADER, row('https://item.rakuten.co.jp/a/1/', '商品1', '')]
    assert GoogleSheetsManager(FakeService(), values).get_target_collections() == []


def test_update_collection_status_writes_status_and_date_columns():
    service = FakeService()
    values = [HEADER, row('https://item.rakuten.co.jp/a/1/', '商品1', 'キッチン'),
              row('https://item.rakuten.co.jp/a/2/', '商品2', 'キッチン')]
    manager = GoogleSheetsManager(service, values)
    items = manager.get_target_collections()[0].items

    assert manager.update_collection_status(items, '済', '2026-10-11')
    data = service.bodies[0]['data']
    assert data == [
        {'range': 'リスト!J2', 'values': [['済']]}, {'range': 'リスト!K2', 'values': [['2026-10-11']]},
        {'range': 'リスト!J3', 'values': [['済']]}, {'range': 'リスト!K3', 'values': [['2026-10-11']]},
    ]


def test_update_collection_status_skips_empty_and_reports_failure():
    service = FakeService(fail=True)
    values = [HEADER, row('https://item.rakuten.co.jp/a/1/', '商品1', 'キッチン')]
    manager = GoogleSheetsManager(service, values)
    items = manager.get_target_collections()[0].items

    assert manager.update_collection_status([], '済', '2026-10-11')
    assert service.bodies == []
    assert manager.update_collection_status(items, '済', '2026-10-11') is False
