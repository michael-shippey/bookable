from app.security import hash_password, verify_password


def test_hash_is_not_plaintext():
    hashed = hash_password("correct horse battery")
    assert hashed != "correct horse battery"


def test_verify_password():
    hashed = hash_password("correct horse battery")
    assert verify_password("correct horse battery", hashed)
    assert not verify_password("wrong password", hashed)


def test_same_password_hashes_differently():
    # Each hash includes a random salt.
    assert hash_password("same-password") != hash_password("same-password")
