"""
main のテスト（ブラウザ・スプレッドシートには接続しない）

処理の流れ（対象なしなら終了、失敗したコレクションがあっても続行、結果に応じたシート更新）を確認する。
"""
import asyncio
import datetime
import main as main_mod
from room_collection import CollectionResult
from test_google_sheets_manager import HEADER, FakeService, row


class FakeBrowserManager:
    def __init__(self):
        self.closed = False

    async def get_page(self):
        return object()

    async def close(self):
        self.closed = True


def setup(monkeypatch, values, results=None, login_ok=True):
    """main が使う関数を差し替え、呼び出し状況を返す"""
    calls = {'browser': None, 'registered': []}
    service = FakeService()
    monkeypatch.setattr(main_mod, 'connect_to_sheets_and_get_values', lambda: (service, values))

    async def create_browser_manager():
        calls['browser'] = FakeBrowserManager()
        return calls['browser']

    async def login(page):
        return login_ok

    async def open_collections(page):
        return 'https://room.rakuten.co.jp/room_test/collections'

    async def get_existing(page, url):
        return {}

    async def register(page, url, collection, existing):
        calls['registered'].append(collection.name)
        result = (results or {}).get(collection.name)
        if isinstance(result, Exception):
            raise result
        return result(collection.items) if result else CollectionResult(added=list(collection.items))

    monkeypatch.setattr(main_mod, 'create_browser_manager', create_browser_manager)
    monkeypatch.setattr(main_mod, 'login_to_rakuten', login)
    monkeypatch.setattr(main_mod, 'open_my_room_collections', open_collections)
    monkeypatch.setattr(main_mod, 'get_existing_collections', get_existing)
    monkeypatch.setattr(main_mod, 'register_collection', register)
    return calls, service


def written(service):
    """シートに書き込んだ {セル: 値}"""
    return {d['range']: d['values'][0][0] for body in service.bodies for d in body['data']}


def test_no_target_does_not_start_browser(monkeypatch):
    calls, service = setup(monkeypatch, [HEADER, row('https://item.rakuten.co.jp/a/1/', '商品1', '')])
    asyncio.run(main_mod.main())
    assert calls['browser'] is None
    assert service.bodies == []


def test_sheet_connection_failure_does_not_start_browser(monkeypatch):
    calls, _ = setup(monkeypatch, [])
    monkeypatch.setattr(main_mod, 'connect_to_sheets_and_get_values', lambda: (None, []))
    asyncio.run(main_mod.main())
    assert calls['browser'] is None


def test_login_failure_stops_and_closes_browser(monkeypatch):
    values = [HEADER, row('https://item.rakuten.co.jp/a/1/', '商品1', 'キッチン')]
    calls, service = setup(monkeypatch, values, login_ok=False)
    asyncio.run(main_mod.main())
    assert calls['registered'] == []
    assert calls['browser'].closed
    assert service.bodies == []


def test_results_are_written_per_collection(monkeypatch):
    values = [
        HEADER,
        row('https://item.rakuten.co.jp/a/1/', '商品1', 'キッチン'),
        row('https://item.rakuten.co.jp/a/2/', '商品2', 'キッチン'),
        row('https://item.rakuten.co.jp/a/3/', '商品3', 'キッチン'),
        row('https://item.rakuten.co.jp/b/1/', '商品4', 'ガジェット'),
    ]
    results = {
        # キッチン: 1件登録 / 1件ROOMに無い / 1件失敗
        'キッチン': lambda items: CollectionResult(added=[items[0]], not_found=[items[1]], failed=[items[2]]),
    }
    calls, service = setup(monkeypatch, values, results)
    today = datetime.date.today().strftime('%Y-%m-%d')
    asyncio.run(main_mod.main())

    assert calls['registered'] == ['キッチン', 'ガジェット']
    cells = written(service)
    statuses = {cell: value for cell, value in cells.items() if '!J' in cell}
    dates = {cell for cell, value in cells.items() if '!K' in cell and value == today}
    # 失敗した行4は書き込まない（「未」のまま次回再試行）
    assert statuses == {'リスト!J2': '済', 'リスト!J3': '不可', 'リスト!J5': '済'}
    assert dates == {'リスト!K2', 'リスト!K3', 'リスト!K5'}
    assert calls['browser'].closed


def test_unexpected_error_closes_browser(monkeypatch):
    values = [HEADER, row('https://item.rakuten.co.jp/a/1/', '商品1', 'キッチン')]
    calls, service = setup(monkeypatch, values, {'キッチン': RuntimeError('想定外')})
    asyncio.run(main_mod.main())
    assert calls['browser'].closed
    assert service.bodies == []
