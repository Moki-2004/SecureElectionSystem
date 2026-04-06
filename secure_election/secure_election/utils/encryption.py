import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet_key() -> bytes:
    """
    Derive a Fernet-compatible key from a secret configured in settings.
    """
    secret = getattr(settings, "VOTE_ENCRYPTION_SECRET", None) or settings.SECRET_KEY
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


cipher = Fernet(_get_fernet_key())


def encrypt_vote(candidate_id: str) -> str:
    return cipher.encrypt(candidate_id.encode("utf-8")).decode("utf-8")


def decrypt_vote(encrypted_text: str) -> str:
    return cipher.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
