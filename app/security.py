from pwdlib import PasswordHash

# recommended() gives us Argon2, a modern algorithm designed to be slow and
# memory-hungry on purpose, which makes stolen password hashes hard to crack.
_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_hash.verify(plain_password, hashed_password)
