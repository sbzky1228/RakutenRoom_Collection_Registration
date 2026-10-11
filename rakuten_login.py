"""
楽天ログインモジュール - Playwrightを使用した楽天市場へのログイン処理
セッション保持（永続化）対応版
"""
import asyncio
import re
from playwright.async_api import Page
from logger import get_logger
from config import (
    RAKUTEN_USER_ID,
    RAKUTEN_PASSWORD,
    RAKUTEN_MY_URL,
    NAVIGATION_TIMEOUT,
)

# 楽天のログイン（認証）画面のホスト
RAKUTEN_LOGIN_HOST = "login.account.rakuten.com"


def is_login_page(url: str) -> bool:
    """楽天のログイン（認証）画面かどうか"""
    return RAKUTEN_LOGIN_HOST in url


async def complete_login_form(page: Page, timeout: int = 60000) -> bool:
    """
    楽天のログイン画面（login.account.rakuten.com）で認証を完了させる。

    初回ログインだけでなく、コレクション操作時などに求められる再認証（/session/upgrade）にも使う。
    画面の状態に応じて以下を繰り返し、ログイン画面から離れたら成功とする。
      - ユーザーID入力欄 → IDを入力して「次へ」
      - 再認証の確認画面（「〇〇として続けますか？」） → 「次へ」
      - パスキー認証の失敗画面 → 「パスワードを使用する」
        （パスキー要求自体はbrowser_managerでキャンセルされ、QRダイアログは出ない）
      - パスワード入力欄 → パスワードを入力して「次へ」

    Args:
        page: ログイン画面を表示しているページ
        timeout: 認証完了までの最大待機時間（ミリ秒）

    Returns:
        bool: ログイン画面から遷移できればTrue
    """
    if not RAKUTEN_USER_ID or not RAKUTEN_PASSWORD:
        get_logger().error("楽天のログイン情報が設定されていません。")
        return False

    user_id_input = page.locator(
        "input[id='user_id'], input[name='loginId'], input[id='loginId'], "
        "input[name='username'], input[placeholder='ユーザーID']"
    ).first
    password_input = page.locator(
        "input[id='password_current'], input[type='password'], input[id='loginUserInner_password']"
    ).first
    # 「次へ」はbutton要素とは限らない（div[id^=cta]、div[id^=prim_]など）ため文言でも探す
    next_button = page.locator("input[value='次へ']").or_(page.get_by_text("次へ", exact=True))
    use_password_button = page.get_by_text("パスワードを使用する", exact=True).first
    # 再認証（/session/upgrade）で最初に出る「〇〇として続けますか？」の確認画面
    continue_confirm_text = page.get_by_text("として続けますか").first

    async def click_next():
        for i in range(await next_button.count()):
            button = next_button.nth(i)
            if await button.is_visible():
                await button.click()
                return True
        return False

    async def wait_hidden(locator, timeout: int = 10000):
        # 画面が切り替わるまで待ち、同じ操作を二重に行わないようにする
        try:
            await locator.wait_for(state='hidden', timeout=timeout)
        except Exception:
            pass

    # ID・パスワードの送信は1回のみとする。
    # 誤ったログイン情報で何度も送信すると、楽天側でアカウントがロックされるおそれがあるため。
    user_id_submitted = False
    password_submitted = False

    deadline = asyncio.get_running_loop().time() + (timeout / 1000)
    while asyncio.get_running_loop().time() < deadline:
        if not is_login_page(page.url):
            return True

        try:
            if await password_input.is_visible():
                if password_submitted:
                    get_logger().error("パスワードを送信しましたがログインできませんでした。"
                          ".envのRAKUTEN_PASSWORDが正しいか確認してください（アカウントロック防止のため再送信しません）")
                    return False
                await password_input.fill(RAKUTEN_PASSWORD)
                await asyncio.sleep(0.5)
                if not await click_next():
                    await password_input.press('Enter')
                password_submitted = True
                get_logger().info("パスワードを入力しました")
                await wait_hidden(password_input, timeout=20000)
            elif await use_password_button.is_visible():
                get_logger().info("パスキー認証をキャンセルし、パスワードでのログインに切り替えます")
                await use_password_button.click()
                await wait_hidden(use_password_button)
            elif await user_id_input.is_visible():
                if user_id_submitted:
                    get_logger().error("ユーザーIDを送信しましたが次の画面に進めませんでした。"
                          ".envのRAKUTEN_USER_IDが正しいか確認してください（アカウントロック防止のため再送信しません）")
                    return False
                await user_id_input.fill(RAKUTEN_USER_ID)
                await asyncio.sleep(0.5)
                if not await click_next():
                    await user_id_input.press('Enter')
                user_id_submitted = True
                get_logger().info("ユーザーIDを入力しました")
                await wait_hidden(user_id_input, timeout=20000)
            elif await continue_confirm_text.is_visible():
                if await click_next():
                    get_logger().info("再認証の確認画面で「次へ」をクリックしました")
                    await wait_hidden(continue_confirm_text)
        except Exception as e:
            # 画面遷移中に要素が消えた場合などは、次のループで再判定する
            print(f"[DEBUG] ログイン画面の操作中に画面が切り替わりました: {e}")

        await asyncio.sleep(0.5)

    get_logger().error(f"ログイン画面での認証が完了しませんでした。現在のURL: {page.url}")
    return False


