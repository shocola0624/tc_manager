import os
import time

# Crockford base32(ULID仕様の符号化アルファベット。I/L/O/U を除く紛らわしい文字を使わない)。
_ENCODING = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid() -> str:
    """作成順にソート可能なID(ULID, 26文字)を生成する。

    タスクのように作成順を保ちたいIDに使う(item_/activity_ 等の既存のランダムIDとは
    別方針)。外部ライブラリを増やさないよう、48bit タイムスタンプ + 80bit 乱数を
    Crockford base32 で自前エンコードする。
    """
    timestamp_ms = int(time.time() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")  # 80bit
    value = (timestamp_ms << 80) | randomness

    chars = []
    for _ in range(26):
        chars.append(_ENCODING[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))
