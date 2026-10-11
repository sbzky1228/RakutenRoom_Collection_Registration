"""
楽天ROOMコレクション登録モジュール - my ROOMのコレクションへ商品を登録する

【画面の構成（調査済み）】
- コレクション一覧: https://room.rakuten.co.jp/<ROOM ID>/collections
    - 各コレクションのカードにタイトルと編集リンク（/collection/<ID>/edit）がある
    - 「新規コレクションを作成する ＋」で /collection/new に移動する
- 作成・編集画面（AngularJS）: ジャンル / 商品 / コレクション名 / 説明 / 画像 の各項目と「完了」
    - 表示直後はAngularJSの準備が終わっておらず、項目を押してもパネルが開かないことがある
    - 商品パネル: ROOMに投稿した商品の一覧。行をクリックするとチェックが切り替わる
      （一覧の枠を下までスクロールすると20件ずつ追加読み込み。1コレクション100件まで）
    - Angularのスコープから、各行の商品URL（eachItem.item.url）と、
      一覧の読み込み状態（collectionItem.isLoading / isFinal = 最後まで読み込んだ）が取れる
    - 商品名はショップ側で変わることがあるため、スプレッドシートのItemURLで照合する
"""
import asyncio
import traceback
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from playwright.async_api import Page
from config import RAKUTEN_ROOM_URL
from google_sheets_manager import Collection, SheetItem, normalize_collection_name
from logger import get_logger
from rakuten_login import complete_login_form, is_login_page

COLLECTION_ITEM_LIMIT = 100  # 1つのコレクションに登録できる商品の上限
ALL_GENRES = 'すべてのジャンル'

# ROOMの商品一覧を開くURL（ROOMに未ログインなら、楽天のログイン状態を使って自動でログインされる）
ROOM_LOGIN_URL = f"{RAKUTEN_ROOM_URL}common/login?redirectafterlogin=/items"

# --- コレクション一覧 ---
CREATE_BUTTON_TEXT = '新規コレクションを作成する'
COLLECTION_EDIT_LINK = "a[href*='/collection/'][href$='/edit']"

# --- 作成・編集画面 ---
GENRE_MENU = "li[ng-click='showCategory()']"
ITEMS_MENU = "li[ng-click='showCategoryItems()']"
NAME_MENU = "li[ng-click='collectionName()']"
GENRE_CURRENT_TEXT = "span[ng-bind='freeCollectionItem.categoryName']"
CREATE_FINISH_BUTTON = "[ng-click='createFinish()']"
# ジャンルパネル
GENRE_ALL_OPTION = "li.selectAll"
GENRE_FINISH_BUTTON = "[ng-click='selectCategoryFinish()']"
# 商品パネル
ITEMS_CONTAINER = ".freeCollectionItemsCon"
ITEM_ROW = "dl[ng-repeat='eachItem in collectionItem.items']"
ITEMS_FINISH_BUTTON = "[ng-click='collectionItemToggleCheckFinish()']"
# コレクション名パネル
NAME_INPUT = "input[ng-model='freeCollectionItem.name']"
NAME_FINISH_BUTTON = "[ng-click='fillNameFinish()']"

# 商品パネルの読み込み状態（件数・読み込み中・最後まで読み込んだか）
ITEMS_STATE_SCRIPT = f"""
() => {{
  const list = angular.element(document.querySelector("{ITEMS_CONTAINER}")).scope().collectionItem;
  return {{count: list.items.length, loading: !!list.isLoading, final: !!list.isFinal}};
}}
"""
# 商品パネルの各行の商品URLと選択状態（選択中 = is_in_collection と toggled_include が異なる。
# 画面のチェックアイコンと同じ条件）を、1回の呼び出しでまとめて取得する
ITEM_ROWS_SCRIPT = """
rows => rows.map(row => {
  const item = angular.element(row).scope().eachItem;
  return {url: (item.item && item.item.url) || '', checked: item.is_in_collection != item.toggled_include};
})
"""

MAX_LOAD_PAGES = 100           # 商品一覧の追加読み込み回数の上限（20件×100回=2000件。無限ループ防止）
LOAD_PAGE_TIMEOUT = 30         # 追加読み込み1回あたりの待ち時間の上限（秒）


