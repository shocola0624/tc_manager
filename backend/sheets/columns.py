from collections.abc import Mapping, Sequence


def build_column_index(header_row: Sequence[str]) -> dict[str, int]:
    """ヘッダ行から列名 → 列インデックス(0始まり)の対応表を作る。

    列順に依存したアクセスを避けるため、行の読み書きは必ずこの対応表を経由する。
    """
    return {name: index for index, name in enumerate(header_row) if name}


def row_to_record(row: Sequence[str], column_index: Mapping[str, int]) -> dict[str, str]:
    """行(セル値のリスト)を列名 → 値の dict に変換する。

    Sheets API は行末の空セルを切り詰めて返すため、足りない列は空文字で補う。
    """
    record: dict[str, str] = {}
    for name, index in column_index.items():
        record[name] = row[index] if index < len(row) else ""
    return record


def record_to_row(record: Mapping[str, str], column_index: Mapping[str, int]) -> list[str]:
    """列名 → 値の dict を、column_index の列幅に合わせた行(セル値のリスト)に変換する。

    record に含まれない列は空文字を書き込む。
    """
    width = max(column_index.values(), default=-1) + 1
    row = [""] * width
    for name, index in column_index.items():
        if name in record:
            row[index] = record[name]
    return row
