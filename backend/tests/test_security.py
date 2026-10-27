import unittest

from pwdlib import PasswordHash

from app.core.security import hash_password


class PasswordHashTests(unittest.TestCase):
    def test_hash_round_trip_accepts_correct_password_and_rejects_wrong_one(self):
        password = "sample password for a test"
        encoded = hash_password(password)
        verifier = PasswordHash.recommended()
        self.assertTrue(encoded.startswith("$argon2id$"))
        self.assertNotEqual(encoded, password)
        self.assertTrue(verifier.verify(password, encoded))
        self.assertFalse(verifier.verify("incorrect password", encoded))

    def test_repeated_hashing_uses_distinct_salts(self):
        self.assertNotEqual(hash_password("same password"), hash_password("same password"))

    def test_input_validation_and_unicode_whitespace_preservation(self):
        with self.assertRaises(ValueError):
            hash_password("")
        with self.assertRaises(TypeError):
            hash_password(None)
        password = "  mật khẩu 🔐  "
        encoded = hash_password(password)
        verifier = PasswordHash.recommended()
        self.assertTrue(verifier.verify(password, encoded))
        self.assertFalse(verifier.verify(password.strip(), encoded))


if __name__ == "__main__":
    unittest.main()