@dataclass
class CollectionResult:
    """1つのコレクションへの登録結果"""
    added: list[SheetItem] = field(default_factory=list)       # 今回新しく登録した
    already: list[SheetItem] = field(default_factory=list)     # すでに登録済みだった
    not_found: list[SheetItem] = field(default_factory=list)   # ROOMに投稿した商品の中に無かった
    over_limit: list[SheetItem] = field(default_factory=list)  # 100件の上限を超えた
    failed: list[SheetItem] = field(default_factory=list)      # エラーなどで登録できなかった（次回再試行）

    @property
    def succeeded(self) -> list[SheetItem]:
        """コレクションに登録されている状態になった商品"""
        return self.added + self.already

    @property
    def unavailable(self) -> list[SheetItem]:
        """再実行しても登録できない商品"""
        return self.not_found + self.over_limit


def normalize_item_url(url: str) -> str:
    """商品URLを比較用の形にそろえる（http/https・クエリ・#以降の違いを無視し、末尾を「/」にする）"""
    parts = urlsplit((url or '').strip())
    path = parts.path if parts.path.endswith('/') else parts.path + '/'
    return f"{parts.netloc.lower()}{path}"


def is_my_room_items_url(url: str) -> bool:
    """自分のROOMの商品一覧（https://room.rakuten.co.jp/<ROOM ID>/items）かどうか"""
    parts = urlsplit(url)
    segments = parts.path.strip('/').split('/')
    return parts.netloc == 'room.rakuten.co.jp' and len(segments) == 2 and segments[1] == 'items'


async def _wait_room_page(page: Page, timeout: int = 60000) -> None:
    """
    ROOMのページが表示されるまで待つ。
    途中で楽天のログイン画面（再認証を含む）に移動した場合は、認証を完了させる。
    """
    deadline = asyncio.get_running_loop().time() + timeout / 1000
    while asyncio.get_running_loop().time() < deadline:
        if is_login_page(page.url):
            get_logger().info("楽天ROOMでログイン（再認証）を求められたため、ログインします")
            if not await complete_login_form(page):
                raise RuntimeError("楽天ROOMのログイン（再認証）に失敗しました")
        elif 'room.rakuten.co.jp' in page.url and '/common/login' not in page.url:
            return
        await asyncio.sleep(0.5)
    raise RuntimeError(f"楽天ROOMのページが表示されませんでした。現在のURL: {page.url}")


async def _goto_room(page: Page, url: str) -> None:
    """ROOMのページを開く（ログイン画面に飛ばされた場合は認証してから目的のページを開き直す）"""
    await page.goto(url, wait_until='domcontentloaded')
    await _wait_room_page(page)
    if urlsplit(page.url).path != urlsplit(url).path:
        await page.goto(url, wait_until='domcontentloaded')
        await _wait_room_page(page)


async def open_my_room_collections(page: Page) -> str:
    """
    楽天ROOMにログインし、「my ROOM」⇒「コレクション」を開く

    Returns:
        str: コレクション一覧のURL（https://room.rakuten.co.jp/<ROOM ID>/collections）
    """
    logger = get_logger()

    await page.goto(ROOM_LOGIN_URL, wait_until='domcontentloaded')
    await _wait_room_page(page)

    # 「my ROOM」から自分のROOMを開く（ROOM IDは変更できるため、IDの形には頼らない）
    await page.get_by_text('my ROOM', exact=True).first.click()
    await page.wait_for_url(is_my_room_items_url, wait_until='commit')
    logger.info(f"my ROOMを開きました: {page.url}")

    # 「コレクション」タブを開く
    # （商品名などに「コレクション」を含む要素と区別するため、文言の完全一致で探す）
    # 表示直後は押しても切り替わらないことがあるため、切り替わるまで押し直す
    collections_url = page.url.split('?')[0].rsplit('/', 1)[0] + '/collections'
    for _ in range(3):
        try:
            await page.get_by_text('コレクション', exact=True).first.click(timeout=10000)
            await page.wait_for_url('**/collections', wait_until='commit', timeout=5000)
            break
        except Exception:
            print("[DEBUG] コレクションタブを押しても切り替わらなかったため、押し直します")
    else:
        # それでも切り替わらない場合は、URLを直接開く
        print(f"[DEBUG] コレクションタブから遷移できなかったため、URLを直接開きます: {collections_url}")
        await _goto_room(page, collections_url)
    await page.get_by_text(CREATE_BUTTON_TEXT).first.wait_for()
    logger.info(f"コレクション一覧を開きました: {page.url}")
    return collections_url


