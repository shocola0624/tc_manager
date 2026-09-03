class SheetAccessError(Exception):
    """Sheets API とのやり取りで発生したエラー"""


class RowNotFoundError(SheetAccessError):
    """update_by_key / upsert の対象行が見つからない"""


class DuplicateKeyError(SheetAccessError):
    """update_by_key の対象キーに一致する行が複数ある(シート上のデータ不整合)"""
