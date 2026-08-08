import datetime
from google_sheets_utils import connect_to_sheets
from google_sheets_manager import GoogleSheetsManager
from logger import logger
from rakuten_room import perform_collection_registration


def main():
    logger.info('プログラムを開始します。')

    service = connect_to_sheets()
    if service is None:
        logger.error('スプレッドシートへの接続に失敗したため、処理を中止します。')
        return

    sheets_manager = GoogleSheetsManager(service)
    items = sheets_manager.get_uncollected_items()

    if not items:
        logger.info('対象のアイテムがありません。')
        return {'processed': False, 'reason': '対象なし'}

    current_date = datetime.datetime.now().strftime('%Y-%m-%d')

    results = perform_collection_registration(items)

    for result in results:
        if result['success']:
            sheets_manager.update_collection_status(result['item']['row_index'], '済', current_date)
            logger.info(f"登録成功: {result['item']['ItemCode']} / {result['item']['CollectionName']}")
        else:
            sheets_manager.update_collection_status(result['item']['row_index'], '不可', current_date)
            logger.error(
                f"登録失敗: {result['item']['ItemCode']} / {result['item']['CollectionName']} - {result['error']}"
            )

    logger.info('コレクション登録処理が完了しました。')
    return {'processed': True, 'count': len(results)}


if __name__ == '__main__':
    main()