async def get_existing_collections(page: Page, collections_url: str) -> dict[str, str]:
    """
    コレクション一覧から、作成済みのコレクションの編集画面URLを取得する

    Returns:
        dict: {正規化したコレクション名: 編集画面のURL}
    """
    await _goto_room(page, collections_url)
    await page.get_by_text(CREATE_BUTTON_TEXT).first.wait_for()

    # コレクションのカードは後から描画されるため、件数が変わらなくなるまで待つ
    # （件数が多い場合に備え、下までスクロールして追加読み込みさせる）
    previous = -1
    for _ in range(MAX_LOAD_PAGES):
        await asyncio.sleep(1.5)
        count = await page.locator(COLLECTION_EDIT_LINK).count()
        if count == previous:
            break
        previous = count
        await page.mouse.wheel(0, 20000)

    cards = await page.eval_on_selector_all(
        COLLECTION_EDIT_LINK,
        """links => links.map(link => {
            // 編集リンクを含むカードのタイトルを取得する
            let card = link;
            while (card && !card.querySelector('a[class*="title"]')) card = card.parentElement;
            const title = card ? card.querySelector('a[class*="title"]').innerText.trim() : '';
            return {title, href: link.href};
        })""",
    )
    collections = {}
    for card in cards:
        key = normalize_collection_name(card['title'])
        if key and key not in collections:
            collections[key] = card['href']
    get_logger().info(f"作成済みのコレクション: {len(collections)}件 {[card['title'] for card in cards]}")
    return collections


async def _open_panel(page: Page, menu_selector: str, panel_selector: str, attempts: int = 3) -> None:
    """
    作成・編集画面の項目（ジャンル・商品・コレクション名）を押して、入力パネルを開く。
    画面の表示直後はAngularJSの準備が終わっておらず、押してもパネルが開かないことがあるため、
    開かなければ押し直す。
    """
    panel = page.locator(panel_selector).first
    for _ in range(attempts):
        menu = page.locator(menu_selector)
        if await menu.is_visible():
            await menu.click()
        try:
            await panel.wait_for(timeout=10000)
            return
        except Exception:
            print(f"[DEBUG] パネルが開かなかったため、押し直します: {menu_selector}")
    raise RuntimeError(f"作成・編集画面の項目を開けませんでした: {menu_selector}")


async def _ensure_all_genres(page: Page) -> None:
    """新規作成時、ジャンルが「すべてのジャンル」になっていることを確認する（違えば選び直す）"""
    logger = get_logger()
    current = (await page.locator(GENRE_CURRENT_TEXT).first.inner_text()).strip()
    if current == ALL_GENRES:
        logger.info(f"ジャンルが「{ALL_GENRES}」であることを確認しました")
        return

    logger.info(f"ジャンルが「{current}」のため、「{ALL_GENRES}」に変更します")
    await _open_panel(page, GENRE_MENU, GENRE_ALL_OPTION)
    await page.locator(GENRE_ALL_OPTION).click()
    await page.locator(GENRE_FINISH_BUTTON).click()
    await page.locator(GENRE_MENU).wait_for()
    current = (await page.locator(GENRE_CURRENT_TEXT).first.inner_text()).strip()
    if current != ALL_GENRES:
        raise RuntimeError(f"ジャンルを「{ALL_GENRES}」に変更できませんでした（現在: {current}）")
    logger.info(f"ジャンルを「{ALL_GENRES}」に変更しました")


