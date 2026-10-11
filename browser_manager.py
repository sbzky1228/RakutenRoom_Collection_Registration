"""ブラウザ管理モジュール - Playwrightを使用したブラウザ操作"""
from playwright.async_api import async_playwright, Page
from config import APP_DIR, HEADLESS_MODE, BROWSER_TIMEOUT, NAVIGATION_TIMEOUT

# パスキー（publicKey）のnavigator.credentials.getを、ユーザーがキャンセルした時と同じ
# NotAllowedErrorで失敗させる。保存済みパスワードの照会（publicKeyなし）はそのまま通す。
CANCEL_PASSKEY_SCRIPT = """
(() => {
  if (!navigator.credentials || !navigator.credentials.get) return;
  const originalGet = navigator.credentials.get.bind(navigator.credentials);
  navigator.credentials.get = (options) => {
    if (options && options.publicKey) {
      return Promise.reject(new DOMException('Passkey was cancelled by automation.', 'NotAllowedError'));
    }
    return originalGet(options);
  };
})();
"""

class BrowserManager:
    """Playwrightを使用したブラウザ実装を管理するクラス"""
    
    def __init__(self):
        # 初期化: Playwright、BrowserContext、Pageオブジェクトを保持する変数
        self.playwright = None
        self.context = None
        self.page = None
    
    async def launch(self):
        """
        ブラウザを起動
        
        1. Playwrightを初期化
        2. 永続コンテキスト（user_data）を設定してChromiumを起動
        3. ページを取得（または作成）
        4. タイムアウトを設定
        """
        self.playwright = await async_playwright().start()
        
        # .pyはプロジェクト直下、.exeはEXEと同じフォルダに保存する
        user_data_dir = APP_DIR / "user_data"
        user_data_dir.mkdir(parents=True, exist_ok=True)
        print(f"Chromiumのユーザーデータ保存先: {user_data_dir}")
        
        # Chromiumブラウザを永続コンテキスト（launch_persistent_context）で起動
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=HEADLESS_MODE,
            args=[
                # bot検出（AutomationControlled）を回避
                "--disable-blink-features=AutomationControlled",
            ],
            # 一般的なデスクトップChromeのUser-Agentを設定してbot判定を回避
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800}
        )
        
        # パスキー（WebAuthn）要求を即座にキャンセル扱いにする
        # これによりChromeのパスキーQRダイアログを出さず、パスワードログインに切り替えられる
        await self.context.add_init_script(CANCEL_PASSKEY_SCRIPT)

        # 起動時に自動生成されたページを取得（無ければ新規作成）
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        # タイムアウトを設定
        self.page.set_default_timeout(BROWSER_TIMEOUT)
        
        # ナビゲーション待機時間を設定
        self.page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)
        
        return self.page
    
    async def close(self):
        """ブラウザコンテキストおよびPlaywrightを閉じる（二重クローズ・エラー防止版）"""
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
        except Exception:
            pass

        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass  # すでに閉じられている場合の TargetClosedError を無視

        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
    
    async def get_page(self) -> Page:
        """ページオブジェクトを取得"""
        if self.page is None:
            raise RuntimeError("ブラウザが起動していません")
        return self.page


async def create_browser_manager() -> BrowserManager:
    """BrowserManagerインスタンスを生成"""
    manager = BrowserManager()
    await manager.launch()
    return manager