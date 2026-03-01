from cryptography.fernet import Fernet
import base64
import hashlib

# Stable secret
SECRET = "vote-encryption-key"

def get_key():
    key = hashlib.sha256(SECRET.encode()).digest()
    return base64.urlsafe_b64encode(key)

cipher = Fernet(get_key())

# 🔐 Encrypt
def encrypt_vote(vote_id: str) -> str:
    return cipher.encrypt(vote_id.encode()).decode()

# 🔓 Decrypt
def decrypt_vote(encrypted_text: str) -> str:
    return cipher.decrypt(encrypted_text.encode()).decode()