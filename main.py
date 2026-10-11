"""
メインプログラム - 楽天ROOMコレクション登録

以下の処理フローを実行します:
1. スプレッドシート接続・登録対象の取得（PostStatus「済」かつCollectionStatus「未」）
   - 対象が無ければブラウザを起動せずに終了する
2. 登録対象をCollectionNameごとにまとめる
3. ブラウザを起動し、楽天にログイン（ログイン済みの場合はスキップ）
4. 「my ROOM」⇒「コレクション」を開き、作成済みのコレクションを確認する
5. コレクションごとに登録する（作成済みなら追加登録、無ければ新規作成して登録）
6. コレクションごとに、スプレッドシートのCollectionStatus・CollectedDateを更新する
7. ブラウザを終了する

【CollectionStatusの更新内容】
- 「済」 : コレクションに登録した／すでに登録されていた
- 「不可」: ROOMに投稿した商品の中に見つからない、またはコレクションの上限（100件）を超えた
- 更新しない（「未」のまま）: エラー・保存を確認できなかった・商品一覧を最後まで読み込めなかった場合など。
  次回の実行で再試行される
"""
import asyncio
import datetime
import traceback
from browser_manager import create_browser_manager
from rakuten_login import login_to_rakuten
from google_sheets_utils import connect_to_sheets_and_get_values
from google_sheets_manager import GoogleSheetsManager
from room_collection import get_existing_collections, open_my_room_collections, register_collection
from logger import get_logger


async def main():
    """メイン処理"""
    logger = get_logger()
    browser_manager = None

    try:
        logger.info("=" * 80)
        logger.info("楽天ROOMコレクション登録プログラムを開始します")
        logger.info("=" * 80)

        # 登録日（最初に取得し、すべての行に同じ日付を書き込む）
        collected_date = datetime.datetime.now().strftime('%Y-%m-%d')

        # ステップ1・2: スプレッドシートから登録対象を取得し、CollectionNameごとにまとめる
        logger.info("スプレッドシートへの接続を確認しています...")
        service, values = connect_to_sheets_and_get_values()
        if service is None:
            logger.error("スプレッドシートへの接続に失敗しました。処理を終了します。")
            return
        logger.info(f"接続成功（データ行数: {max(len(values) - 1, 0)}行）")

        sheets_manager = GoogleSheetsManager(service, values)
        collections = sheets_manager.get_target_collections()
        if collections is None:
            logger.error("登録対象の取得に失敗しました。処理を終了します。")
            return
        if not collections:
            logger.info("コレクションに登録する商品がありません。処理を終了します。")
            return

        # ステップ3: ブラウザを起動し、楽天にログイン
        logger.info("ブラウザを起動しています...")
        browser_manager = await create_browser_manager()
        page = await browser_manager.get_page()

        logger.info("楽天にログインしています...")
        if not await login_to_rakuten(page):
            logger.error("楽天へのログインに失敗しました。処理を終了します。")
            return

        # ステップ4: 「my ROOM」⇒「コレクション」を開き、作成済みのコレクションを確認
        logger.info("楽天ROOMのコレクション一覧を開いています...")
        collections_url = await open_my_room_collections(page)
        existing = await get_existing_collections(page, collections_url)

        # ステップ5・6: コレクションごとに登録し、スプレッドシートを更新
        total = {'added': 0, 'already': 0, 'unavailable': 0, 'failed': 0}
        for collection in collections:
            result = await register_collection(page, collections_url, collection, existing)

            for item in result.added:
                logger.info(f"【登録】「{collection.name}」に登録しました: {item.item_code} / {item.item_name}")
            for item in result.already:
                logger.info(f"【登録済み】「{collection.name}」に登録済みでした: {item.item_code} / {item.item_name}")
            for item in result.unavailable:
                logger.warning(f"【不可】「{collection.name}」に登録できませんでした: {item.item_code} / {item.item_name}")
            for item in result.failed:
                logger.error(f"【失敗】「{collection.name}」への登録に失敗しました（次回再試行）: "
                             f"{item.item_code} / {item.item_name}")

            sheets_manager.update_collection_status(result.succeeded, '済', collected_date)
            sheets_manager.update_collection_status(result.unavailable, '不可', collected_date)

            total['added'] += len(result.added)
            total['already'] += len(result.already)
            total['unavailable'] += len(result.unavailable)
            total['failed'] += len(result.failed)

        logger.info(
            f"登録結果: 登録 {total['added']}件 / 登録済み {total['already']}件 / "
            f"不可 {total['unavailable']}件 / 失敗 {total['failed']}件"
        )
        if total['failed']:
            logger.warning("登録に失敗した商品があります。CollectionStatusは「未」のままのため、次回の実行で再試行されます。")

        logger.info("=" * 80)
        logger.info("楽天ROOMコレクション登録プログラムが完了しました")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
        logger.error(traceback.format_exc())

    finally:
        if browser_manager:
            logger.info("ブラウザを閉じています...")
            await browser_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
