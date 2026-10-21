import time

from ulid import generate_ulid

_ENCODING_CHARS = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


def test_generate_ulid_has_correct_shape():
    value = generate_ulid()
    assert len(value) == 26
    assert set(value) <= _ENCODING_CHARS


def test_generate_ulid_is_unique():
    values = {generate_ulid() for _ in range(1000)}
    assert len(values) == 1000


def test_generate_ulid_sorts_with_creation_order():
    first = generate_ulid()
    time.sleep(0.002)
    second = generate_ulid()
    assert first < second