async def _wait_items_loaded(page: Page, previous_count: int) -> dict:
    """商品一覧の読み込みが終わる（件数が増える、または最後まで読み込む）まで待つ"""
    deadline = asyncio.get_running_loop().time() + LOAD_PAGE_TIMEOUT
    while True:
        state = await page.evaluate(ITEMS_STATE_SCRIPT)
        if not state['loading'] and (state['final'] or state['count'] > previous_count):
            return state
        if asyncio.get_running_loop().time() > deadline:
            return state
        await asyncio.sleep(0.5)


async def _load_item_rows(page: Page, wanted_keys: set[str]) -> tuple[list[dict], bool]:
    """
    商品パネルの商品を、対象の商品がすべて見つかるか最後まで読み込むまで追加読み込みする

    Returns:
        tuple: (各行の商品URLと選択状態, 見つからない商品を「ROOMに無い」と判断してよいか)
            2つ目は、一覧を最後まで読み込めた場合のみTrue。途中で止まった場合はFalse
    """
    rows = page.locator(ITEM_ROW)
    state = await _wait_items_loaded(page, previous_count=0)
    for _ in range(MAX_LOAD_PAGES):
        row_data = await rows.evaluate_all(ITEM_ROWS_SCRIPT)
        found = {normalize_item_url(row['url']) for row in row_data}
        if state['final'] or wanted_keys <= found:
            print(f"[DEBUG] 商品パネルの読み込み件数: {len(row_data)}（最後まで読み込み: {state['final']}）")
            return row_data, state['final']

        # 一覧の枠を一番下までスクロールすると、次の20件が読み込まれる
        await page.eval_on_selector(ITEMS_CONTAINER, "e => e.scrollTop = e.scrollHeight")
        state = await _wait_items_loaded(page, previous_count=state['count'])
        if not state['final'] and state['count'] <= len(row_data):
            get_logger().warning(f"商品一覧の追加読み込みが進みません（読み込み済み: {state['count']}件）")
            break
    else:
        get_logger().warning(f"商品一覧の追加読み込みが上限（{MAX_LOAD_PAGES}回）に達しました")

    return await rows.evaluate_all(ITEM_ROWS_SCRIPT), False


async def _select_items(page: Page, items: list[SheetItem], result: CollectionResult) -> None:
    """商品パネルで対象の商品にチェックを入れる（すでにチェック済みの商品は触らない）"""
    logger = get_logger()
    await _open_panel(page, ITEMS_MENU, ITEMS_CONTAINER)
    row_data, fully_loaded = await _load_item_rows(page, {normalize_item_url(item.item_url) for item in items})

    url_to_index = {}
    for index, row in enumerate(row_data):
        url_to_index.setdefault(normalize_item_url(row['url']), index)
    selected_count = sum(1 for row in row_data if row['checked'])

    selected_keys = set()
    for item in items:
        key = normalize_item_url(item.item_url)
        index = url_to_index.get(key)
        if index is None:
            if fully_loaded:
                logger.warning(f"ROOMに投稿した商品の中に見つかりません: {item.item_code} / {item.item_name}")
                result.not_found.append(item)
            else:
                # 一覧を最後まで読み込めていないため、ROOMに無いとは言い切れない（次回再試行）
                logger.warning(f"商品一覧を最後まで読み込めず、商品を確認できませんでした: "
                               f"{item.item_code} / {item.item_name}")
                result.failed.append(item)
            continue
        if row_data[index]['checked'] or key in selected_keys:
            # すでにこのコレクションに入っている（同じ商品の重複行も含む）
            result.already.append(item)
            continue
        if selected_count >= COLLECTION_ITEM_LIMIT:
            logger.warning(f"コレクションの上限（{COLLECTION_ITEM_LIMIT}件）に達したため登録できません: "
                           f"{item.item_code} / {item.item_name}")
            result.over_limit.append(item)
            continue

        row = page.locator(ITEM_ROW).nth(index)
        await row.scroll_into_view_if_needed()
        await row.click()
        await row.locator('.icon-circle-check').wait_for(timeout=10000)
        selected_count += 1
        selected_keys.add(key)
        result.added.append(item)

    await page.locator(ITEMS_FINISH_BUTTON).click()
    await page.locator(ITEMS_MENU).wait_for()


