"""
Legacy sheets module.
Google Sheets関連の処理は `google_sheets_manager.py` に移動しました。
このファイルは互換性のために残されていますが、直接参照しないでください。
"""

from logger import logger


def deprecated_function(*args, **kwargs):
    logger.warning('Legacy sheets.py function called. Use GoogleSheetsManager instead.')
    raise RuntimeError('Legacy sheets module is deprecated. Use GoogleSheetsManager in google_sheets_manager.py')


def get_sheet_data(*args, **kwargs):
    deprecated_function()


def update_sheet_data(*args, **kwargs):
    deprecated_function()


def find_uncollected_items(*args, **kwargs):
    deprecated_function()
