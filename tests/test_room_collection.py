"""
room_collection のテスト（ブラウザは起動しない）

画面操作の部分はフェイクのページと差し替えた関数で置き換え、
商品の照合と、結果（登録 / 登録済み / 不可 / 失敗）の振り分けを確認する。
"""
import asyncio
import pytest
import room_collection as rc
from google_sheets_manager import Collection, SheetItem

COLLECTIONS_URL = 'https://room.rakuten.co.jp/room_test/collections'
EDIT_URL = 'https://room.rakuten.co.jp/room_test/collection/1/edit'


class FakeLocator:
    """Playwrightのロケーターの代わり。操作はページの calls に記録する"""

    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def nth(self, index):
        return FakeLocator(self.page, f'{self.selector}[{index}]')

    def locator(self, selector):
        return FakeLocator(self.page, f'{self.selector} {selector}')

    async def click(self, **kwargs):
        self.page.calls.append(('click', self.selector))

    async def fill(self, value):
        self.page.calls.append(('fill', self.selector, value))

    async def wait_for(self, **kwargs):
        pass

    async def scroll_into_view_if_needed(self):
        pass


class FakePage:
    def __init__(self):
        self.url = COLLECTIONS_URL
        self.calls = []

    def locator(self, selector):
        return FakeLocator(self, selector)

    def get_by_text(self, text, **kwargs):
        return FakeLocator(self, f'text={text}')

    async def wait_for_url(self, url, **kwargs):
        pass


def item(row_number, url):
    return SheetItem(row_number=row_number, item_url=url, item_code=f'code{row_number}', item_name=f'商品{row_number}')


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def screen(monkeypatch):
    """
    画面操作を差し替える。各テストで screen の値を書き換えて状況を作る
      rows: 商品パネルの行（url / checked）
      fully_loaded: 商品一覧を最後まで読み込めたか
      saved: 保存後に編集画面で確認できる商品URL（None なら選んだ商品がすべて保存されたことにする）
      fail_on: 例外を起こす処理名
    """
    state = {'rows': [], 'fully_loaded': True, 'saved': None, 'fail_on': None, 'selected': [],
             'existing_after_save': {}}

    def maybe_fail(name):
        if state['fail_on'] == name:
            raise RuntimeError(f'{name} で失敗')

    async def goto_room(page, url):
        maybe_fail('goto')
        page.url = url

    async def ensure_all_genres(page):
        pass

    async def open_panel(page, menu, panel, attempts=3):
        pass

    async def load_item_rows(page, wanted_keys):
        return state['rows'], state['fully_loaded']

    async def save_collection(page):
        maybe_fail('save')
        page.url = COLLECTIONS_URL

    async def get_existing(page, url):
        return dict(state['existing_after_save'])

    async def get_saved_item_keys(page, edit_url, wanted_keys):
        if state['saved'] is not None:
            return {rc.normalize_item_url(u) for u in state['saved']}
        selected = {rc.normalize_item_url(state['rows'][i]['url']) for i in state['selected']}
        return selected | {rc.normalize_item_url(r['url']) for r in state['rows'] if r['checked']}

    original_click = FakeLocator.click

    async def click(self, **kwargs):
        # 商品の行がクリックされたら、選んだ行として記録する
        if self.selector.startswith(rc.ITEM_ROW + '['):
            state['selected'].append(int(self.selector[len(rc.ITEM_ROW) + 1:-1]))
        await original_click(self, **kwargs)

    monkeypatch.setattr(rc, '_goto_room', goto_room)
    monkeypatch.setattr(rc, '_ensure_all_genres', ensure_all_genres)
    monkeypatch.setattr(rc, '_open_panel', open_panel)
    monkeypatch.setattr(rc, '_load_item_rows', load_item_rows)
    monkeypatch.setattr(rc, '_save_collection', save_collection)
    monkeypatch.setattr(rc, 'get_existing_collections', get_existing)
    monkeypatch.setattr(rc, '_get_saved_item_keys', get_saved_item_keys)
    monkeypatch.setattr(FakeLocator, 'click', click)
    return state


def test_normalize_item_url():
    assert rc.normalize_item_url('https://item.rakuten.co.jp/shop/item1/?scid=x#top') == 'item.rakuten.co.jp/shop/item1/'
    assert rc.normalize_item_url('http://ITEM.rakuten.co.jp/shop/item1') == 'item.rakuten.co.jp/shop/item1/'


def test_is_my_room_items_url():
    assert rc.is_my_room_items_url('https://room.rakuten.co.jp/room_d482f8508f/items')
    assert rc.is_my_room_items_url('https://room.rakuten.co.jp/my_custom_id/items?x=1')  # ROOM IDを変更した場合
    assert not rc.is_my_room_items_url('https://room.rakuten.co.jp/items')
    assert not rc.is_my_room_items_url('https://room.rakuten.co.jp/room_x/collections')