async def _save_collection(page: Page) -> None:
    """「完了」を押してコレクションを保存し、作成・編集画面から離れるまで待つ"""
    editing_url = page.url
    await page.locator(CREATE_FINISH_BUTTON).click()
    try:
        await page.wait_for_url(lambda url: url != editing_url, wait_until='commit', timeout=60000)
    except Exception:
        raise RuntimeError(f"「完了」を押しましたが画面が切り替わりませんでした。現在のURL: {page.url}")
    print(f"[DEBUG] 保存後のURL: {page.url}")


async def _get_saved_item_keys(page: Page, edit_url: str, wanted_keys: set[str]) -> set[str]:
    """編集画面を開き直し、コレクションに保存されている商品（チェックが付いている商品）を返す"""
    await _goto_room(page, edit_url)
    await _open_panel(page, ITEMS_MENU, ITEMS_CONTAINER)
    row_data, _ = await _load_item_rows(page, wanted_keys)
    return {normalize_item_url(row['url']) for row in row_data if row['checked']}


async def register_collection(
    page: Page, collections_url: str, collection: Collection, existing: dict[str, str]
) -> CollectionResult:
    """
    コレクションに商品を登録し、保存されたことを編集画面で確認する

    Args:
        page: Playwrightのページオブジェクト
        collections_url: コレクション一覧のURL
        collection: 登録先のコレクション名と商品
        existing: 作成済みのコレクション（{正規化したコレクション名: 編集画面のURL}）。
                  新規作成した場合は、作成したコレクションを追加する

    Returns:
        CollectionResult: 商品ごとの登録結果
    """
    logger = get_logger()
    result = CollectionResult()
    key = normalize_collection_name(collection.name)
    edit_url = existing.get(key)
    is_new = edit_url is None

    try:
        if not is_new:
            logger.info(f"作成済みのコレクション「{collection.name}」に追加登録します（{len(collection.items)}件）")
            await _goto_room(page, edit_url)
        else:
            logger.info(f"コレクション「{collection.name}」が無いため、新規作成します（{len(collection.items)}件）")
            await _goto_room(page, collections_url)
            await page.get_by_text(CREATE_BUTTON_TEXT).first.click()
            await page.wait_for_url('**/collection/new', wait_until='commit')
            await page.locator(GENRE_CURRENT_TEXT).first.wait_for()
            await _ensure_all_genres(page)

        await _select_items(page, collection.items, result)
        if not result.added:
            # 新しく入れる商品が無ければ保存しない（新規作成は商品0件では作成できない）
            logger.info(f"コレクション「{collection.name}」に新しく登録する商品はありませんでした")
            return result

        if is_new:
            await _open_panel(page, NAME_MENU, NAME_INPUT)
            await page.locator(NAME_INPUT).fill(collection.name)
            await page.locator(NAME_FINISH_BUTTON).click()
            await page.locator(NAME_MENU).wait_for()

        await _save_collection(page)

        # 保存されたことを、編集画面を開き直して確認する
        if is_new:
            existing.update(await get_existing_collections(page, collections_url))
            edit_url = existing.get(key)
            if not edit_url:
                raise RuntimeError("新規作成したコレクションが一覧に見つかりません")
        added_keys = {normalize_item_url(item.item_url) for item in result.added}
        missing = added_keys - await _get_saved_item_keys(page, edit_url, added_keys)
        if missing:
            raise RuntimeError(f"保存後のコレクションに入っていない商品があります: {sorted(missing)}")

    except Exception as e:
        logger.error(f"コレクション「{collection.name}」の登録中にエラーが発生しました: {e}（URL: {page.url}）")
        logger.error(traceback.format_exc())
        # 保存を確認できなかった商品（同じ商品の重複行を含む）と、まだ処理していない商品は失敗（次回再試行）とする
        unsaved_keys = {normalize_item_url(item.item_url) for item in result.added}
        result.already = [item for item in result.already if normalize_item_url(item.item_url) not in unsaved_keys]
        result.added = []
        result.failed = [item for item in collection.items
                         if item not in result.already and item not in result.unavailable]
        return result

    action = '新規作成して登録' if is_new else '追加登録'
    logger.info(f"✓ コレクション「{collection.name}」に{len(result.added)}件を{action}し、保存されたことを確認しました")
    return result
