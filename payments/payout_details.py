import json

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.views.decorators.debug import sensitive_variables


def _cipher():
    try:
        return Fernet(settings.PAYOUT_DETAILS_ENCRYPTION_KEY)
    except ValueError as exc:
        raise ImproperlyConfigured("Set PAYOUT_DETAILS_ENCRYPTION_KEY to a valid Fernet key.") from exc


@sensitive_variables('details')
def encrypt_payout_details(details):
    if details is None or details == {}:
        return ''
    return _cipher().encrypt(json.dumps(details).encode('utf-8')).decode('ascii')


def decrypt_payout_details(ciphertext):
    if not ciphertext:
        return {}
    return json.loads(_cipher().decrypt(ciphertext))
