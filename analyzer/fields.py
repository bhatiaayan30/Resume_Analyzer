from django.db import models
from cryptography.fernet import Fernet
from django.conf import settings

def get_fernet():
    key = getattr(settings, 'ENCRYPTION_KEY', None)
    if not key:
        raise ValueError("ENCRYPTION_KEY is not set in settings")
    if isinstance(key, str):
        key = key.encode('utf-8')
    return Fernet(key)

class EncryptedTextField(models.TextField):
    """
    A custom TextField that automatically encrypts its content using Fernet symmetric encryption.
    """
    def get_prep_value(self, value):
        if not value:
            return value
        fernet = get_fernet()
        # Encrypt the string and store as base64 encoded string
        return fernet.encrypt(str(value).encode('utf-8')).decode('utf-8')

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            fernet = get_fernet()
            return fernet.decrypt(value.encode('utf-8')).decode('utf-8')
        except Exception:
            # If it cannot be decrypted, it might be legacy unencrypted data
            return value
