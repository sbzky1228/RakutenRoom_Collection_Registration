import time
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from config import (
    CHROMIUM_EXECUTABLE_PATH,
    HEADLESS_MODE,
    BROWSER_TIMEOUT,
    NAVIGATION_TIMEOUT,
    RAKUTEN_USER_ID,
    RAKUTEN_PASSWORD,
    RAKUTEN_ROOM_BASE_URL,
    SELECTORS,
)
from logger import logger


def login_to_rakuten_room(page):
    page.goto(f'{RAKUTEN_ROOM_BASE_URL}/all/items', wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
    page.wait_for_load_state('domcontentloaded')

    login_button = page.query_selector(SELECTORS.LOGIN_BUTTON)
    if login_button:
        login_button.click()
        page.wait_for_load_state('domcontentloaded')
    else:
        page.goto(f'{RAKUTEN_ROOM_BASE_URL}/login', wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
        page.wait_for_load_state('domcontentloaded')

    user_input = page.wait_for_selector(SELECTORS.LOGIN_USER_INPUT, timeout=BROWSER_TIMEOUT)
    user_input.fill(RAKUTEN_USER_ID)

    password_input = page.wait_for_selector(SELECTORS.LOGIN_PASSWORD_INPUT, timeout=BROWSER_TIMEOUT)
    password_input.fill(RAKUTEN_PASSWORD)

    submit_button = page.query_selector(SELECTORS.LOGIN_SUBMIT_BUTTON)
    if submit_button:
        submit_button.click()
    else:
        password_input.press('Enter')

    page.wait_for_load_state('networkidle', timeout=NAVIGATION_TIMEOUT)


def go_to_collections(page):
    page.goto(f'{RAKUTEN_ROOM_BASE_URL}/mypage', wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
    page.wait_for_load_state('domcontentloaded')
    page.click(SELECTORS.COLLECTION_TAB_BUTTON)
    page.wait_for_load_state('networkidle')


def add_to_collection(page, item):
    collection_name = item['CollectionName']

    if page.query_selector(f'text="{collection_name}"'):
        page.click(f'text="{collection_name}"')
    else:
        page.click(SELECTORS.CREATE_NEW_COLLECTION_BUTTON)
        page.wait_for_selector(SELECTORS.COLLECTION_NAME_INPUT, timeout=BROWSER_TIMEOUT)

        try:
            page.select_option(SELECTORS.COLLECTION_GENRE_SELECT, label='すべてのジャンル')
        except Exception as exc:
            logger.warning(f'コレクション作成画面のジャンル選択が確認できませんでした: {exc}')

        page.fill(SELECTORS.COLLECTION_NAME_INPUT, collection_name)
        page.click(SELECTORS.COLLECTION_CREATE_BUTTON)

    page.wait_for_selector(SELECTORS.ITEM_URL_INPUT, timeout=BROWSER_TIMEOUT)
    page.fill(SELECTORS.ITEM_URL_INPUT, item['ItemURL'])
    page.click(SELECTORS.ITEM_ADD_BUTTON)
    page.wait_for_load_state('networkidle')


def perform_collection_registration(items):
    results = []
    with sync_playwright() as p:
        browser_args = {}
        if CHROMIUM_EXECUTABLE_PATH:
            browser_args['executable_path'] = CHROMIUM_EXECUTABLE_PATH

        browser = p.chromium.launch(headless=HEADLESS_MODE, **browser_args)
        page = browser.new_page()
        page.set_default_timeout(BROWSER_TIMEOUT)
        page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)

        try:
            login_to_rakuten_room(page)
            go_to_collections(page)
            for item in items:
                try:
                    add_to_collection(page, item)
                    results.append({'item': item, 'success': True})
                except Exception as exc:
                    logger.exception(f'コレクション登録に失敗しました: {item}')
                    results.append({'item': item, 'success': False, 'error': str(exc)})
        finally:
            browser.close()

    return results