from auth.hashing import hash_password, verify_password


def test_hash_then_verify_succeeds():
    hash_hex, salt_hex = hash_password('correct horse battery staple')
    assert verify_password('correct horse battery staple', hash_hex, salt_hex)


def test_wrong_password_fails_verification():
    hash_hex, salt_hex = hash_password('right password')
    assert not verify_password('wrong password', hash_hex, salt_hex)


def test_same_password_different_salts_produce_different_hashes():
    hash1, salt1 = hash_password('same password')
    hash2, salt2 = hash_password('same password')

    assert salt1 != salt2
    assert hash1 != hash2


def test_explicit_salt_is_deterministic():
    salt = bytes.fromhex('00' * 16)
    hash1, salt1 = hash_password('pw', salt=salt)
    hash2, salt2 = hash_password('pw', salt=salt)

    assert hash1 == hash2
    assert salt1 == salt2