async def login_to_rakuten(page: Page) -> bool:
    """
    楽天市場にログイン

    my Rakuten（会員ページ）でログイン状態を判定し、未ログインの場合のみID・パスワードで認証します。
    ※永続セッションにより既にログイン済みの場合は入力をスキップします。
    ※パスキー認証はbrowser_managerでキャンセルされるため、「パスワードを使用する」でパスワード入力に切り替えます。

    Args:
        page: Playwrightのページオブジェクト

    Returns:
        bool: ログイン成功時True、失敗時False
    """
    async def check_login_state(timeout: int = 30000) -> bool | None:
        """
        my Rakutenを開いてログイン状態を判定する。
        楽天市場トップのヘッダーは会員情報の描画が不安定なため、会員ページで判定する。
        ※my Rakutenはログイン済みでも読み込み直後の十数秒は「ログイン」ボタンを仮表示するため、
          「ログイン」ボタンの有無ではなく、確定後にだけ出る文言で判定する。

        Returns:
            True: ログイン済み（「ログアウト」が表示）
            False: 未ログイン（「ご利用にはログインが必要です」が表示）
            None: どちらも判定できなかった
        """
        await page.goto(RAKUTEN_MY_URL, wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
        logout_text = page.get_by_text("ログアウト", exact=True)
        need_login_text = page.get_by_text("ご利用にはログインが必要です")
        deadline = asyncio.get_running_loop().time() + (timeout / 1000)

        while asyncio.get_running_loop().time() < deadline:
            if await logout_text.count() > 0:
                return True
            if await need_login_text.count() > 0:
                return False
            await asyncio.sleep(0.5)

        get_logger().error(f"ログイン状態を判定できませんでした。URL: {page.url} / タイトル: {await page.title()}")
        return None

    try:
        # 【セッション判定】保存されたセッションで既にログイン済みならID入力へ進まず成功とする
        login_state = await check_login_state()
        if login_state:
            get_logger().info("保存されたセッションにより、既にログイン済みです。")
            return True
        if login_state is None:
            return False

        # my Rakutenの「ログイン」ボタンからログイン画面へ移動する
        login_button = page.locator("a, button").filter(has_text=re.compile(r"^\s*ログイン\s*$"))
        await login_button.first.click()
        try:
            await page.wait_for_url(is_login_page, wait_until='commit', timeout=30000)
        except Exception:
            get_logger().error(f"ログイン画面に遷移しませんでした。現在のURL: {page.url}")
            return False

        if not await complete_login_form(page):
            return False

        # 会員ページで実際にログインできたかを確認する
        if await check_login_state():
            get_logger().info("楽天市場へのログインに成功しました")
            return True

        get_logger().error(f"楽天市場へのログインに失敗しました。現在のURL: {page.url}")
        return False

    except Exception as e:
        get_logger().error(f"ログイン処理でエラーが発生しました: {e}")
        return False