def test_new_collection_selects_items_sets_name_and_saves(screen):
    screen['rows'] = [{'url': 'https://item.rakuten.co.jp/a/1/', 'checked': False},
                      {'url': 'https://item.rakuten.co.jp/a/2/?s=1', 'checked': False}]
    screen['existing_after_save'] = {'キッチン': EDIT_URL}
    page = FakePage()
    existing = {}
    items = [item(2, 'https://item.rakuten.co.jp/a/2/'), item(3, 'https://item.rakuten.co.jp/a/2/'),  # 重複行
             item(4, 'https://item.rakuten.co.jp/x/none/')]

    result = run(rc.register_collection(page, COLLECTIONS_URL, Collection('キッチン', items), existing))

    assert [i.row_number for i in result.added] == [2]
    assert [i.row_number for i in result.already] == [3]
    assert [i.row_number for i in result.not_found] == [4]
    assert result.failed == []
    assert screen['selected'] == [1]
    assert ('fill', rc.NAME_INPUT, 'キッチン') in page.calls
    assert existing == {'キッチン': EDIT_URL}  # 作成したコレクションが作成済みとして追加される


def test_existing_collection_keeps_checked_items_and_does_not_save_without_new_items(screen):
    screen['rows'] = [{'url': 'https://item.rakuten.co.jp/a/1/', 'checked': True}]
    screen['fail_on'] = 'save'  # 保存が呼ばれたら失敗になる
    page = FakePage()

    result = run(rc.register_collection(
        page, COLLECTIONS_URL, Collection('キッチン', [item(2, 'https://item.rakuten.co.jp/a/1/')]),
        {'キッチン': EDIT_URL}))

    assert [i.row_number for i in result.already] == [2]
    assert result.added == [] and result.failed == []
    assert screen['selected'] == []  # 登録済みの商品はクリックしない（外さない）
    assert not any(call[1] == rc.NAME_INPUT for call in page.calls)  # 作成済みなら名前は変えない


def test_existing_collection_matches_normalized_name(screen):
    screen['rows'] = [{'url': 'https://item.rakuten.co.jp/a/1/', 'checked': False}]
    page = FakePage()
    result = run(rc.register_collection(
        page, COLLECTIONS_URL, Collection('キッチン　', [item(2, 'https://item.rakuten.co.jp/a/1/')]),
        {'キッチン': EDIT_URL}))
    assert [i.row_number for i in result.added] == [2]
    assert not any(call[1] == rc.NAME_INPUT for call in page.calls)  # 新規作成していない


def test_not_found_is_retried_when_list_was_not_fully_loaded(screen):
    screen['rows'] = [{'url': 'https://item.rakuten.co.jp/a/1/', 'checked': False}]
    screen['fully_loaded'] = False
    result = run(rc.register_collection(
        FakePage(), COLLECTIONS_URL, Collection('キッチン', [item(2, 'https://item.rakuten.co.jp/x/none/')]),
        {'キッチン': EDIT_URL}))
    assert result.not_found == []
    assert [i.row_number for i in result.failed] == [2]


def test_over_limit(screen):
    screen['rows'] = ([{'url': f'https://item.rakuten.co.jp/a/{n}/', 'checked': True} for n in range(99)]
                      + [{'url': 'https://item.rakuten.co.jp/b/1/', 'checked': False},
                         {'url': 'https://item.rakuten.co.jp/b/2/', 'checked': False}])
    result = run(rc.register_collection(
        FakePage(), COLLECTIONS_URL,
        Collection('キッチン', [item(2, 'https://item.rakuten.co.jp/b/1/'), item(3, 'https://item.rakuten.co.jp/b/2/')]),
        {'キッチン': EDIT_URL}))
    assert [i.row_number for i in result.added] == [2]
    assert [i.row_number for i in result.over_limit] == [3]


def test_unsaved_items_become_failed_including_duplicates(screen):
    screen['rows'] = [{'url': 'https://item.rakuten.co.jp/a/1/', 'checked': False},
                      {'url': 'https://item.rakuten.co.jp/a/2/', 'checked': True}]
    screen['saved'] = ['https://item.rakuten.co.jp/a/2/']  # 保存後に a/1 が入っていない
    items = [item(2, 'https://item.rakuten.co.jp/a/1/'), item(3, 'https://item.rakuten.co.jp/a/1/'),
             item(4, 'https://item.rakuten.co.jp/a/2/'), item(5, 'https://item.rakuten.co.jp/x/none/')]
    result = run(rc.register_collection(FakePage(), COLLECTIONS_URL, Collection('キッチン', items),
                                        {'キッチン': EDIT_URL}))
    assert result.added == []
    assert [i.row_number for i in result.already] == [4]       # 元から入っていた商品は「済」のまま
    assert [i.row_number for i in result.not_found] == [5]     # ROOMに無い商品は「不可」のまま
    assert [i.row_number for i in result.failed] == [2, 3]     # 保存を確認できない商品と重複行は再試行


def test_error_before_selecting_marks_all_items_failed(screen):
    screen['fail_on'] = 'goto'
    items = [item(2, 'https://item.rakuten.co.jp/a/1/'), item(3, 'https://item.rakuten.co.jp/a/2/')]
    result = run(rc.register_collection(FakePage(), COLLECTIONS_URL, Collection('キッチン', items),
                                        {'キッチン': EDIT_URL}))
    assert [i.row_number for i in result.failed] == [2, 3]
    assert result.succeeded == [] and result.unavailable == []


def test_new_collection_missing_after_save_is_failed(screen):
    screen['rows'] = [{'url': 'https://item.rakuten.co.jp/a/1/', 'checked': False}]
    screen['existing_after_save'] = {}  # 保存後の一覧に作ったはずのコレクションが無い
    result = run(rc.register_collection(
        FakePage(), COLLECTIONS_URL, Collection('キッチン', [item(2, 'https://item.rakuten.co.jp/a/1/')]), {}))
    assert [i.row_number for i in result.failed] == [2]
